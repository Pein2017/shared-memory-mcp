"""Isolated native startup consumers, with local rejection before model inference.

The HTTP stub retains booleans/tool names only, never prompts or auth headers.
Claude/Codex are expected to exit nonzero after its deterministic HTTP 400.
"""
from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import select
import shlex
import shutil
import subprocess
import tempfile
import threading
import time
import uuid
from shared_memory_mcp.core import WORKFLOW_REMINDER

PACKAGE = Path(__file__).resolve().parents[1]
CLI = '/data/CoordExp/.shared-memory/.venv/bin/shared-memory'
RUNTIME = str(Path(CLI).with_name('python'))
PI_SDK = '/root/.nvm/versions/node/v22.22.0/lib/node_modules/@earendil-works/pi-coding-agent'
HELPER = PACKAGE / 'tests/native/startup_helpers.py'
TOOLS = ['context','search','read','create','approve','update','delete','capture','curate']
CLAUDE_MODEL = 'claude-haiku-4-5-20251001'


def environment(home):
    # Do not forward actual provider credentials, proxies, hook/plugin config, or auth homes.
    return {'PATH':os.environ['PATH'],'LANG':'C.UTF-8',
            'NO_PROXY':'127.0.0.1,localhost','no_proxy':'127.0.0.1,localhost',
            'TMPDIR':str(home),'DISABLE_TELEMETRY':'1','DISABLE_ERROR_REPORTING':'1',
            'DISABLE_AUTOUPDATER':'1','CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC':'1'}


def run(command, cwd, env, timeout=45):
    started = time.monotonic()
    process = subprocess.Popen(command,cwd=cwd,env=env,stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
    deadline_hit = False
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        deadline_hit = True
        import signal
        os.killpg(process.pid,signal.SIGTERM)
        try:
            stdout,stderr = process.communicate(timeout=3)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGKILL)
            stdout,stderr = process.communicate()
    return {'exit_code':process.returncode,'deadline_hit':deadline_hit,
            'elapsed_seconds':round(time.monotonic()-started,3),'stdout':stdout,'stderr':stderr}


def require(command, cwd, env):
    result = run(command,cwd,env,20)
    if result['exit_code']:
        raise RuntimeError(f'Fixture command failed ({result["exit_code"]}): {command[:2]}: {result["stderr"][:600]}')
    return result


