/** Actual installed CLI -> managed Pi SDK onboarding. No provider/model calls. */
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtemp, mkdir, writeFile, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { resolve, join } from "node:path";
import { pathToFileURL } from "node:url";

const sdkRoot = process.env.PI_SDK_ROOT;
assert.ok(sdkRoot, "Set PI_SDK_ROOT to the installed Pi SDK package");
const cli = process.env.SHARED_MEMORY_TEST_CLI ?? "/data/CoordExp/.shared-memory/.venv/bin/shared-memory";
const { createAgentSession, DefaultResourceLoader, ModelRuntime, SessionManager, SettingsManager } =
  await import(pathToFileURL(join(sdkRoot, "dist/index.js")).href);
const { convertToLlm } = await import(pathToFileURL(join(sdkRoot, "dist/core/messages.js")).href);
const scratch = await mkdtemp(join(tmpdir(), "shared-memory-pi-onboarding-"));
const parent = join(scratch, "parent");
const project = join(parent, "independent");
const root = join(scratch, "memory");
const agentDir = join(scratch, "agent");
const wrapper = join(scratch, "configured-memory.ts");
const source = [{ uri: "file:///fixture/parent-only.md" }];
function command(binary, args, options = {}, expected = 0) {
  const result = spawnSync(binary, args, { encoding: "utf8", ...options });
  assert.equal(result.status, expected, result.stderr);
  return result.stdout;
}
const memory = (args, options = {}, expected = 0) =>
  JSON.parse(command(cli, ["--root", root, ...args], options, expected));
let session;
try {
  await mkdir(project, { recursive: true });
  await mkdir(agentDir);
  command("git", ["-C", parent, "init", "--quiet"]);
  command("git", ["-C", project, "init", "--quiet"]);
  memory(["init"]);
  memory(["register", "--project-id", "parent", "--project-root", parent]);
  const caller = { cwd: parent, harness: "pi", session_id: "fixture-source", actor: "pi" };
  const captured = memory(["call", "--tool", "capture"], { input: JSON.stringify({ context: caller,
    record: { kind: "invariant", title: "Parent-only owner", body: "FOREIGN-PARENT-RECORD", scope: "project", sources: source },
    review: { reason: "Fixture review", evidence: source }, idempotency_key: "parent-source" }) });
  const recordFile = join(root, "records", "parent", `${captured.id}.md`);
  const curationFile = join(root, "curation", "parent", `${captured.id}.json`);
  const registryBefore = await readFile(join(root, "registry.json"));
  const recordBefore = await readFile(recordFile);
  const curationBefore = await readFile(curationFile);
  const projectInfo = memory(["project", "--cwd", project], {}, 2);
  await writeFile(wrapper, `import {createSharedMemoryExtension} from ${JSON.stringify(resolve("adapters/pi/shared-memory.ts"))};\n`
    + `export default createSharedMemoryExtension(${JSON.stringify({ root, cli })});\n`);
  const settingsManager = SettingsManager.inMemory({ packages: [], extensions: [] });
  const resourceLoader = new DefaultResourceLoader({ cwd: project, agentDir, settingsManager,
    additionalExtensionPaths: [wrapper], noExtensions: true, noSkills: true,
    noPromptTemplates: true, noThemes: true, noContextFiles: true });
  await resourceLoader.reload();
  assert.deepEqual(resourceLoader.getExtensions().errors, []);
  const modelRuntime = await ModelRuntime.create({ authPath: join(agentDir, "auth.json"),
    modelsPath: null, allowModelNetwork: false, refreshOnCreate: false });
  const manager = SessionManager.inMemory(project);
  ({ session } = await createAgentSession({ cwd: project, agentDir, settingsManager,
    sessionManager: manager, resourceLoader, modelRuntime, noTools: "all" }));
  const errors = [];
  await session.bindExtensions({ mode: "json", onError: (error) => errors.push(error) });
  const user = { role: "user", content: "fixture task", timestamp: 1 };
  const diagnosed = await session.extensionRunner.emitContext([user]);
  assert.equal(diagnosed[0].customType, "shared-memory-onboarding");
  assert.ok(diagnosed[0].content.includes(projectInfo.registration.command));
  assert.ok(!JSON.stringify(convertToLlm(diagnosed)).includes("FOREIGN-PARENT-RECORD"));
  assert.deepEqual(await readFile(join(root, "registry.json")), registryBefore,
    "actual CLI context and project discovery do not register or mutate bindings");
  command(cli, projectInfo.registration.argv.slice(1));
  await session.extensionRunner.emit({ type: "session_start", reason: "resume" });
  const registered = await session.extensionRunner.emitContext(diagnosed);
  assert.equal(registered[0].customType, "shared-memory-context");
  assert.ok(registered[0].content.includes(projectInfo.suggested_project_id));
  assert.ok(!JSON.stringify(registered).includes("FOREIGN-PARENT-RECORD"));
  const callerAfter = { cwd: project, harness: "pi", session_id: manager.getSessionId(), actor: "pi" };
  assert.deepEqual(memory(["call", "--tool", "search"], {
    input: JSON.stringify({ context: callerAfter, query: "FOREIGN-PARENT-RECORD" }) }).items, []);
  assert.deepEqual(await readFile(recordFile), recordBefore);
  assert.deepEqual(await readFile(curationFile), curationBefore);
  assert.ok(manager.getEntries().every((entry) => entry.type !== "custom_message"));
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({ status: "pass", installed_sdk: sdkRoot,
    boundary: "installed CLI + canonical fixture store + real Pi loader/session + convertToLlm",
    model_calls: 0, checks: ["actionable onboarding", "read-only diagnostics", "independent project registration/retry",
      "no foreign memory", "canonical bytes preserved", "native history preserved"] }));
} finally {
  session?.dispose();
  await rm(scratch, { recursive: true, force: true });
}
