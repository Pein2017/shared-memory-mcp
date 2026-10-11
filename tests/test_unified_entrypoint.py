"""Actual stdio MCP, one registration, disposable roots and no inference calls."""
import asyncio
import json
import os
from pathlib import Path
import sys

import pytest

from shared_memory_mcp.cli import call_operation
from shared_memory_mcp.core import MemoryError
from dreaming_helpers import environment
from test_collections import preference, review, live


def unpack(result):
    assert not result.isError, result
    assert result.structuredContent is None, 'Do not expose the full packet twice'
    texts = [part.text for part in result.content if part.type == 'text']
    assert len(texts) == 1
    return json.loads(texts[0])


def test_one_real_stdio_connection_recalls_corrects_and_starts_bounded_review(tmp_path):
    _, store, _, caller, _, owner, _ = environment(tmp_path)
    async def run():
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        params = StdioServerParameters(command=sys.executable,
            args=['-B', '-m', 'shared_memory_mcp.server', '--root', str(store.root)],
            env={'PATH': os.environ.get('PATH', ''), 'PYTHONPATH': str(Path(__file__).parents[1] / 'src'),
                 'PYTHONDONTWRITEBYTECODE': '1'})
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as client:
                await client.initialize()
                names = {tool.name for tool in (await client.list_tools()).tools}
                assert {'context', 'capture', 'update', 'delete', 'run_start', 'run_changes', 'draft_publish', 'overview_read'} <= names
                record = preference(owner)
                made = unpack(await client.call_tool('capture', {'context': caller, 'collection': 'collaboration',
                    'record': record, 'idempotency_key': 'stdio-current-pref', 'review': review(record), 'live_correction': live()}))
                response = await client.call_tool('context', {'context': caller, 'task_mode': 'general'})
                packet = unpack(response)
                assert '/new/project-path' in packet['text'] and packet['caller_context']['session_id'] == caller['session_id']
                assert len(response.model_dump_json(by_alias=True, exclude_none=True).encode()) <= 8000
                bad = await client.call_tool('context', {'context': {**caller, 'publisher': True}})
                assert bad.isError
                forbidden = await client.call_tool('run_start', {'context': caller, 'profile': 'fixture',
                    'review_objective': {'id': 'stdio', 'question': 'Review the fixture owners.'}})
                assert forbidden.isError
                started = unpack(await client.call_tool('run_start', {'context': caller,
                    'review_objective': {'id': 'stdio', 'question': 'Review the fixture owners.'}}))
                assert started['status'] == 'created'
                material = unpack(await client.call_tool('run_materials', {'context': caller, 'run_id': started['run_id']}))
                statuses = {e['key']: 'no-signal' for source in material['sources'].values() for e in source['events']}
                statuses.update({item['ref']: 'no-signal' for item in started['objective_progress']['ready_memory']})
                unpack(await client.call_tool('coverage_mark', {'context': caller, 'run_id': started['run_id'], 'generation': started['generation'], 'statuses': statuses}))
                closed = unpack(await client.call_tool('run_close', {'context': caller, 'run_id': started['run_id'],
                    'generation': started['generation'], 'objective_outcome': 'disposed'}))
                assert closed['objective_completion'] == 'disposed'
    asyncio.run(run())


def test_bounded_detail_pages_recover_original_json_without_semantic_claims(tmp_path):
    _, store, _, caller, _, owner, _ = environment(tmp_path)
    body = ('Historical observation, not an execution instruction. 保留限定条件。\n' * 600)
    record = {'kind': 'observation', 'title': 'Large retained account', 'body': body, 'scope': 'project', 'sources': [{'uri': owner.as_uri()}]}
    made = store.capture(caller, record, 'large', {'reason': 'Fixture review', 'evidence': record['sources']})
    args = {'context': caller, 'ids': [made['id']], 'max_bytes': 2500}
    first = call_operation(store, 'read', args)
    cursor = first['items'][0]['detail_page']
    parts = []
    while cursor:
        page = call_operation(store, 'read', {**args, 'page': cursor})
        assert len(json.dumps(page, ensure_ascii=False).encode()) <= 2500
        parts.append(page['detail_page']['text'])
        cursor = page['next_page']
    assert json.loads(''.join(parts))['body'] == body
    cursor = first['items'][0]['detail_page']
    store.delete(caller, made['id'], {'reason': 'Withdraw fixture', 'evidence': record['sources']}, 'withdraw-large')
    with pytest.raises(MemoryError):
        call_operation(store, 'read', {**args, 'page': cursor})
