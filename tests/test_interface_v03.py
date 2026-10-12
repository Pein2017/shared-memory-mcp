"""v0.3 public interface: 21 names, caller, cursors, fences, derived keys, envelopes and diagnostics."""
import asyncio
import json
import os
from pathlib import Path
import sys

import pytest

from shared_memory_mcp.core import MemoryError
from shared_memory_mcp.operations import (PUBLIC, READ_ONLY, RETIRED, call, decode_cursor, derive_key,
                                          encode_cursor)
from dreaming_helpers import claim, environment, record_op, review as semantic_review, view_op

V03 = ('context', 'search', 'read', 'capture', 'approve', 'supersede', 'withdraw', 'annotate',
       'source_list', 'source_read', 'dream_start', 'dream_status', 'dream_materials', 'dream_draft',
       'dream_publish', 'dream_close', 'dream_takeover', 'overview', 'issue_open', 'issue_list', 'issue_close')


def record(owner, title='Fixture finding', body='Fixture owner records coverage 7 under a CPU control.'):
    return {'kind': 'observation', 'title': title, 'body': body, 'scope': 'project',
            'sources': [{'uri': owner.as_uri(), 'locator': 'L1'}]}


def review(owner):
    return {'reason': 'Checked against the fixture owner', 'evidence': [{'uri': owner.as_uri(), 'locator': 'L1'}]}


def assert_envelope(tool, response):
    if tool == 'context':  # the budgeted startup packet keeps its documented hook/Pi shape
        assert response['packet_version'] == 1 and response['status'] == 'ok'
        return
    assert response['status'] == 'ok', response
    assert response['scope'] and isinstance(response['revision'], str) and response['revision']
    assert ('item' in response) != ('items' in response), sorted(response)
    assert 'next_cursor' in response and isinstance(response['omitted'], dict)
    assert all(isinstance(v, int) for v in response['omitted'].values())
    assert isinstance(response['truncated'], bool) and isinstance(response['notices'], list)
    assert set(response['budget']) == {'limit_bytes', 'used_bytes'} and response['budget']['used_bytes'] > 0
    if tool.startswith('dream_'):
        assert 'next' in response
        if response['next'] is not None:
            assert response['next']['tool'] in PUBLIC and response['next']['args']['caller']
    for legacy in ('offset', 'next_offset', 'next_page', 'corpus_revision'):
        assert legacy not in response


def shape_error(store, tool, arguments, field):
    with pytest.raises(MemoryError) as raised:
        call(store, tool, arguments)
    diagnostic = raised.value.diagnostic
    assert diagnostic['code'] == 'invalid_arguments' and field in diagnostic['message']
    assert diagnostic['example']['caller']
    return diagnostic


def test_public_names_are_exactly_twenty_one():
    assert PUBLIC == V03
    assert not set(RETIRED) & set(PUBLIC)
    assert 'dream_materials' not in READ_ONLY


def test_cursor_rejects_tampered_foreign_and_stale_tokens():
    token = encode_cursor('search', 'rev-1', {'offset': 3})
    assert decode_cursor(token, 'search', 'rev-1') == ('rev-1', {'offset': 3})
    body = json.loads(__import__('base64').urlsafe_b64decode(token + '=' * (-len(token) % 4)))
    body['position']['offset'] = 0  # hand-edited position keeps valid JSON
    tampered = __import__('base64').urlsafe_b64encode(json.dumps(body).encode()).decode().rstrip('=')
    for bad, code in ((tampered, 'invalid_cursor'), ('not-a-cursor', 'invalid_cursor'),
                      (encode_cursor('read', 'rev-1', {'offset': 3}), 'invalid_cursor')):
        with pytest.raises(MemoryError) as raised:
            decode_cursor(bad, 'search', 'rev-1')
        assert raised.value.code == code
    with pytest.raises(MemoryError) as raised:
        decode_cursor(token, 'search', 'rev-2')
    assert raised.value.code == 'stale_cursor'


def test_legacy_arguments_are_rejected_with_an_example(tmp_path):
    _, store, _, caller, _, owner, _ = environment(tmp_path)
    assert 'cursor' in shape_error(store, 'search', {'caller': caller, 'query': 'x', 'offset': 2}, 'offset')['message']
    shape_error(store, 'read', {'caller': caller, 'ids': ['0' * 32], 'page': {'id': '0' * 32}}, 'page')
    run = '0123456789abcdef0123456789abcdef'
    assert 'expected_revision' in shape_error(store, 'dream_close', {'caller': caller, 'run_id': run, 'generation': 1}, 'generation')['message']
    assert 'caller' in shape_error(store, 'context', {'context': caller}, 'context')['message']
    shape_error(store, 'context', {'caller': caller, 'max_chars': 6000}, 'max_chars')
    shape_error(store, 'annotate', {'caller': caller, 'id': run, 'review': review(owner),
                                    'expected_content_digest': 'x'}, 'expected_content_digest')
    shape_error(store, 'capture', {'caller': caller}, 'record')
    with pytest.raises(MemoryError) as raised:
        call(store, 'create', {'caller': caller, 'record': record(owner)})
    assert raised.value.code == 'unknown_tool' and '`create` was retired; use `capture`' in str(raised.value)
    with pytest.raises(MemoryError) as raised:
        call(store, 'search', {'caller': {**caller, 'role': 'boss'}})
    assert raised.value.diagnostic['code'] == 'invalid_arguments'


