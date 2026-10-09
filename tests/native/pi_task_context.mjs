import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const options = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const sdk = pathToFileURL(path.join(options.sdkRoot, "dist/index.js")).href;
process.env.PI_CODING_AGENT_DIR = options.agentDir;
const { createAgentSession, DefaultResourceLoader, ModelRuntime, SessionManager, SettingsManager } = await import(sdk);
const { createMcpExtension } = await import(pathToFileURL(path.join(options.sdkRoot, 'dist/extensions/mcp/index.js')).href);
const { convertToLlm } = await import(pathToFileURL(path.join(options.sdkRoot, "dist/core/messages.js")).href);
fs.mkdirSync(options.agentDir, { recursive: true });
const wrapper = path.join(options.agentDir, "shared-wrapper.ts");
fs.writeFileSync(wrapper, `import { createSharedMemoryExtension } from ${JSON.stringify(options.extension)};\nexport default createSharedMemoryExtension(${JSON.stringify({root: options.root, cli: options.cli})});\n`);
fs.writeFileSync(path.join(options.agentDir, 'mcp.json'), JSON.stringify({mcpServers: {shared_memory: {
  command: options.cli, args: ['--root', options.root, 'serve'], exposure: 'direct', timeout: 15}}}));
const settingsManager = SettingsManager.inMemory({ packages: [], extensions: [], autoEnableCodemode: false });
const loader = new DefaultResourceLoader({ cwd: options.project, agentDir: options.agentDir, settingsManager,
  additionalExtensionPaths: [wrapper], extensionFactories: [{name: 'installed-mcp', factory: createMcpExtension()}],
  noExtensions: true, noSkills: true, noPromptTemplates: true, noThemes: true, noContextFiles: true });
await loader.reload();
assert.deepEqual(loader.getExtensions().errors, []);
const modelRuntime = await ModelRuntime.create({authPath: path.join(options.agentDir, 'auth.json'), modelsPath: null,
  allowModelNetwork: false, refreshOnCreate: false});
const manager = SessionManager.inMemory(options.project);
const { session } = await createAgentSession({ cwd: options.project, agentDir: options.agentDir, settingsManager,
  sessionManager: manager, resourceLoader: loader, modelRuntime, noTools: true });
