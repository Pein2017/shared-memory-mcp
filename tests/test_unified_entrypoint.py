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
                assert {'context', 'capture', 'supersede', 'withdraw', 'dream_start', 'dream_status', 'dream_publish', 'overview'} <= names
                record = preference(owner)
                made = unpack(await client.call_tool('capture', {'caller': caller, 'collection': 'collaboration',
                    'record': record, 'idempotency_key': 'stdio-current-pref', 'review': review(record), 'live_correction': live()}))
                response = await client.call_tool('context', {'caller': caller, 'task_mode': 'general'})
                packet = unpack(response)
                assert '/new/project-path' in packet['text'] and packet['caller_context']['session_id'] == caller['session_id']
                assert len(response.model_dump_json(by_alias=True, exclude_none=True).encode()) <= 8000
                bad = await client.call_tool('context', {'caller': {**caller, 'publisher': True}})
                assert bad.isError
                forbidden = await client.call_tool('dream_start', {'caller': caller, 'profile': 'fixture',
                    'review_objective': {'id': 'stdio', 'question': 'Review the fixture owners.'}})
                assert forbidden.isError
                started = unpack(await client.call_tool('dream_start', {'caller': caller,
                    'review_objective': {'id': 'stdio', 'question': 'Review the fixture owners.'}}))
                assert started['outcome'] == 'created'
                run_id = started['item']['run_id']
                material = unpack(await client.call_tool('dream_materials', {'caller': caller, 'run_id': run_id}))
                statuses = {e['key']: 'no-signal' for source in material['item']['sources'].values() for e in source['events']}
                statuses.update({item['ref']: 'no-signal' for item in started['item']['objective_progress']['ready_memory']})
                drafted = unpack(await client.call_tool('dream_draft', {'caller': caller, 'run_id': run_id, 'expected_revision': material['revision'],
                    'operations': [{'type': 'coverage', 'statuses': statuses}]}))
                # Coverage marks take effect atomically when the draft is published.
                assert drafted['next']['tool'] == 'dream_publish'
                published = unpack(await client.call_tool('dream_publish', {'caller': caller, 'run_id': run_id,
                    'expected_revision': drafted['revision']}))
                closed = unpack(await client.call_tool('dream_close', {'caller': caller, 'run_id': run_id,
                    'expected_revision': published['revision'], 'objective_outcome': 'disposed'}))
                assert closed['item']['objective_completion'] == 'disposed'
    asyncio.run(run())


def test_bounded_detail_pages_recover_original_json_without_semantic_claims(tmp_path):
    _, store, _, caller, _, owner, _ = environment(tmp_path)
    body = ('Historical observation, not an execution instruction. 保留限定条件。\n' * 600)
    record = {'kind': 'observation', 'title': 'Large retained account', 'body': body, 'scope': 'project', 'sources': [{'uri': owner.as_uri()}]}
    made = store.capture(caller, record, 'large', {'reason': 'Fixture review', 'evidence': record['sources']})
    args = {'caller': caller, 'ids': [made['id']], 'max_bytes': 2500}
    first = call_operation(store, 'read', args)
    cursor = first['items'][0]['cursor']
    parts = []
    while cursor:
        page = call_operation(store, 'read', {**args, 'cursor': cursor})
        assert len(json.dumps(page, ensure_ascii=False).encode()) <= 2500
        parts.append(page['detail_page']['text'])
        cursor = page['next_cursor']
    assert json.loads(''.join(parts))['body'] == body
    cursor = first['items'][0]['cursor']
    store.delete(caller, made['id'], {'reason': 'Withdraw fixture', 'evidence': record['sources']}, 'withdraw-large')
    with pytest.raises(MemoryError):
        call_operation(store, 'read', {**args, 'cursor': cursor})