def test_derived_idempotency_key_replays_and_conflicts(tmp_path):
    _, store, _, caller, _, owner, _ = environment(tmp_path)
    lineage = {**caller, 'role': 'worker', 'model': 'fixture-model', 'parent_session_id': 'fixture-lead'}
    first = call(store, 'capture', {'caller': lineage, 'record': record(owner)})
    assert first['item']['effective_status'] == 'candidate' and not first['replayed']
    again = call(store, 'capture', {'caller': lineage, 'record': record(owner)})
    assert again['replayed'] and again['item']['id'] == first['item']['id']
    assert again['idempotency_key'] == first['idempotency_key']
    assert first['idempotency_key'] == 'derived:' + derive_key(caller, {'tool': 'capture', 'record': record(owner),
                                                                        'collection': 'project'})
    with pytest.raises(MemoryError) as raised:  # reusing the reported key with changed content fails
        call(store, 'capture', {'caller': caller, 'record': record(owner, body='Changed content.'),
                                'idempotency_key': first['idempotency_key']})
    assert raised.value.code == 'idempotency_conflict'
    other = call(store, 'capture', {'caller': {**caller, 'session_id': 'another-session'}, 'record': record(owner)})
    assert other['item']['id'] != first['item']['id']


def test_stale_search_cursor_and_stale_record_fence(tmp_path):
    _, store, _, caller, _, owner, _ = environment(tmp_path)
    for index in range(3):
        call(store, 'capture', {'caller': caller, 'record': record(owner, f'Fixture coverage {index}'), 'review': review(owner)})
    page = call(store, 'search', {'caller': caller, 'query': 'fixture coverage', 'limit': 1})
    assert_envelope('search', page)
    assert page['next_cursor'] and page['truncated']
    following = call(store, 'search', {'caller': caller, 'query': 'fixture coverage', 'limit': 1, 'cursor': page['next_cursor']})
    assert following['items'][0]['id'] != page['items'][0]['id']
    call(store, 'capture', {'caller': caller, 'record': record(owner, 'Fixture coverage late'), 'review': review(owner)})
    with pytest.raises(MemoryError) as raised:
        call(store, 'search', {'caller': caller, 'query': 'fixture coverage', 'limit': 1, 'cursor': page['next_cursor']})
    assert raised.value.code == 'stale_cursor'
    target = page['items'][0]['id']
    revision = call(store, 'read', {'caller': caller, 'ids': [target]})['items'][0]['revision']
    done = call(store, 'annotate', {'caller': caller, 'id': target, 'review': review(owner),
                                    'details': {'summary': 'Fixture summary'}, 'expected_revision': revision})
    assert_envelope('annotate', done)
    with pytest.raises(MemoryError) as raised:
        call(store, 'annotate', {'caller': caller, 'id': target, 'review': review(owner), 'retired': True,
                                 'expected_revision': revision})
    assert raised.value.diagnostic['current_revision'] == done['revision'] != revision