class Provider:
    def __init__(self, sentinel, identifier):
        self.requests = []
        self.sentinel = sentinel
        self.identifier = identifier
        owner = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*_args):
                pass
            def do_GET(self):
                self.reject()
            def do_POST(self):
                size = int(self.headers.get('Content-Length','0'))
                raw = self.rfile.read(min(size,4_194_304)).decode('utf-8','replace')
                try:
                    body = json.loads(raw)
                except ValueError:
                    body = {}
                tools, tool_names, tool_types, schema_tools = [], [], [], []
                def walk(value, namespace=None):
                    if isinstance(value,dict):
                        name = value.get('name')
                        kind = value.get('type')
                        if kind == 'namespace':
                            namespace = name if isinstance(name,str) else ''
                        if isinstance(name,str):
                            tool_names.append(name)
                        memory_namespaces = ('mcp__shared_memory','mcp__shared-memory')
                        qualified = None
                        if isinstance(name,str) and name.rsplit('__',1)[0] in memory_namespaces and name.rsplit('__',1)[-1] in TOOLS:
                            qualified = name
                        if kind == 'function' and namespace in memory_namespaces and name in TOOLS:
                            qualified = namespace+'__'+name
                        if qualified and (namespace is None or qualified.rsplit('__',1)[0] == namespace):
                            tools.append(qualified)
                            schema = value.get('input_schema',value.get('parameters'))
                            if isinstance(schema,dict) and schema.get('type')=='object' and 'context' in schema.get('properties',{}):
                                schema_tools.append(qualified)
                        if isinstance(kind,str):
                            tool_types.append(kind)
                        for nested in value.values(): walk(nested,namespace)
                    elif isinstance(value,list):
                        for nested in value: walk(nested,namespace)
                walk(body.get('tools',[]))
                additional = [item for item in body.get('input',[]) if isinstance(item,dict) and item.get('type')=='additional_tools']
                for item in additional:
                    walk(item.get('tools',[]))
                callers = []
                workflow_reminder_present = False
                def find_callers(value):
                    nonlocal workflow_reminder_present
                    if isinstance(value,dict):
                        if value.get('type')=='additional_tools':
                            return
                        for nested in value.values(): find_callers(nested)
                    elif isinstance(value,list):
                        for nested in value: find_callers(nested)
                    elif isinstance(value,str):
                        for snapshot in value.split(WORKFLOW_REMINDER+'\n<shared-memory-context>')[1:]:
                            records = snapshot.split('</shared-memory-context>',1)[0]
                            if owner.sentinel in records and owner.identifier in records:
                                workflow_reminder_present = True
                        for match in re.finditer(r'caller_context: (\{[^\n]+\})',value):
                            try: caller = json.loads(match.group(1))
                            except ValueError: continue
                            if all(key in caller for key in ('cwd','harness','session_id','actor')):
                                callers.append({key:caller[key] for key in ('cwd','project_id','harness','session_id','actor','task_id') if key in caller})
                find_callers(body.get('input',[]))
                find_callers(body.get('messages',[]))
                owner.requests.append({'method':'POST','path':self.path.split('?')[0],
                    'model':body.get('model'), 'effort_fields_present':any(key in raw for key in ('"effort"','"reasoning_effort"')),
                    'body_bytes':size,'sentinel_present':owner.sentinel in raw,
                    'record_id_present':owner.identifier in raw,'context_wrapper_present':'shared-memory-context' in raw,
                    'workflow_reminder_present':workflow_reminder_present,
                    'memory_tools':sorted(set(tools)), 'tool_names':sorted(set(tool_names)),
                    'memory_schema_tools':sorted(set(schema_tools)),
                    'tool_types':sorted(set(tool_types)),
                    'memory_names_in_request':[name for name in TOOLS if name in raw],
                    'json_fields':sorted(body) if isinstance(body,dict) else [],
                    'tools_count':len(body.get('tools',[])) if isinstance(body,dict) else 0,
                    'additional_tools_entries':len(additional),
                    'all_tools_catalog_present':'ALL_TOOLS' in raw,
                    'tool_search_present':any('tool_search' in name for name in tool_names),
                    'caller_contexts':callers[-10:],
                    'content_encoding':self.headers.get('Content-Encoding'),
                    'response_status':400})
                self.reject()
            def reject(self):
                payload = json.dumps({'type':'error','error':{'type':'invalid_request_error',
                    'message':'Synthetic startup consumer probe ends before model inference.'}}).encode()
                self.send_response(400)
                self.send_header('Content-Type','application/json')
                self.send_header('Content-Length',str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)
        self.server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.thread = threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()

    @property
    def url(self):
        return f'http://127.0.0.1:{self.server.server_port}'

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(2)


