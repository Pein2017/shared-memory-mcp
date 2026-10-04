"""Explicit, bounded native Haiku qualification; never part of ordinary pytest."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import tempfile
import time
import uuid

from shared_memory_mcp.core import MemoryStore

SOURCE = Path(__file__).resolve().parents[1]
MODEL = 'claude-haiku-4-5-20251001'
TOOLS = ['memory_context','memory_search','memory_read','memory_propose','memory_promote','memory_supersede']


def unpack(response):
    if response.isError:
        raise RuntimeError('Fixture MCP operation failed')
    return response.structuredContent or json.loads(response.content[0].text)


async def peer_operations(cli, root, project, source, words, identifier=None):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    params = StdioServerParameters(command=str(cli),args=['--root',str(root),'serve'],cwd=str(project),
                                  env={'PATH':os.environ['PATH'],'LANG':'C.UTF-8'})
    records = {}
    for harness in ('codex','pi'):
        context = {'cwd':str(project),'harness':harness,'session_id':'synthetic-sdk-'+harness,'actor':'fixture'}
        async with stdio_client(params) as (reader,writer):
            async with ClientSession(reader,writer) as session:
                await session.initialize()
                if identifier:
                    records[harness] = unpack(await session.call_tool('memory_read',{'context':context,'ids':[identifier]}))['items'][0]
                else:
                    record = {'kind':'observation','title':'Synthetic '+harness+' peer','body':words[harness],
                              'scope':'project','sources':[source]}
                    proposed = unpack(await session.call_tool('memory_propose',{'context':context,'record':record,'idempotency_key':'seed-'+harness}))['record']
                    records[harness] = unpack(await session.call_tool('memory_promote',{'context':context,'id':proposed['id'],
                        'review':{'reason':'Synthetic fixture value supplied by test owner','evidence':[source]},
                        'idempotency_key':'review-'+harness}))['record']
    return records


def native(run, label, command, project, environment, prompt):
    session_id = str(uuid.uuid4())
    argv = [*command,'--session-id',session_id,'--',prompt]
    start = time.monotonic()
    with (run/(label+'.jsonl')).open('w') as out, (run/(label+'.stderr.log')).open('w') as err:
        os.chmod(out.name,0o600); os.chmod(err.name,0o600)
        process = subprocess.Popen(argv,cwd=project,env=environment,stdin=subprocess.DEVNULL,
                                   stdout=out,stderr=err,start_new_session=True)
        deadline = False
        try:
            process.wait(timeout=180)
        except subprocess.TimeoutExpired:
            deadline = True
            os.killpg(process.pid,signal.SIGTERM)
            try: process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL); process.wait()
    events = []
    for line in (run/(label+'.jsonl')).read_text().splitlines():
        try: events.append(json.loads(line))
        except ValueError: continue
    results = [item for item in events if item.get('type')=='result']
    init = next((item for item in events if item.get('type')=='system' and item.get('subtype')=='init'),{})
    tools, models = [], []
    for event in events:
        message = event.get('message',{})
        if message.get('model'): models.append(message['model'])
        for item in message.get('content',[]):
            if item.get('type')=='tool_use': tools.append(item.get('name'))
    final = results[-1] if results else {}
    receipt = {'label':label,'session_id':session_id,'native_session_id':init.get('session_id'),
               'exit_code':process.returncode,'deadline_hit':deadline,'elapsed_seconds':round(time.monotonic()-start,2),
               'requested_model':MODEL,'init_model':init.get('model'),'reported_models':sorted(set(models)),
               'tools':tools,'result_subtype':final.get('subtype'),'is_error':final.get('is_error',True),
               'total_cost_usd':final.get('total_cost_usd'),'usage':final.get('usage'),
               'raw':str(run/(label+'.jsonl'))}
    return receipt, final.get('result',''), init


def actual_startup(args):
    """Consume the installed user hook/MCP config; reject before inference."""
    from native_startup_probe import Provider, run
    project = args.actual_cwd.resolve()
    identifier = str(uuid.uuid4())
    provider = Provider('shared-memory-context','caller_context')
    credentials_path = args.claude_dir/'.credentials.json'
    original_credentials = credentials_path.read_bytes()
    try:
        env = dict(os.environ,CLAUDE_CONFIG_DIR=str(args.claude_dir),ANTHROPIC_BASE_URL=provider.url,
                   ANTHROPIC_API_KEY='synthetic-local-only-key',DISABLE_TELEMETRY='1',DISABLE_ERROR_REPORTING='1')
        for key in ('CLAUDE_CODE_OAUTH_TOKEN','ANTHROPIC_AUTH_TOKEN','CLAUDE_CODE_SIMPLE','CLAUDE_CODE_SAFE_MODE'):
            env.pop(key,None)
        # These per-invocation overrides prevent test writes/account MCP traffic;
        # the owned hook and native shared-memory registration come from user config.
        settings = json.dumps({'autoMemoryEnabled':False,'disableClaudeAiMcp':True})
        command = ['claude','--print','--model',MODEL,'--setting-sources','user','--settings',settings,
                   '--no-session-persistence','--output-format','stream-json','--verbose','--include-hook-events',
                   '--tools','','--session-id',identifier,'--','Synthetic actual startup check. Do not run tools.']
        result = run(command,project,env)
        (SOURCE/'outputs/actual-claude-session.jsonl').write_text(result['stdout'])
        (SOURCE/'outputs/actual-claude-session.stderr.log').write_text(result['stderr'])
        events = []
        for line in result['stdout'].splitlines():
            try: events.append(json.loads(line))
            except ValueError: continue
        init = next((item for item in events if item.get('type')=='system' and item.get('subtype')=='init'),{})
        expected = MemoryStore(args.memory_root).resolve({'cwd':str(project),'harness':'claude','session_id':identifier,'actor':'claude'})
        requests = [r for r in provider.requests if r['path'].endswith('/messages')]
        names = {name.rsplit('__',1)[-1] for name in init.get('tools',[]) if name.startswith('mcp__shared-memory__')}
        matched = [r for r in requests if r['context_wrapper_present'] and any(caller.get('cwd')==str(project)
            and caller.get('project_id')==expected['project_id'] and caller.get('harness')=='claude'
            and caller.get('actor')=='claude' and caller.get('session_id')==identifier for caller in r['caller_contexts'])]
        ok = result['exit_code']==1 and not result['deadline_hit'] and init.get('session_id')==identifier
        ok = ok and init.get('model')==MODEL and set(TOOLS)<=names and bool(matched)
        ok = ok and all(r['model']==MODEL and not r['effort_fields_present'] for r in requests)
        ok = ok and credentials_path.read_bytes()==original_credentials
        receipt = {'status':'pass' if ok else 'failed','configuration':'actual user config','model':MODEL,
                   'native_session_id':init.get('session_id'),'scope':expected,'exit_code':result['exit_code'],
                   'exit_reason':'expected local HTTP400 rejection','deadline_hit':result['deadline_hit'],
                   'six_native_tools':sorted(names),'provider_requests':requests,
                   'credentials_unchanged':credentials_path.read_bytes()==original_credentials,
                   'model_inference_calls':0,'real_provider_requests':0,
                   'per_invocation_overrides':{'autoMemoryEnabled':False,'disableClaudeAiMcp':True}}
        (SOURCE/'outputs/actual-claude-session.json').write_text(json.dumps(receipt,indent=2)+'\n')
        print(json.dumps({key:receipt[key] for key in ('status','configuration','model','exit_code','deadline_hit','six_native_tools','credentials_unchanged')}))
        if not ok: raise RuntimeError('Actual native startup boundary failed; inspect sanitized receipt')
        return 0
    finally:
        provider.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--live',action='store_true',help='Explicitly authorize the two native Haiku model sessions')
    parser.add_argument('--actual-startup',action='store_true',help='Verify actual configuration against local HTTP400 without inference')
    parser.add_argument('--actual-cwd',type=Path,default=Path('/data/CoordExp'))
    parser.add_argument('--memory-root',type=Path,default=Path('/data/CoordExp/.shared-memory'))
    parser.add_argument('--cli',type=Path,default=Path('/data/CoordExp/.shared-memory/.venv/bin/shared-memory'))
    parser.add_argument('--claude-dir',type=Path,default=os.environ.get('CLAUDE_CONFIG_DIR'))
    args = parser.parse_args()
    if not args.claude_dir: parser.error('Supply the existing Claude auth directory')
    if args.actual_startup:
        if args.live: parser.error('Choose either --live or --actual-startup')
        return actual_startup(args)
    if not args.live: parser.error('Paid/provider execution requires explicit --live')
    credentials = json.loads((args.claude_dir/'.credentials.json').read_text())['claudeAiOauth']
    if credentials.get('expiresAt',0) <= time.time()*1000+300000:
        raise RuntimeError('Existing access token is expired or near expiry; no refresh copy or automatic retry')
    token = credentials['accessToken']
    run = SOURCE/'outputs'/('claude-haiku-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'-'+uuid.uuid4().hex[:6])
    run.mkdir(mode=0o700)
    report = {'status':'running','model':MODEL,'run':str(run),'sessions':[],
              'paid_session_limit':2,'per_session_budget_usd':1,'peer_clients':'synthetic official-SDK fixtures',
              'refresh_token_copied':False,'actual_native_memory_written':False}
    def save():
        (run/'results.json').write_text(json.dumps(report,indent=2)+'\n')
        (SOURCE/'outputs/claude-haiku-results.json').write_text(json.dumps(report,indent=2)+'\n')
    save()
    try:
        with tempfile.TemporaryDirectory(prefix='shared-memory-haiku-') as scratch:
            project = Path(scratch)
            subprocess.run(['git','init','-q',str(project)],check=True,capture_output=True)
            words = {name:name.upper()+'_'+uuid.uuid4().hex for name in ('startup','codex','pi','claude')}
            owner = project/'fixture-owner.md'
            owner.write_text('Synthetic integration fixture; not research facts.\n'+'\n'.join(words.values())+'\n')
            root = run/'memory'; store = MemoryStore(root); store.init(); store.register('haiku-qualification',[str(project)])
            source = {'uri':owner.as_uri()}
            seed_context = {'cwd':str(project),'harness':'codex','session_id':'synthetic-bootstrap','actor':'fixture'}
            bootstrap = store.propose(seed_context,{'kind':'invariant','title':'Startup-only sentinel','body':words['startup'],
                'scope':'project','sources':[source]},'seed-startup')['record']
            store.promote(seed_context,bootstrap['id'],{'reason':'Synthetic fixture','evidence':[source]},'review-startup')
            peers = asyncio.run(peer_operations(args.cli,root,project,source,words))
            home = run/'native-config';home.mkdir(mode=0o700)
            settings = run/'settings.json'; mcp = run/'mcp.json'
            hook = shlex.join([str(args.cli),'--root',str(root),'hook','--harness','claude'])
            settings.write_text(json.dumps({'autoMemoryEnabled':False,'disableClaudeAiMcp':True,
                'hooks':{'SessionStart':[{'matcher':'startup|resume|clear|compact',
                    'hooks':[{'type':'command','command':hook,'timeout':15}]}]}}))
            mcp.write_text(json.dumps({'mcpServers':{'shared-memory':{'type':'stdio','command':str(args.cli),
                'args':['--root',str(root),'serve']}}}))
            env = dict(os.environ,CLAUDE_CONFIG_DIR=str(home),CLAUDE_CODE_OAUTH_TOKEN=token,
                       DISABLE_TELEMETRY='1',DISABLE_ERROR_REPORTING='1',DISABLE_AUTOUPDATER='1')
            for key in ('ANTHROPIC_API_KEY','ANTHROPIC_AUTH_TOKEN','ANTHROPIC_BASE_URL','CLAUDE_CODE_SIMPLE','CLAUDE_CODE_SAFE_MODE'):
                env.pop(key,None)
            allowed = ','.join('mcp__'+name+'__*' for name in ('shared-memory','shared_memory'))
            command = ['claude','--print','--model',MODEL,'--setting-sources','','--settings',str(settings),
                '--strict-mcp-config','--mcp-config',str(mcp),'--no-session-persistence',
                '--output-format','stream-json','--verbose','--include-hook-events','--tools','',
                '--permission-mode','dontAsk','--allowedTools',allowed,'--max-budget-usd','1']
            report.update(fixture_project=str(project),store=str(root),bootstrap_id=bootstrap['id'],
                          peer_ids={name:r['id'] for name,r in peers.items()},command=command)
            save()
            guidance = ('This is a bounded synthetic shared-memory qualification. Use only the shared-memory MCP tools. '
                'Use the exact caller_context supplied by your startup <shared-memory-context>, including actual session_id. '
                'Copy STARTUP_<nonce> from that already injected memory; never call memory_context or memory_search to obtain it. '
                'Only read the explicitly supplied peer IDs. Do not use built-in tools or create unrelated records. ')
            prompt = guidance+'Read both peer IDs '+json.dumps([r['id'] for r in peers.values()])+'. Then propose one project-scope observation, title Claude native Haiku qualification, exact body '+words['claude']+'. Source uri '+owner.as_uri()+'. Use proposal key haiku-capture. Explicitly promote that candidate using key haiku-review, reason Synthetic value checked against this supplied test source, evidence the same URI. Return JSON with startup_word, both peer bodies, and created_record_id.'
            receipt, text, init = native(run,'writer',command,project,env,prompt)
            report['sessions'].append(receipt);save()
            assert receipt['exit_code']==0 and not receipt['deadline_hit'] and not receipt['is_error'], receipt
            assert receipt['native_session_id']==receipt['session_id'] and receipt['init_model']==MODEL, receipt
            assert set(receipt['reported_models'])=={MODEL}, receipt
            assert words['startup'] in text and all(words[name] in text for name in ('codex','pi')), 'Startup/peer values missing'
            used = {name.rsplit('__',1)[-1] for name in receipt['tools']}
            assert used=={'memory_read','memory_propose','memory_promote'}, receipt
            context = {'cwd':str(project),'harness':'claude','session_id':'lead-readback','actor':'lead'}
            captured = next(item for item in store.search(context,'Claude native Haiku qualification')['items'] if item.get('body')==words['claude'])
            assert captured['effective_status']=='active' and captured['provenance']['harness']=='claude'
            assert captured['provenance']['session_id']==receipt['session_id'] and captured['sources']==[source]
            readback = asyncio.run(peer_operations(args.cli,root,project,source,words,captured['id']))
            assert all(item['body']==words['claude'] and item['id']==captured['id'] for item in readback.values())
            report.update(claude_record_id=captured['id'],candidate_review=True,actual_session_provenance=True,
                          peer_sdk_readback=True,startup_recall=True)
            save()
            prompt = guidance+'Read only Claude record ID '+captured['id']+'. Do not write anything. Return JSON with startup_word, the recalled Claude body, and the record_id.'
            receipt, text, init = native(run,'fresh-reader',command,project,env,prompt)
            report['sessions'].append(receipt);save()
            assert receipt['exit_code']==0 and not receipt['deadline_hit'] and not receipt['is_error'],receipt
            assert receipt['native_session_id']==receipt['session_id'] and receipt['init_model']==MODEL,receipt
            assert set(receipt['reported_models'])=={MODEL} and words['startup'] in text and words['claude'] in text,receipt
            assert {name.rsplit('__',1)[-1] for name in receipt['tools']}=={'memory_read'},receipt
            assert captured['id'] in text and store.doctor()['projects']['haiku-qualification']==4
            assert not (home/'.credentials.json').exists(), 'Native fixture unexpectedly persisted credentials'
            report.update(status='pass',fresh_session_recall=True,real_native_sessions=2,
                          total_cost_usd=sum(item.get('total_cost_usd') or 0 for item in report['sessions']))
            save();print(json.dumps({key:report[key] for key in ('status','model','real_native_sessions','startup_recall','peer_sdk_readback','candidate_review','actual_session_provenance','fresh_session_recall','total_cost_usd','run')}))
            return 0
    except Exception as exc:
        report.update(status='failed',error_type=type(exc).__name__,diagnostic=str(exc)[:1600],
                      no_automatic_relaunch=True)
        save();raise


if __name__=='__main__':
    raise SystemExit(main())
