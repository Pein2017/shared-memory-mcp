"""Actual installed console entrypoint through two fresh official SDK clients."""
import asyncio
import json
import os
from pathlib import Path
import shutil
import subprocess
import pytest

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
                await session.initialize()
                tools = await session.list_tools()
                assert {tool.name for tool in tools.tools} == {'memory_context','memory_search','memory_read','memory_propose','memory_promote','memory_supersede'}
                proposed = await session.call_tool('memory_propose',{'context':context,'record':record,'idempotency_key':'sdk-propose'})
                assert not proposed.isError, proposed
                payload = proposed.structuredContent or json.loads(proposed.content[0].text)
                identifier = payload['record']['id']
                promoted = await session.call_tool('memory_promote',{'context':context,'id':identifier,'review':review,'idempotency_key':'sdk-promote'})
                assert not promoted.isError, promoted
        async with stdio_client(params) as (read,write):
            async with ClientSession(read,write) as session:
                await session.initialize()
                response = await session.call_tool('memory_read',{'context':context,'ids':[identifier]})
                assert not response.isError, response
                payload = response.structuredContent or json.loads(response.content[0].text)
                assert payload['items'][0]['kind'] == 'hypothesis'
                assert payload['items'][0]['effective_status'] == 'active'
                assert payload['items'][0]['body'] == record['body']
                contextual = await session.call_tool('memory_context',{'context':context,'max_chars':6000})
                assert not contextual.isError, contextual
                assert len((contextual.structuredContent or json.loads(contextual.content[0].text))['text']) <= 6000
    asyncio.run(call_sequence())