def codex_trust(binary, home, project, env):
    """Use native discovery hash, then persist trust in the isolated config only."""
    process = subprocess.Popen([binary,'app-server','--listen','stdio://'],cwd=project,env=env,
        stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,bufsize=1)
    def exchange(identifier,method,params):
        process.stdin.write(json.dumps({'id':identifier,'method':method,'params':params})+'\n')
        process.stdin.flush()
        deadline = time.monotonic()+12
        while time.monotonic()<deadline:
            ready,_,_ = select.select([process.stdout],[],[],max(0,deadline-time.monotonic()))
            if not ready: break
            raw = process.stdout.readline()
            if not raw: break
            response = json.loads(raw)
            if response.get('id') == identifier:
                if 'error' in response: raise RuntimeError(str(response['error']))
                return response['result']
        raise RuntimeError(f'Native {method} discovery deadline')
    try:
        exchange(1,'initialize',{'clientInfo':{'name':'native-startup-probe','version':'1'},
                                 'capabilities':{'experimentalApi':True}})
        process.stdin.write(json.dumps({'method':'initialized','params':{}})+'\n')
        process.stdin.flush()
        result = exchange(2,'hooks/list',{'cwds':[str(project)]})
        hooks = [hook for entry in result['data'] for hook in entry['hooks']
                 if hook['eventName']=='sessionStart' and hook['sourcePath']==str(home/'hooks.json')]
        if len(hooks)!=1:
            raise RuntimeError(f'Expected exactly one isolated hook, got {len(hooks)}')
        hook = hooks[0]
        exchange(3,'config/batchWrite',{'edits':[{'keyPath':'hooks.state',
            'value':{hook['key']:{'trusted_hash':hook['currentHash'],'enabled':True}},'mergeStrategy':'upsert'}],
            'filePath':None,'expectedVersion':None,'reloadUserConfig':True})
        verified = exchange(4,'hooks/list',{'cwds':[str(project)]})
        trusted = [entry for group in verified['data'] for entry in group['hooks']
                   if entry['key']==hook['key']]
        if len(trusted)!=1 or trusted[0]['trustStatus']!='trusted':
            raise RuntimeError('Native isolated hook trust did not verify')
        return {'key':hook['key'],'hash':hook['currentHash'],'discovery_trust':hook['trustStatus'],
                'isolated_trust_persisted':True}
    finally:
        process.terminate()
        try: process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill(); process.wait()


