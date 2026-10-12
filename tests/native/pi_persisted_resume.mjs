/** Disk-backed native sessions + fresh-process reopen + actual SDK prompt.
 * The local deterministic stream is NOT a remote provider or cache measurement.
 */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';

const o = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const phase = process.argv[3];
process.env.PI_CODING_AGENT_DIR = o.agentDir;
const sdk = await import(pathToFileURL(path.join(o.sdkRoot, 'dist/index.js')).href);
const ai = await import(pathToFileURL(path.join(path.dirname(o.sdkRoot), 'pi-ai/dist/index.js')).href);
sdk.initTheme('dark', false);
fs.mkdirSync(o.agentDir, {recursive:true});
fs.mkdirSync(o.sessionDir, {recursive:true});
const wrapper = path.join(o.agentDir, 'memory-wrapper.ts');
fs.writeFileSync(wrapper, `import {createSharedMemoryExtension} from ${JSON.stringify(o.extension)};\nexport default createSharedMemoryExtension(${JSON.stringify({root:o.root,cli:o.cli})});\n`);
fs.writeFileSync(path.join(o.agentDir, 'mcp.json'), JSON.stringify({mcpServers:{'shared-memory':{
  command:o.cli, args:['--root',o.root,'serve'], exposure:'direct', directTools:true, timeout:15}}}));
const settings = sdk.SettingsManager.inMemory({packages:[], extensions:[], autoEnableCodemode:false,
  compaction:{enabled:false}, retry:{enabled:false}});
const loader = new sdk.DefaultResourceLoader({cwd:o.project, agentDir:o.agentDir, settingsManager:settings,
  additionalExtensionPaths:[wrapper,o.adapter], noExtensions:true, noSkills:true, noPromptTemplates:true,
  noThemes:true, noContextFiles:true});
await loader.reload();
assert.deepEqual(loader.getExtensions().errors, []);
const saved = phase === 'resume' ? JSON.parse(fs.readFileSync(o.primaryReceipt, 'utf8')) : null;
const manager = phase === 'warm' ? sdk.SessionManager.inMemory(o.project)
  : saved ? sdk.SessionManager.open(saved.sessionFile, o.sessionDir)
  : sdk.SessionManager.create(o.project, o.sessionDir);
if (saved) {
  assert.equal(manager.getSessionId(), saved.sessionId, 'Open the exact persisted session, not continueRecent');
  assert.equal(manager.getSessionFile(), saved.sessionFile);
}
const requests = [];
const fakeCalls = [];
const runtime = await sdk.ModelRuntime.create({authPath:path.join(o.agentDir,'auth.json'), modelsPath:null,
  allowModelNetwork:false, refreshOnCreate:false});
const modelDefinition = {id:'cpu-fixture', name:'CPU-only deterministic test stream', api:'memory-fixture',
  baseUrl:'http://127.0.0.1:0/never-used', reasoning:false, input:['text'],
  cost:{input:0,output:0,cacheRead:0,cacheWrite:0}, contextWindow:64000, maxTokens:1024};
const caller = {cwd:o.project, harness:'pi', session_id:manager.getSessionId(), actor:'pi'};
const binding = phase === 'peer' ? {task_mode:'general', query:'OTHER_SESSION_QUERY_CANARY'}
  : {task_mode:'research', query:'airport'};
const usage = {input:0,output:0,cacheRead:0,cacheWrite:0,totalTokens:0,
  cost:{input:0,output:0,cacheRead:0,cacheWrite:0,total:0}};
runtime.registerProvider('memory-fixture', {api:'memory-fixture', apiKey:'cpu-fixture-only',
  models:[modelDefinition], streamSimple(model, context, options) {
    const index = requests.length;
    assert.ok(index < (phase === 'resume' ? 1 : 2), 'Bounded local fake stream calls');
    requests.push(JSON.parse(JSON.stringify(context)));
    fakeCalls.push({api:model.api, provider:model.provider, model:model.id});
    const stream = ai.createAssistantMessageEventStream();
    queueMicrotask(async () => {
      try {
        // This records the actual SDK request projection; there is no network send.
        await options?.onPayload?.({messages:context.messages}, model);
        const tool = phase !== 'resume' && index === 0;
        const block = tool ? {type:'toolCall', id:`persisted-context-${phase}`, name:'shared-memory_context',
          arguments:{caller, ...binding}} : {type:'text',text:'CPU fixture completed.'};
        const final = {role:'assistant', api:model.api, provider:model.provider, model:model.id,
          content:[block], usage:structuredClone(usage), stopReason:tool ? 'toolUse' : 'stop', timestamp:Date.now()};
        const partial = {...final, content:[], stopReason:'pending'};
        stream.push({type:'start', partial:{...partial}});
        if (tool) {
          partial.content = [{...block,arguments:{}}];
          stream.push({type:'toolcall_start',contentIndex:0,partial:{...partial}});
          stream.push({type:'toolcall_delta',contentIndex:0,delta:JSON.stringify(block.arguments),partial:{...partial}});
          partial.content = [block];
          stream.push({type:'toolcall_end',contentIndex:0,toolCall:block,partial:{...partial}});
        } else {
          partial.content = [{type:'text',text:''}];
          stream.push({type:'text_start',contentIndex:0,partial:{...partial}});
          partial.content = [block];
          stream.push({type:'text_delta',contentIndex:0,delta:block.text,partial:{...partial}});
          stream.push({type:'text_end',contentIndex:0,content:block.text,partial:{...partial}});
        }
        stream.push({type:'done',reason:final.stopReason,message:final});
        stream.end(final);
      } catch (error) {
        const message = {role:'assistant',api:model.api,provider:model.provider,model:model.id,content:[],
          usage:structuredClone(usage),stopReason:'error',errorMessage:String(error),timestamp:Date.now()};
        stream.push({type:'error',reason:'error',error:message}); stream.end(message);
      }
    });
    return stream;
  }});
