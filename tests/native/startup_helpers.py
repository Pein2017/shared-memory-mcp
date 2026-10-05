"""Test-only installed MCP seeding and native hook receipts."""
import asyncio
import json
from pathlib import Path
import subprocess
import sys


def unpack(result):
    if result.isError:
        raise RuntimeError('MCP fixture operation failed')
    return result.structuredContent or json.loads(result.content[0].text)


async def seed(options):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    context = {'cwd':options['project'],'harness':'codex','session_id':'native-fixture-seed','actor':'fixture'}
    source = {'uri':Path(options['project'],'fixture-owner.md').as_uri()}
    params = StdioServerParameters(command=options['cli'],args=['--root',options['root'],'serve'],cwd=options['project'])
    async with stdio_client(params) as (reader,writer):
        async with ClientSession(reader,writer) as session:
            await session.initialize()
            proposed = unpack(await session.call_tool('create',{'context':context,
                'record':{'kind':'invariant','title':'Synthetic startup sentinel','body':options['sentinel'],
                          'scope':'project','sources':[source]},'idempotency_key':'native-propose'}))
            identifier = proposed['record']['id']
            unpack(await session.call_tool('approve',{'context':context,'id':identifier,
                'review':{'reason':'Synthetic test fixture only','evidence':[source]},'idempotency_key':'native-promote'}))
            routing = Path(options['root']) / 'routing'
            routing.mkdir(exist_ok=True)
            (routing / (proposed['record']['project_id'] + '.json')).write_text(json.dumps({
                'version': 1, 'description': 'Synthetic navigation fixture, not scientific evidence.',
                'topics': [{'id': 'fixture', 'title': options['sentinel'], 'when': 'During this isolated test.',
                            'sources': [source], 'memory_ids': [identifier]}]}))
            nav = unpack(await session.call_tool('context',{'context':context}))
            assert nav['records_not_loaded'] and nav['items'] == [] and 'text' not in nav
            cli_context = subprocess.run([options['cli'],'--root',options['root'],'context',
                                         '--cwd',context['cwd'],'--harness',context['harness'],
                                         '--session-id',context['session_id'],'--actor',context['actor']],
                                         capture_output=True,text=True,check=True)
            recalled = json.loads(cli_context.stdout)
            tools = await session.list_tools()
    print(json.dumps({'status':'ok','id':identifier,'text_chars':len(recalled['text']),
                      'sentinel_present':options['sentinel'] in recalled['text'],
                      'tools':[tool.name for tool in tools.tools]}))


def hook(options):
    raw = sys.stdin.read()
    event = json.loads(raw)
    result = subprocess.run([options['cli'],'--root',options['root'],'hook','--harness',options['harness']],
                            input=raw,capture_output=True,text=True,timeout=15)
    output = json.loads(result.stdout)
    text = output.get('hookSpecificOutput',{}).get('additionalContext','')
    receipt = {key:event.get(key) for key in ('cwd','session_id','hook_event_name','source')}
    receipt.update(exit_code=result.returncode,text_chars=len(text),
                   sentinel_present=options['sentinel'] in text,record_id_present=options['id'] in text)
    with open(options['receipt'],'a') as stream:
        stream.write(json.dumps(receipt)+'\n')
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    return result.returncode


if __name__ == '__main__':
    mode, options_path = sys.argv[1:]
    options = json.loads(Path(options_path).read_text())
    if mode == 'seed':
        asyncio.run(seed(options))
    else:
        raise SystemExit(hook(options))