try {
  const errors = [];
  await session.bindExtensions({mode: 'json', onError: error => errors.push(error)});
  await session.extensionRunner.emitBeforeAgentStart('Fixture task', undefined, {sections: {}});
  assert.deepEqual(errors, []);
  const tools = session.agent.state.tools;
  const contextTool = tools.find(t => t.name.endsWith("__context"));
  assert.ok(contextTool, session.getAllTools().map(t => t.name).join(","));
  const caller = () => ({ cwd: options.project, harness: "pi", session_id: manager.getSessionId(), actor: "pi" });
  async function contextCall(id, mode, query, previousRevision) {
    const args = { context: caller(), task_mode: mode, query,
      ...(previousRevision ? { previous_revision: previousRevision } : {}) };
    const result = await contextTool.execute(id, args, undefined, undefined);
    assert.ok(result.content);
    await session.extensionRunner.emitToolResult({ type: "tool_result", toolName: contextTool.name,
      toolCallId: id, input: args, content: result.content, isError: false, details: result.details });
    return { role: "toolResult", toolCallId: id, toolName: contextTool.name, content: result.content,
             isError: false, timestamp: 1 };
  }
  const before = JSON.stringify(manager.getEntries());
  const user = { role: "user", content: "Fixture", timestamp: 1 };
  console.log(JSON.stringify({stage: 'actual-mcp-ready'}));
  const first = await contextCall("research-call", "research", "airport");
  const research = await session.extensionRunner.emitContext([user, first]);
  const owned = values => values.filter(m => m.role === "custom" && ["shared-memory-context", "shared-memory-task-context"].includes(m.customType));
  assert.equal(owned(research).length, 2);
  assert.ok(owned(research).find(m => m.customType === "shared-memory-task-context").content.includes(options.sentinel));
  assert.ok(owned(research).every(m => !m.content.includes(options.forbidden)));
  assert.ok(JSON.stringify(convertToLlm(research)).includes(options.sentinel));
  assert.ok(!JSON.stringify(research.find(m => m.role === "toolResult")).includes(options.sentinel));
  const firstPacket = JSON.parse(first.content.find(c => c.type === "text").text);
  const unchanged = await contextCall("unchanged-call", "research", "airport", firstPacket.packet_revision);
  const unchangedPacket = JSON.parse(unchanged.content.find(c => c.type === "text").text);
  assert.equal(unchangedPacket.unchanged, true);
  assert.equal(unchangedPacket.text, "");
  const repeated = await session.extensionRunner.emitContext([user, first, unchanged]);
  assert.deepEqual(owned(repeated), owned(research));
  assert.equal(owned(repeated).length, 2);
  assert.equal(JSON.stringify(convertToLlm(repeated)).split(options.sentinel).length,
               JSON.stringify(convertToLlm(research)).split(options.sentinel).length);
  const extended = await session.extensionRunner.emitContext([...research, { role: "user", content: "Continue", timestamp: 2 }]);
  assert.deepEqual(convertToLlm(extended).slice(0, convertToLlm(research).length), convertToLlm(research));
  const second = await contextCall("general-call", "general", "airport");
  const general = await session.extensionRunner.emitContext([user, first, second]);
  assert.deepEqual(owned(general).find(m => m.customType === "shared-memory-context"),
                   owned(research).find(m => m.customType === "shared-memory-context"));
  assert.ok(owned(general).find(m => m.customType === "shared-memory-task-context").content.includes("task_mode: general"));
  assert.ok(Buffer.byteLength(JSON.stringify(owned(general))) <= 8000);
  assert.equal(JSON.stringify(manager.getEntries()), before);
  await session.extensionRunner.emitToolResult({ type: "tool_result", toolName: contextTool.name,
    toolCallId: "failed-call", input: {}, content: [{ type: "text", text: "fixture failure" }], isError: true });
  const failed = await session.extensionRunner.emitContext([user, first, second]);
  assert.equal(owned(failed).length, 0);
  // Native restart/replacement closes the prior MCP transport before SessionStart.
  await session.extensionRunner.emit({ type: 'session_shutdown', reason: 'exit' });
  await session.extensionRunner.emit({ type: "session_start" });
  const resumed = await session.extensionRunner.emitContext([user, first, second]);
  assert.ok(owned(resumed).find(m => m.customType === "shared-memory-task-context").content.includes("task_mode: general"));
  await session.extensionRunner.emit({ type: "session_compact", compactionEntry: {}, fromExtension: false });
  const compacted = await session.extensionRunner.emitContext([user]);
  assert.ok(owned(compacted).length <= 2 && owned(compacted).length > 0);
  const previousSession = manager.getSessionId();
  console.log(JSON.stringify({stage: 'before-session-switch'}));
  manager.newSession();
  const newSessionHistory = JSON.stringify(manager.getEntries());
  // Native restart/replacement closes the prior MCP transport before SessionStart.
  await session.extensionRunner.emit({ type: 'session_shutdown', reason: 'exit' });
  await session.extensionRunner.emit({ type: "session_start" });
  const switched = await session.extensionRunner.emitContext([user, first]);
  for (const message of owned(switched)) {
    assert.ok(message.content.includes(manager.getSessionId()));
    assert.ok(!message.content.includes(previousSession));
  }
  assert.equal(JSON.stringify(manager.getEntries()), newSessionHistory);
  assert.ok(!JSON.stringify(convertToLlm(switched)).includes(previousSession));
  console.log(JSON.stringify({ status: "passed", actual_sdk: true, actual_mcp_context: true,
    task_replacement: true, combined_budget: true, stable_background: true, ordinary_prefix: true,
    context_result_deduplicated: true, native_history_unchanged: true, failed_refresh_cleared: true,
    resume_binding: true, compaction_refresh: true, session_isolation: true, model_network_called: false }));
} finally {
  console.log(JSON.stringify({stage: 'shutdown-start'}));
  await session.extensionRunner.emit({type: 'session_shutdown', reason: 'exit'});
  session.dispose();
  console.log(JSON.stringify({stage: 'shutdown-complete', active_handle_types: process._getActiveHandles().map(h => h.constructor.name)}));
}