const model = runtime.getModel('memory-fixture','cpu-fixture');
assert.ok(model);
const {session} = await sdk.createAgentSession({cwd:o.project, agentDir:o.agentDir, settingsManager:settings,
  sessionManager:manager, resourceLoader:loader, modelRuntime:runtime, model, noTools:true});
const errors = [];
const lifecycle = [];
session.subscribe(event => lifecycle.push(event.type));
try {
  await session.bindExtensions({mode:'json', onError:e => errors.push(e)});
  if (phase === 'warm') {
    // Installed direct tools are frozen from cached catalog at extension load.
    // Warm only this isolated catalog, then terminate before the disk-backed phases.
    await session.extensionRunner.emitBeforeAgentStart('CPU catalog warmup',undefined,{sections:{}});
    const gateway = session.agent.state.tools.find(t => t.name === 'mcp');
    assert.ok(gateway);
    const result = await gateway.execute('warm-catalog',{server:'shared-memory'},undefined,undefined);
    assert.ok(!result.details?.error);
  } else {
    const before = saved ? fs.readFileSync(saved.sessionFile) : null;
    await session.prompt(phase === 'resume' ? 'Resume only this exact CPU fixture session; do not call a tool.'
      : 'Call the designated fixture context tool once, then finish.');
    fs.writeFileSync(path.join(o.outputDir, `${phase}-requests.json`), JSON.stringify(requests,null,2)+'\n');
    assert.deepEqual(errors, []);
    assert.equal(requests.length, phase === 'resume' ? 1 : 2);
    assert.ok(lifecycle.includes('agent_end'));
    const entries = manager.getEntries();
    const stored = entries.find(e => e.type === 'message' && e.message.role === 'toolResult'
      && e.message.toolName === 'shared-memory_context');
    assert.ok(stored, 'Actual installed MCP result is persisted by the native tool pipeline');
    assert.equal(stored.message.isError, false);
    const packet = JSON.parse(stored.message.content.find(p => p.type === 'text').text);
    assert.equal(packet.status, 'ok');
    assert.equal(packet.caller_context.session_id, manager.getSessionId());
    assert.deepEqual(packet.binding, saved ? {task_mode:'research',query:'airport'} : binding);
    assert.ok(!entries.some(e => e.type === 'custom_message' && e.customType?.startsWith('shared-memory')),
      'Ephemeral shared memory is not persisted as a second native custom message');
    const file = manager.getSessionFile();
    assert.ok(file && fs.existsSync(file));
    const raw = fs.readFileSync(file);
    assert.ok(raw.toString().includes('<shared-memory-context>'), 'Native tool output retains the original full packet');
    if (saved) {
      assert.ok(raw.subarray(0,before.length).equals(before), 'Reopen and projection only append native history');
      const peer = JSON.parse(fs.readFileSync(o.peerReceipt,'utf8'));
      const final = JSON.stringify(requests[0]);
      const memories = requests[0].messages.filter(m => m.role === 'user'
        && JSON.stringify(m.content).includes('<shared-memory-'));
      assert.equal(memories.length,2,'One bootstrap and one task part in the actual SDK request');
      assert.ok(memories.some(m => JSON.stringify(m.content).includes('task_mode: research')),
        'Selected task binding recovers from the persisted installed-name context result');
      assert.equal(final.split('FIXTURE_TASK').length-1,1,'Actual request suppresses stored full-packet duplication');
      assert.ok(final.includes(manager.getSessionId()));
      assert.ok(!final.includes(peer.sessionId) && !final.includes('OTHER_SESSION_QUERY_CANARY'),
        'Neighboring persisted session identity and binding do not leak');
      assert.ok(requests[0].messages.filter(m => m.role === 'toolResult').every(m =>
        !JSON.stringify(m.content).includes('<shared-memory-context>')));
      assert.ok(Buffer.byteLength(JSON.stringify(memories)) <= 8000);
    }
    const receipt = {phase,pid:process.pid,sessionId:manager.getSessionId(),sessionFile:file,
      fakeStreamCalls:fakeCalls, lifecycle, installedTool:'shared-memory_context', actualMcpResult:true,
      paidProviderCalls:0, remoteProviderCalls:0, compaction:'not performed'};
    fs.writeFileSync(phase === 'resume' ? path.join(o.outputDir,'resume-receipt.json')
      : phase === 'peer' ? o.peerReceipt : o.primaryReceipt,
      JSON.stringify(receipt,null,2)+'\n');
    console.log(JSON.stringify({status:'passed',...receipt}));
  }
} finally {
  await session.extensionRunner.emit({type:'session_shutdown',reason:'exit'});
  session.dispose();
}