def summarize(result, requests, receipt, harness, cwd):
    events = []
    for raw in result.pop('stdout').splitlines():
        try: entry = json.loads(raw)
        except ValueError: continue
        events.append({key:entry[key] for key in ('type','subtype','hook_event','hook_name','exit_code','is_error') if key in entry})
    stderr = result.pop('stderr')
    result['stderr_summary'] = '\n'.join(line[:300] for line in stderr.splitlines()
        if any(word in line.lower() for word in ('error','failed','hook','mcp','400','auth')))[:2400]
    result.update(events=events[-30:],provider_requests=requests,
                  native_hook_receipts=[json.loads(raw) for raw in receipt.read_text().splitlines()] if receipt.exists() else [],
                  real_provider_requests=0,model_inference_calls=0)
    matching = [request for request in requests if request['sentinel_present'] and request['record_id_present']
                and request.get('workflow_reminder_present',False)]
    names = {name.rsplit('__',1)[-1] for request in matching for name in request['memory_tools']}
    verified_receipts = [entry for entry in result['native_hook_receipts'] if entry['exit_code']==0 and entry['sentinel_present'] and entry['record_id_present']
                     and entry['text_chars']<=6000 and entry.get('hook_event_name')=='SessionStart'
                     and entry.get('source')=='startup' and entry.get('session_id')
                     and entry.get('cwd')==str(cwd)]
    native_ok = True
    if harness=='claude':
        schema_names = {name.rsplit('__',1)[-1] for request in matching for name in request['memory_schema_tools']}
        native_ok = (result['exit_code']==1 and set(TOOLS)<=schema_names
                     and all(request['model']==CLAUDE_MODEL and not request['effort_fields_present']
                         and any(caller.get('cwd')==entry['cwd'] and caller.get('session_id')==entry['session_id']
                             and caller.get('harness')==harness and caller.get('actor')==harness
                             for caller in request['caller_contexts'] for entry in verified_receipts) for request in matching))
    result['status'] = 'pass' if matching and set(TOOLS)<=names and verified_receipts and native_ok and not result['deadline_hit'] else 'limit'
    result['consumer_boundary'] = 'installed native hook and serialized provider request; local HTTP400 rejection'
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--harness',choices=['all','pi','codex','claude'],default='all')
    args = parser.parse_args()
    output = PACKAGE/'outputs'
    output.mkdir(exist_ok=True)
    run_root = Path(tempfile.mkdtemp(prefix='native-startup-',dir=output))
    project, store = run_root/'project', run_root/'memory'
    project.mkdir()
    env = environment(run_root)
    for command in (['git','init','-q',str(project)],['git','-C',str(project),'config','user.name','Native Fixture'],
                    ['git','-C',str(project),'config','user.email','fixture@example.invalid']):
        require(command,run_root,env)
    (project/'fixture-owner.md').write_text('Synthetic fixture only. No scientific claim.\n')
    require(['git','-C',str(project),'add','fixture-owner.md'],run_root,env)
    require(['git','-C',str(project),'commit','-qm','Synthetic native startup fixture'],run_root,env)
    worktree = run_root/'linked-worktree'
    require(['git','-C',str(project),'worktree','add','--detach','-q',str(worktree)],run_root,env)
    for command in ([CLI,'--root',str(store),'init'],[CLI,'--root',str(store),'register','--project-id','native-fixture','--project-root',str(project)]):
        require(command,run_root,env)
    sentinel = 'NATIVE_MEMORY_'+uuid.uuid4().hex
    seed_options = {'cli':CLI,'root':str(store),'project':str(project),'sentinel':sentinel}
    seed_path = run_root/'seed.json'
    seed_path.write_text(json.dumps(seed_options))
    seeded = json.loads(require([RUNTIME,str(HELPER),'seed',str(seed_path)],run_root,env)['stdout'])
    report = {'run_root':str(run_root),'actual_cli':CLI,'project':str(project),'linked_worktree':str(worktree),
              'store':str(store),'sentinel':sentinel,'record_id':seeded['id'],'seed':seeded,'harnesses':{},
              'supported_harnesses':['codex','pi','claude'],'historical_harnesses':{}}
    previous_path = output/'native-startup-probe.json'
    if args.harness!='all' and previous_path.exists():
        previous = json.loads(previous_path.read_text())
        for name, result in previous.get('harnesses',{}).items():
            if name==args.harness: continue
            retained = {**result,'evidence_report':str(Path(previous['run_root'])/'selected-results.json'),
                        'fixture':{key:previous[key] for key in ('store','linked_worktree','record_id','sentinel')}}
            if retained.get('deadline_hit'):
                retained['consumer_status'] = retained['status']
                retained['status'] = 'limit'
            retained['current_activation'] = 'historical_evidence_only'
            report['historical_harnesses'][name] = retained
        for name,result in previous.get('historical_harnesses',{}).items():
            if name!=args.harness and name not in report['historical_harnesses']:
                report['historical_harnesses'][name] = result
    def save():
        text = json.dumps(report,indent=2)+'\n'
        (run_root/'selected-results.json').write_text(text)
        (output/'native-startup-probe.json').write_text(text)
        for name,result in report['harnesses'].items():
            (run_root/(name+'-selected.log')).write_text(json.dumps(result,indent=2)+'\n')
    save()
    if args.harness in ('all','pi'):
        options = {**seed_options,'id':seeded['id'],'project':str(worktree),'agentDir':str(run_root/'pi'),
                   'sdkRoot':PI_SDK,'extension':str(PACKAGE/'adapters/pi/shared-memory.ts')}
        path = run_root/'pi-options.json'; path.write_text(json.dumps(options))
        result = run(['node',str(PACKAGE/'tests/native/pi_real_context.mjs'),str(path)],run_root,env)
        try: selected = json.loads(result.pop('stdout').splitlines()[-1])
        except (ValueError,IndexError): selected = {'status':'limit'}
        selected.update({key:value for key,value in result.items() if key != 'stderr'})
        selected['stderr_summary'] = result['stderr'][-1500:]
        selected['consumer_status'] = selected['status']
        if result['exit_code'] or result['deadline_hit']:
            selected['status'] = 'limit'
        report['harnesses']['pi'] = selected; save()
    for harness in ('codex','claude'):
        if args.harness not in ('all',harness): continue
        home = run_root/harness; home.mkdir()
        native_env = environment(home)
        receipt = run_root/(harness+'-hook-receipt.jsonl')
        options = {**seed_options,'id':seeded['id'],'harness':harness,'receipt':str(receipt)}
        path = run_root/(harness+'-hook-options.json'); path.write_text(json.dumps(options))
        hook_command = shlex.join([RUNTIME,str(HELPER),'hook',str(path)])
        provider = Provider(sentinel,seeded['id'])
        try:
            binary = shutil.which(harness)
            if not binary: raise RuntimeError('Native CLI unavailable')
            if harness == 'claude':
                native_env.update(CLAUDE_CONFIG_DIR=str(home),ANTHROPIC_BASE_URL=provider.url,
                                  ANTHROPIC_API_KEY='synthetic-local-only-key')
                settings = home/'settings.json'
                settings.write_text(json.dumps({'autoMemoryEnabled':False,'disableClaudeAiMcp':True,
                    'hooks':{'SessionStart':[{'matcher':'startup|resume|clear|compact',
                    'hooks':[{'type':'command','command':hook_command,'timeout':20}]}]}}))
                mcp = home/'mcp.json'; mcp.write_text(json.dumps({'mcpServers':{'shared-memory':{
                    'type':'stdio','command':CLI,'args':['--root',str(store),'serve']}}}))
                command = [binary,'--print','Synthetic startup probe. Do not run tools.','--model',CLAUDE_MODEL,
                    '--setting-sources','user','--settings',str(settings),'--strict-mcp-config','--mcp-config',str(mcp),
                    '--tools','','--disable-slash-commands','--no-session-persistence','--output-format','stream-json',
                    '--verbose','--include-hook-events']
            else:
                native_env['CODEX_HOME'] = str(home)
                config = f'''model = "gpt-5.4"
model_provider = "native_stub"
approval_policy = "never"
sandbox_mode = "read-only"
[features]
hooks = true
plugin_hooks = true
[model_providers.native_stub]
name = "Synthetic Local Startup Probe"
base_url = {json.dumps(provider.url+'/v1')}
wire_api = "responses"
requires_openai_auth = false
supports_websockets = false
request_max_retries = 0
stream_max_retries = 0
[mcp_servers.shared_memory]
command = {json.dumps(CLI)}
args = ["--root", {json.dumps(str(store))}, "serve"]
startup_timeout_sec = 15
tool_timeout_sec = 15
'''
                (home/'config.toml').write_text(config)
                (home/'hooks.json').write_text(json.dumps({'hooks':{'SessionStart':[{'matcher':'startup|resume|clear|compact',
                    'hooks':[{'type':'command','command':hook_command,'timeout':20}]}]}}))
                report['codex_hook_trust'] = codex_trust(binary,home,worktree,native_env)
                command = [binary,'exec','--json','--ephemeral','--ignore-rules','--cd',str(worktree),
                           'Synthetic startup probe. Do not run tools.']
            result = run(command,worktree,native_env)
            for stream in ('stdout','stderr'):
                raw_path = run_root/(harness+'-'+stream+'.log')
                raw_path.write_text(result[stream]); raw_path.chmod(0o600)
            report['harnesses'][harness] = summarize(result,provider.requests,receipt,harness,worktree)
            report['harnesses'][harness]['native_binary'] = binary
            if harness=='claude':
                report['harnesses'][harness]['model'] = CLAUDE_MODEL
        except Exception as exc:
            report['harnesses'][harness] = {'status':'limit','error_type':type(exc).__name__,
                                          'diagnostic':str(exc)[:800],'provider_requests':provider.requests}
        finally:
            provider.close(); save()
    print(json.dumps({'report':str(output/'native-startup-probe.json'),
        'run_root':str(run_root),'harnesses':{name:{key:result.get(key) for key in ('status','exit_code','deadline_hit')}
                                           for name,result in report['harnesses'].items()}}))
    return 0 if all(result['status']=='pass' for result in report['harnesses'].values()) else 1


if __name__ == '__main__':
    raise SystemExit(main())
