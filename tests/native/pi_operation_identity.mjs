import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

const o = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
process.env.PI_CODING_AGENT_DIR = o.agentDir;
const sdk = await import(pathToFileURL(path.join(o.sdkRoot, 'dist/index.js')).href);
const {convertToLlm} = await import(pathToFileURL(path.join(o.sdkRoot, 'dist/core/messages.js')).href);
sdk.initTheme('dark', false);
fs.mkdirSync(o.agentDir, {recursive: true});
const wrapper = path.join(o.agentDir, 'configured-memory.ts');
fs.writeFileSync(wrapper, `import {createSharedMemoryExtension} from ${JSON.stringify(o.extension)};\nexport default createSharedMemoryExtension(${JSON.stringify({root:o.root, cli:o.cli})});\n`);
fs.writeFileSync(path.join(o.agentDir, 'mcp.json'), JSON.stringify({mcpServers:{'shared-memory':{
  command:o.cli, args:['--root',o.root,'serve'], exposure:'direct', directTools:true, timeout:15}}}));
const factories = o.transport === 'native' ? [{name:'native-mcp', factory:(await import(pathToFileURL(path.join(o.sdkRoot, 'dist/extensions/mcp/index.js')).href)).createMcpExtension()}] : [];
const settings = sdk.SettingsManager.inMemory({packages:[], extensions:[], autoEnableCodemode:false});
const loader = new sdk.DefaultResourceLoader({cwd:o.project, agentDir:o.agentDir, settingsManager:settings,
  additionalExtensionPaths:[wrapper, ...(o.transport === 'installed' ? [o.adapter] : [])], extensionFactories:factories,
  noExtensions:true, noSkills:true, noPromptTemplates:true, noThemes:true, noContextFiles:true});
