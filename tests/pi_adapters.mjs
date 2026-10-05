/** Installed Pi loader/session boundary. No prompt, provider, or model calls. */
import assert from "node:assert/strict";
import { mkdtemp, mkdir, writeFile, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { resolve, join } from "node:path";
import { pathToFileURL } from "node:url";

const sdkRoot = process.env.PI_SDK_ROOT;
assert.ok(sdkRoot, "Set PI_SDK_ROOT to the installed @earendil-works/pi-coding-agent package");
const { createAgentSession, DefaultResourceLoader, ModelRuntime, SessionManager, SettingsManager } =
  await import(pathToFileURL(join(sdkRoot, "dist/index.js")).href);
const { convertToLlm } = await import(pathToFileURL(join(sdkRoot, "dist/core/messages.js")).href);
const extension = resolve("adapters/pi/shared-memory.ts");
const scratch = await mkdtemp(join(tmpdir(), "shared-memory-pi-test-"));
const project = join(scratch, "actual-host-project");
const agentDir = join(scratch, "agent");
const fixtureCli = join(scratch, "context-fixture.mjs");
const response = join(scratch, "response.json");
const calls = join(scratch, "calls.jsonl");
const wrapper = join(scratch, "configured-memory.ts");
const reminder = "Shared-memory reminder: fixture workflow guidance.\n";
const firstText = reminder + "<shared-memory-context>first</shared-memory-context>";
const currentText = reminder + "<shared-memory-context>current</shared-memory-context>";
let session;
try {
  await mkdir(project);
  await mkdir(agentDir);
  await writeFile(fixtureCli, `#!${process.execPath}\nimport {readFileSync,appendFileSync} from 'node:fs';
appendFileSync(${JSON.stringify(calls)},JSON.stringify(process.argv.slice(2))+'\\n');
process.stdout.write(readFileSync(${JSON.stringify(response)},'utf8'));\n`, { mode: 0o700 });
  delete process.env.SHARED_MEMORY_CLI;
  delete process.env.SHARED_MEMORY_ROOT;
  await writeFile(wrapper, `import {createSharedMemoryExtension} from ${JSON.stringify(extension)};\n`
    + `export default createSharedMemoryExtension(${JSON.stringify({ root: scratch, cli: fixtureCli })});\n`);
  await writeFile(response, JSON.stringify({ status: "ok", text: firstText }));
  const settingsManager = SettingsManager.inMemory({ packages: [], extensions: [] });
  const loader = new DefaultResourceLoader({ cwd: project, agentDir, settingsManager,
    additionalExtensionPaths: [wrapper], noExtensions: true, noSkills: true,
    noPromptTemplates: true, noThemes: true, noContextFiles: true });
  await loader.reload();
  assert.deepEqual(loader.getExtensions().errors, []);
  assert.equal(loader.getExtensions().extensions.length, 1);
  const modelRuntime = await ModelRuntime.create({ authPath: join(agentDir, "auth.json"),
    modelsPath: null, allowModelNetwork: false, refreshOnCreate: false });
  const manager = SessionManager.inMemory(project);
  ({ session } = await createAgentSession({ cwd: project, agentDir, settingsManager,
    sessionManager: manager, resourceLoader: loader, modelRuntime, noTools: "all" }));
  const errors = [];
  await session.bindExtensions({ mode: "json", onError: (error) => errors.push(error) });
  const stale = { role: "custom", customType: "shared-memory-context", content: "stale", display: false, timestamp: 1 };
  const user = { role: "user", content: "host user", timestamp: 2 };
  const system = { role: "system", content: "host system prompt", timestamp: 0 };
  const historyBeforeContext = structuredClone(manager.getEntries());
  const prefix = await session.extensionRunner.emitContext([system, user]);
  const convertedPrefix = convertToLlm(prefix);
  const continuation = [
    { role: "assistant", content: [{ type: "toolCall", id: "fixture-call", name: "fixture", arguments: {} }], timestamp: 3 },
    { role: "toolResult", toolCallId: "fixture-call", toolName: "fixture", content: [{ type: "text", text: "fixture result" }], isError: false, timestamp: 4 },
    { role: "user", content: "host continuation", timestamp: 5 },
  ];
  const grown = await session.extensionRunner.emitContext([...prefix, ...continuation]);
  const convertedGrown = convertToLlm(grown);
  assert.deepEqual(convertedGrown.slice(0, convertedPrefix.length), convertedPrefix,
    "ordinary conversation growth preserves the entire converted prefix");
  assert.deepEqual(convertedGrown.slice(convertedPrefix.length), continuation);
  assert.equal(grown.filter((m) => m.customType === "shared-memory-context").length, 1);
  assert.deepEqual(grown[0], system, "native dispatch retains the leading system prompt");
  assert.equal(grown[1].customType, "shared-memory-context");
  assert.equal(convertedGrown[1].role, "user", "recall has user-level authority");
  assert.deepEqual(manager.getEntries(), historyBeforeContext, "context transforms leave native history unchanged");
  // The installed context runner hides system messages; also retain the handler's
  // placement contract for callers that expose more than one leading system message.
  const contextHandler = loader.getExtensions().extensions[0].handlers.get("context")[0];
  const secondSystem = { role: "system", content: "host prompt section", timestamp: 1 };
  const peer = { role: "custom", customType: "peer-context", content: "peer guidance", display: false, timestamp: 2 };
  const direct = await contextHandler({ type: "context", messages: [system, secondSystem, user, stale, peer, stale] },
    session.extensionRunner.createContext());
  assert.deepEqual(direct.messages.slice(0, 2), [system, secondSystem]);
  assert.equal(direct.messages[2].customType, "shared-memory-context");
  assert.deepEqual(direct.messages.slice(3), [user, peer], "ordinary and peer messages retain their order");
  let messages = await session.extensionRunner.emitContext([user, stale, stale]);
  assert.equal(messages.length, 2);
  assert.equal(messages[0].content, firstText);
  messages = await session.extensionRunner.emitContext(messages);
  assert.equal(messages.filter((m) => m.customType === "shared-memory-context").length, 1);
  assert.ok(convertToLlm(messages).some((m) => JSON.stringify(m.content).includes(firstText.replace(/\n/g, "\\n"))));
  await writeFile(response, JSON.stringify({ status: "ok", text: currentText }));
  await session.extensionRunner.emit({ type: "session_start", reason: "resume" });
  messages = await session.extensionRunner.emitContext(messages);
  assert.equal(messages[0].content, currentText);
  await session.extensionRunner.emit({ type: "session_compact", reason: "manual", willRetry: false,
    fromExtension: false, compactionEntry: { id: "fixture-compaction" } });
  messages = await session.extensionRunner.emitContext(messages);
  assert.equal(messages.length, 2);
  const actualCalls = (await readFile(calls, "utf8")).trim().split("\n").map(JSON.parse);
  assert.equal(actualCalls.length, 3, "startup/resume/compact refresh only");
  for (const args of actualCalls) {
    assert.equal(args[args.indexOf("--cwd") + 1], project);
    assert.equal(args[args.indexOf("--session-id") + 1], manager.getSessionId());
    assert.equal(args[args.indexOf("--harness") + 1], "pi");
  }
  const previousSessionId = manager.getSessionId();
  manager.newSession();
  assert.notEqual(manager.getSessionId(), previousSessionId);
  await writeFile(response, JSON.stringify({ status: "ok", text: firstText }));
  messages = await session.extensionRunner.emitContext(messages);
  assert.equal(messages[0].content, firstText, "changed session identity refreshes recalled content");
  const identityCalls = (await readFile(calls, "utf8")).trim().split("\n").map(JSON.parse);
  assert.equal(identityCalls.length, 4);
  assert.equal(identityCalls.at(-1)[identityCalls.at(-1).indexOf("--session-id") + 1], manager.getSessionId());
  await writeFile(response, "malformed");
  await session.extensionRunner.emit({ type: "session_start", reason: "reload" });
  messages = await session.extensionRunner.emitContext(messages);
  assert.deepEqual(messages, [user], "invalid transport clears old recall");
  await writeFile(response, JSON.stringify({ status: "ok", text: reminder + "x".repeat(6001 - reminder.length) }));
  await session.extensionRunner.emit({ type: "session_start", reason: "reload" });
  assert.deepEqual(await session.extensionRunner.emitContext(messages), [user]);
  await writeFile(response, JSON.stringify({ status: "unmapped", text: "must not be injected" }));
  await session.extensionRunner.emit({ type: "session_start", reason: "reload" });
  assert.deepEqual(await session.extensionRunner.emitContext(messages), [user], "unmapped scope ignores all content");
  const failedRefreshCalls = (await readFile(calls, "utf8")).trim().split("\n").length;
  await session.extensionRunner.emitContext(messages);
  assert.equal((await readFile(calls, "utf8")).trim().split("\n").length, failedRefreshCalls,
    "failed refresh stays empty without retrying on every model request");
  assert.ok(manager.getEntries().every((entry) => entry.type !== "custom_message"),
    "request context recall is never persisted in native session history");
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({ status: "pass", installed_sdk: sdkRoot,
    boundary: "real extension loader + in-memory session + native event dispatch + convertToLlm",
    context_transport: "fixture executable", model_calls: 0,
    checks: ["actual cwd", "session identity refresh", "startup/resume/compact", "ordinary-growth converted prefix", "leading system preserved", "user-level recall", "replacement", "fail closed", "bounded", "native history preserved"],
    cache_claim: "CPU prefix correctness only; provider cache behavior unmeasured" }));
} finally {
  session?.dispose();
  await rm(scratch, { recursive: true, force: true });
}