def test_every_tool_response_has_the_uniform_envelope(tmp_path):
    _, store, _, caller, _, owner, _ = environment(tmp_path)
    seen = {}

    def files():
        return {str(f.relative_to(store.root)): f.read_bytes() for f in store.root.rglob('*')
                if f.is_file() and '.sqlite3' not in f.name}

    def run(tool, **arguments):
        before = files() if tool in READ_ONLY else None
        response = call(store, tool, {'caller': caller, **arguments})
        assert_envelope(tool, response)
        if before is not None:  # read-only annotation matches persistence (cursor-handle SQLite cache excluded)
            assert files() == before, tool
        seen[tool] = response
        return response

    run('context', query='fixture')
    candidate = run('capture', record=record(owner, 'Candidate finding'))['item']
    active = run('capture', record=record(owner, 'Active finding'), review=review(owner))['item']
    run('search', query='finding')
    run('search', statuses=['candidate'])
    run('read', ids=[active['id']])
    run('annotate', id=active['id'], review=review(owner), details={'summary': 'Fixture'})
    run('approve', id=candidate['id'], review=review(owner))
    successor = run('capture', record=record(owner, 'Successor finding'))['item']
    run('supersede', id=successor['id'], old_ids=[active['id']], review=review(owner))
    run('withdraw', id=candidate['id'], review=review(owner))
    grants = run('source_list')['items']
    assert {g['id'] for g in grants} == {'owner', 'human'}
    run('source_list', grant_id='owner')
    run('source_read', selection={'grant_id': 'owner'})
    started = run('dream_start', review_objective={'id': 'iface', 'question': 'Review the fixture owners.'})
    run_id = started['item']['run_id']
    assert started['next'] == {'tool': 'dream_materials', 'args': {'caller': caller, 'run_id': run_id}}
    status = run('dream_status', run_id=run_id)
    taken = run('dream_takeover', run_id=run_id, expected_revision=status['revision'])
    with pytest.raises(MemoryError) as raised:  # the old run revision is a stale fence after takeover
        call(store, 'dream_takeover', {'caller': caller, 'run_id': run_id, 'expected_revision': status['revision']})
    assert raised.value.code == 'stale_attempt' and raised.value.diagnostic['current_revision'] == taken['revision']
    material = run('dream_materials', run_id=run_id)
    assert material['next']['tool'] == 'dream_draft'
    sources = material['item']['sources']
    owner_key = sources['owner']['events'][0]['key']
    statuses = {e['key']: 'processed' for source in sources.values() for e in source['events']}
    statuses.update({item['ref']: 'no-signal' for item in started['item']['objective_progress']['ready_memory']})
    c = claim(owner_key)
    draft = run('dream_draft', run_id=run_id, expected_revision=material['next']['args']['expected_revision'],
                operations=[{'type': 'coverage', 'statuses': statuses}, record_op('fact', c), view_op('view', c)])
    assert draft['item']['draft']['operations'] and draft['item']['coverage']['processed']
    assert draft['next']['tool'] == 'dream_publish'
    published = run('dream_publish', **{k: v for k, v in draft['next']['args'].items() if k != 'caller'})
    opened = run('issue_open', run_id=run_id, expected_revision=published['revision'], topic='preservation',
                 relation='owner-clarification', note='Proposal only.', observations={'refs': [owner_key]})
    issues = run('issue_list', query='preservation')['items']
    run('issue_close', id=issues[0]['id'], disposition='handled', reason='Checked; no change needed.',
        expected_revision=issues[0]['revision'])
    run('overview', view='research', scenario='research')
    run('dream_close', run_id=run_id, expected_revision=opened['revision'], objective_outcome='reviewed')
    assert set(seen) == set(V03)


def test_fresh_stdio_client_lists_exactly_the_v03_surface(tmp_path):
    pytest.importorskip('mcp')
    _, store, _, caller, _, owner, _ = environment(tmp_path)

    async def session():
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
        params = StdioServerParameters(command=sys.executable,
            args=['-B', '-m', 'shared_memory_mcp.server', '--root', str(store.root)],
            env={'PATH': os.environ.get('PATH', ''), 'PYTHONPATH': str(Path(__file__).parents[1] / 'src'),
                 'PYTHONDONTWRITEBYTECODE': '1'})
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as client:
                await client.initialize()
                tools = (await client.list_tools()).tools
                assert tuple(t.name for t in tools) == V03
                for tool in tools:
                    properties = tool.inputSchema['properties']
                    assert 'caller' in tool.inputSchema['required'], tool.name
                    assert not {'context', 'offset', 'page', 'generation', 'max_chars', 'expected_content_digest'} & set(properties)
                    assert {'role', 'model', 'parent_session_id', 'task_id'} <= set(tool.inputSchema['$defs']['Caller']['properties'])
                    assert tool.annotations.readOnlyHint == (tool.name in READ_ONLY), tool.name
                assert next(t for t in tools if t.name == 'dream_materials').annotations.readOnlyHint is False
                for old in ('create', 'update', 'delete', 'curate', 'memory_audit', 'dream_catalog', 'run_start',
                            'draft_submit', 'coverage_mark', 'overview_read', 'issue_search'):
                    result = await client.call_tool(old, {'context': caller})
                    assert result.isError
                    diagnostic = json.loads(result.content[0].text)['diagnostic']
                    assert diagnostic['code'] == 'unknown_tool'
                    assert f'`{old}` was retired; use `{RETIRED[old]}`' in diagnostic['message']
                wrong = await client.call_tool('search', {'context': caller, 'query': 'x'})
                assert wrong.isError
                diagnostic = json.loads(wrong.content[0].text)['diagnostic']
                assert diagnostic['code'] == 'invalid_arguments' and diagnostic['example']['caller']
                typed = await client.call_tool('read', {'caller': caller, 'ids': 'not-a-list'})
                assert typed.isError and json.loads(typed.content[0].text)['diagnostic']['example']['ids']
                made = await client.call_tool('capture', {'caller': caller, 'record': record(owner)})
                assert not made.isError, made
                payload = json.loads(made.content[0].text)
                assert payload['item']['effective_status'] == 'candidate' and payload['idempotency_key'].startswith('derived:')
                denied = await client.call_tool('read', {'caller': {**caller, 'cwd': '/'}, 'ids': [payload['item']['id']]})
                assert denied.isError and json.loads(denied.content[0].text)['status'] == 'error'
    asyncio.run(session())