await loader.reload();
assert.deepEqual(loader.getExtensions().errors, []);
const runtime = await sdk.ModelRuntime.create({authPath:path.join(o.agentDir,'auth.json'), modelsPath:null, allowModelNetwork:false, refreshOnCreate:false});
const manager = sdk.SessionManager.inMemory(o.project);
let {session} = await sdk.createAgentSession({cwd:o.project, agentDir:o.agentDir, settingsManager:settings, sessionManager:manager, resourceLoader:loader, modelRuntime:runtime, noTools:true});
const errors = [];
const owned = ms => ms.filter(m => m.role === 'custom' && m.customType?.startsWith('shared-memory'));
const user = {role:'user', content:'CPU fixture', timestamp:1};
const caller = () => ({cwd:o.project, harness:'pi', session_id:manager.getSessionId(), actor:'pi'});
let sequence = 0;
const contextCalls = () => fs.readFileSync(o.calls, 'utf8').trim().split('\n').map(JSON.parse).filter(args => args[2] === 'context').length;
async function dispatch(name, content, details, isError=false) {
  const id = `operation-${++sequence}`;
  await session.extensionRunner.emitToolResult({type:'tool_result', toolName:name, toolCallId:id,
    input:{}, content, details, isError});
  return {role:'toolResult', toolName:name, toolCallId:id, content, details, isError, timestamp:sequence};
}
async function call(tool, args) {
  const result = await tool.execute(`execute-${++sequence}`, args, undefined, undefined);
  return dispatch(tool.name, result.content, result.details, Boolean(result.isError || result.details?.error));
}
async function resume() {
  // Native session replacement closes the old transport before SessionStart.
  await session.extensionRunner.emit({type:'session_shutdown', reason:'exit'});
  await session.extensionRunner.emit({type:'session_start', reason:'resume'});
}
function assertPacket(messages, mode) {
  assert.equal(owned(messages).length, 2, 'one bootstrap and one task packet');
  assert.ok(owned(messages)[1].content.includes(`task_mode: ${mode}`));
  assert.ok(owned(messages)[1].content.includes('FIXTURE_TASK'));
  assert.ok(Buffer.byteLength(JSON.stringify(owned(messages))) <= 8000);
  assert.equal(JSON.stringify(convertToLlm(messages)).split('FIXTURE_TASK').length - 1, 1, 'no duplicate task text');
  assert.ok(!messages.filter(m => m.role === 'toolResult').some(m => JSON.stringify(m).includes('<shared-memory-task-context>')));
}
try {
  await session.bindExtensions({mode:'json', onError:e => errors.push(e)});
  await session.extensionRunner.emitBeforeAgentStart('CPU fixture', undefined, {sections:{}});
  if (o.transport === 'installed' && !session.agent.state.tools.some(t => t.name === 'shared-memory_context')) {
    // First isolated connection fills the installed adapter's real metadata cache.
    // Its direct registrations are frozen at load, so use a fresh extension runtime.
    const gateway = session.agent.state.tools.find(t => t.name === 'mcp');
    assert.ok(gateway);
    await gateway.execute('warm-catalog', {server:'shared-memory'}, undefined, undefined);
    await session.extensionRunner.emit({type:'session_shutdown', reason:'exit'});
    session.dispose();
    await loader.reload();
    ({session} = await sdk.createAgentSession({cwd:o.project, agentDir:o.agentDir, settingsManager:settings,
      sessionManager:manager, resourceLoader:loader, modelRuntime:runtime, noTools:true}));
    await session.bindExtensions({mode:'json', onError:e => errors.push(e)});
    await session.extensionRunner.emitBeforeAgentStart('CPU fixture', undefined, {sections:{}});
  }
  const names = session.getAllTools().map(t => t.name);
  const name = o.transport === 'installed' ? 'shared-memory_context' : 'mcp__shared_memory__context';
  const tool = session.agent.state.tools.find(t => t.name === name);
  assert.ok(tool, names.join(','));
  const history = JSON.stringify(manager.getEntries());
  const first = await call(tool, {caller:caller(), query:'airport', task_mode:'research'});
  console.log(JSON.stringify({stage:'actual-context', tool:name, details:first.details,
    packet:JSON.parse(first.content[0].text)}));
  let projected = await session.extensionRunner.emitContext([user, first]);
  assertPacket(projected, 'research');
  const grown = await session.extensionRunner.emitContext([...projected, {role:'user', content:'Continue', timestamp:3}]);
  assert.deepEqual(convertToLlm(grown).slice(0, convertToLlm(projected).length), convertToLlm(projected));
  const background = owned(projected)[0];
  const second = await call(tool, {caller:caller(), query:'airport', task_mode:'general'});
  projected = await session.extensionRunner.emitContext([user, first, second]);
  assertPacket(projected, 'general');
  assert.deepEqual(owned(projected)[0], background);
  const packet = JSON.parse(second.content[0].text);
  const unchanged = await call(tool, {caller:caller(), query:'airport', task_mode:'general', previous_revision:packet.packet_revision});
  assert.equal(JSON.parse(unchanged.content[0].text).unchanged, true);
  assert.deepEqual(owned(await session.extensionRunner.emitContext([user, first, second, unchanged])), owned(projected));

  // Actual installed gateway execution, including persisted tool-result details projection.
  if (o.transport === 'installed') {
    const gateway = session.agent.state.tools.find(t => t.name === 'mcp');
    assert.ok(gateway);
    const gatewayMessage = await call(gateway, {server:'shared-memory', tool:'context', args:{caller:caller(), query:'airport', task_mode:'research'}});
    assert.equal(gatewayMessage.details.server, 'shared-memory');
    assert.equal(gatewayMessage.details.tool, 'context');
    console.log(JSON.stringify({stage:'actual-gateway', details:gatewayMessage.details,
      packet:JSON.parse(gatewayMessage.content[0].text)}));
    assertPacket(await session.extensionRunner.emitContext([user, gatewayMessage]), 'research');
    await resume();
    assertPacket(await session.extensionRunner.emitContext([user, gatewayMessage]), 'research');
  }
  // Lifecycle events are real installed dispatch, histories are synthetic/in-memory.
  await resume();
  assertPacket(await session.extensionRunner.emitContext([user, second]), 'general');
  await session.extensionRunner.emit({type:'session_compact', compactionEntry:{}, fromExtension:false});
  assertPacket(await session.extensionRunner.emitContext([user]), 'general');

  // Relevant candidate and reviewed capture calls refresh an already bound task packet.
  for (const op of ['candidate', 'capture']) {
    const mutation = session.agent.state.tools.find(t => t.name === (o.transport === 'installed' ? 'shared-memory_capture' : 'mcp__shared_memory__capture'));
    assert.ok(mutation);
    const rec = {kind:'observation', title:`airport ${op}`, body:`REFRESH_${op}: airport fixture only.`, scope:'project', sources:[{uri:pathToFileURL(path.join(o.project,'owner.md')).href}]};
    const args = {caller:caller(), record:rec, idempotency_key:`fixture-${op}`,
      ...(op === 'capture' ? {review:{reason:'Synthetic review only', evidence:rec.sources}} : {})};
    const beforeRefresh = contextCalls();
    await call(mutation, args);
    assert.equal(contextCalls(), beforeRefresh + 1, op+' performs an actual CLI refresh');
    const after = await session.extensionRunner.emitContext([user]);
    assertPacket(after, 'general');
    if (op === 'capture') assert.ok(owned(after)[1].content.includes('REFRESH_capture'));
  }

  // Exact aliases only; untrusted/ambiguous output must never bypass projection.
  for (const alias of ['shared-memory_context','shared_memory_context','mcp__shared_memory__context','mcp__shared-memory__context']) {
    const msg = await dispatch(alias, second.content);
    assertPacket(await session.extensionRunner.emitContext([user, msg]), 'general');
  }
  const foreignTool = {...second, toolName:'other-shared-memory_context', toolCallId:'foreign-tool'};
  const retained = await session.extensionRunner.emitContext([user, foreignTool]);
  assert.deepEqual(retained.find(m => m.toolCallId === 'foreign-tool'), foreignTool, 'unrelated tool is not intercepted');
  for (const [label, content, details, isError] of [
    ['transport-error',second.content,undefined,true],
    ['details-error',second.content,{error:'tool_error'},false],
    ['malformed',[{type:'text',text:'malformed <shared-memory-context>FOREIGN</shared-memory-context>'}],undefined,false],
    ['null',[{type:'text',text:'null'}],undefined,false],
    ['non-ok',[{type:'text',text:JSON.stringify({...packet,status:'invalid'})}],undefined,false],
    ['invalid-parts',[{type:'text',text:JSON.stringify({...packet,parts:[]})}],undefined,false],
    ['oversized',[{type:'text',text:JSON.stringify({...packet,text:'x'.repeat(8001)})}],undefined,false],
    ['foreign-caller',[{type:'text',text:JSON.stringify({...packet,caller_context:{...packet.caller_context,session_id:'FOREIGN_SESSION'}})}],undefined,false],
    ['conflicting-details',second.content,{server:'other',tool:'context'},false],
  ]) {
    const good = await dispatch(name, second.content);
    const bad = await dispatch(name, content, details, isError);
    const result = await session.extensionRunner.emitContext([user, good, bad]);
    assert.equal(owned(result).length, 0, label+' clears stale packet');
    assert.ok(!JSON.stringify(convertToLlm(result)).includes('<shared-memory-context>'), label+' does not expose raw failed packet');
    await resume();
    const resumed = await session.extensionRunner.emitContext([user, good, bad]);
    assert.equal(owned(resumed).length, 0, label+' latest failed context prevents stale recovery');
  }
  // Budget failures expose only a caller-validated bounded continuation, never raw text.
  const pointer = {ids:[packet.items[0].id]};
  const limited = await dispatch(name, [{type:'text',text:JSON.stringify({...packet, status:'budget-limited', continuation:pointer})}]);
  const limitedProjection = await session.extensionRunner.emitContext([user, limited]);
  assert.equal(owned(limitedProjection).length, 0);
  assert.deepEqual(JSON.parse(limitedProjection.find(m => m.role === 'toolResult').content[0].text).continuation, pointer);
  assert.ok(!JSON.stringify(convertToLlm(limitedProjection)).includes('<shared-memory-context>'));
  assert.deepEqual(await session.extensionRunner.emitContext(limitedProjection), limitedProjection);
  // Receipt-cache eviction cannot make an older historical binding current again.
  let latest;
  for (let i=0; i<2050; i++) latest = await dispatch(name, second.content);
  assertPacket(await session.extensionRunner.emitContext([user, first, latest]), 'general');
  // Adapter errors on mutations do not trigger a false success refresh.
  const beforeFailedMutation = contextCalls();
  await dispatch(o.transport === 'installed' ? 'shared-memory_capture' : 'mcp__shared_memory__capture',
    [{type:'text',text:'failed'}], {error:'tool_error'}, false);
  assert.equal(contextCalls(), beforeFailedMutation);
  fs.writeFileSync(o.failure, 'owned fixture failure');
  await resume();
  assert.equal(owned(await session.extensionRunner.emitContext([user])).length, 0, 'failed CLI refresh removes stale recall');
  fs.unlinkSync(o.failure);
  // Recovery must not treat unchanged-only history as a full accepted snapshot.
  await resume();
  const wrongUnchanged = {...JSON.parse(unchanged.content[0].text), packet_revision:'wrong-revision'};
  const badUnchanged = await dispatch(name, [{type:'text',text:JSON.stringify(wrongUnchanged)}]);
  assert.equal(owned(await session.extensionRunner.emitContext([user,badUnchanged])).length, 0);
  assert.equal(JSON.stringify(manager.getEntries()), history, 'context transforms never write native history');
  manager.newSession();
  const newHistory = JSON.stringify(manager.getEntries());
  const isolated = await session.extensionRunner.emitContext([user, second]);
  assert.ok(!JSON.stringify(convertToLlm(isolated)).includes(packet.caller_context.session_id));
  assert.ok(owned(isolated).every(m => m.content.includes(manager.getSessionId())));
  assert.equal(JSON.stringify(manager.getEntries()), newHistory);
  assert.deepEqual(errors, []);
  console.log(JSON.stringify({status:'passed', transport:o.transport, installedSdk:o.sdkRoot, installedAdapter:o.transport === 'installed' ? o.adapter : null,
    modelCalls:0, providerCalls:0, contextTool:name, checks:['acceptance','projection','exact aliases','gateway details','mutation refresh','failure clearing','resume','compaction','session isolation','native history preservation'],
    limitation:'Synthetic in-memory histories and dispatched lifecycle events; not persisted restart/real compaction or provider proof.'}));
} finally {
  await session.extensionRunner.emit({type:'session_shutdown', reason:'exit'});
  session.dispose();
}
