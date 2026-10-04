"""Actual installed console entrypoint through two fresh official SDK clients."""
import asyncio
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import pytest
from shared_memory_mcp.core import WORKFLOW_REMINDER

CLI = os.environ.get('SHARED_MEMORY_TEST_CLI','/data/CoordExp/.shared-memory/.venv/bin/shared-memory')
SERVER = str(Path(CLI).with_name('shared-memory-mcp'))


def test_installed_stdio_roundtrip(tmp_path):
    pytest.importorskip('mcp')
    if not Path(CLI).exists():
        pytest.skip('Set SHARED_MEMORY_TEST_CLI to an installed shared-memory entrypoint')
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    project = tmp_path / 'project'
    project.mkdir()
    root = tmp_path / 'memory'
    for command in ([CLI,'--root',str(root),'init'],[CLI,'--root',str(root),'register','--project-id','demo','--project-root',str(project)]):
        result = subprocess.run(command,capture_output=True,text=True)
        assert result.returncode == 0, result.stderr
    context = {'cwd':str(project),'harness':'codex','session_id':'sdk-client','actor':'test'}
    source = {'uri':'file:///research/result.md','locator':'L1'}
    record = {'kind':'hypothesis','title':'机制假设','body':'尚待证据检验。','scope':'project','sources':[source]}
    review = {'reason':'reviewed as a hypothesis','evidence':[source]}
    async def call_sequence():
        params = StdioServerParameters(command=SERVER,args=['--root',str(root)],env={k:v for k,v in os.environ.items() if k != 'PYTHONPATH'},cwd=str(tmp_path))
        async with stdio_client(params) as (read,write):
            async with ClientSession(read,write) as session:
                initialized = await session.initialize()
                assert WORKFLOW_REMINDER in initialized.instructions
                assert 'untrusted data' in initialized.instructions
                assert 'does not establish scientific truth' in initialized.instructions
                packaged_logo = Path(__file__).parents[1]/'src/shared_memory_mcp/assets/logo.svg'
                server_icon = initialized.serverInfo.icons[0]
                assert server_icon.mimeType == 'image/svg+xml'
                assert base64.b64decode(server_icon.src.split(',',1)[1]) == packaged_logo.read_bytes()
                tools = await session.list_tools()
                assert {tool.name for tool in tools.tools} == {'context','search','read','create','approve','update','delete'}
                for tool in tools.tools:
                    assert tool.title and tool.icons == initialized.serverInfo.icons
                    assert 'context' in tool.inputSchema['required']
                descriptions = {tool.name:tool.description.lower() for tool in tools.tools}
                for name, terms in {
                    'context': ('fresh','start/resume','caller'),
                    'search': ('task/topic','duplicates','inactive'),
                    'read': ('full','source','applicability'),
                    'create': ('durable','candidates','source-linked'),
                    'approve': ('main-agent/consolidator','review','scientific truth'),
                    'update': ('successor','old_ids','exact-scope','history'),
                    'delete': ('review','marker','original bytes','history'),
                }.items():
                    assert all(term in descriptions[name] for term in terms), descriptions[name]
                proposed = await session.call_tool('create',{'context':context,'record':record,'idempotency_key':'sdk-propose'})
                assert not proposed.isError, proposed
                payload = proposed.structuredContent or json.loads(proposed.content[0].text)
                identifier = payload['record']['id']
                promoted = await session.call_tool('approve',{'context':context,'id':identifier,'review':review,'idempotency_key':'sdk-promote'})
                assert not promoted.isError, promoted
        async with stdio_client(params) as (read,write):
            async with ClientSession(read,write) as session:
                await session.initialize()
                response = await session.call_tool('read',{'context':context,'ids':[identifier]})
                assert not response.isError, response
                payload = response.structuredContent or json.loads(response.content[0].text)
                assert payload['items'][0]['kind'] == 'hypothesis'
                assert payload['items'][0]['effective_status'] == 'active'
                assert payload['items'][0]['body'] == record['body']
                contextual = await session.call_tool('context',{'context':context,'max_chars':6000})
                assert not contextual.isError, contextual
                assert len((contextual.structuredContent or json.loads(contextual.content[0].text))['text']) <= 6000
                successor = await session.call_tool('create',{'context':context,'record':{**record,'body':'Updated hypothesis; still needs evidence.'},'idempotency_key':'sdk-successor'})
                assert not successor.isError, successor
                successor_id = (successor.structuredContent or json.loads(successor.content[0].text))['record']['id']
                updated = await session.call_tool('update',{'context':context,'id':successor_id,'old_ids':[identifier],'review':review,'idempotency_key':'sdk-update'})
                assert not updated.isError, updated
                assert (updated.structuredContent or json.loads(updated.content[0].text))['record']['supersedes'] == [identifier]
                identifier = successor_id
                deleted = await session.call_tool('delete',{'context':context,'id':identifier,'review':review,'idempotency_key':'sdk-delete'})
                assert not deleted.isError, deleted
                marker = (deleted.structuredContent or json.loads(deleted.content[0].text))['record']
                hidden = await session.call_tool('read',{'context':context,'ids':[identifier,marker['id']]})
                assert (hidden.structuredContent or json.loads(hidden.content[0].text))['items'] == []
                history = await session.call_tool('read',{'context':context,'ids':[identifier,marker['id']],'include_inactive':True})
                assert [r['effective_status'] for r in (history.structuredContent or json.loads(history.content[0].text))['items']] == ['withdrawn','withdrawal']
    asyncio.run(call_sequence())
