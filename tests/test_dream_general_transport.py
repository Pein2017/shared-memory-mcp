"""Real general endpoint caller-to-consumer qualification; no native/model claims."""
import asyncio
from copy import deepcopy
import json
import sys

import pytest

from dreaming_helpers import environment, claim, record_op
from test_dream_transport import ENV, args_for, cli, payload
from shared_memory_mcp.dreaming import Dreaming, configure_policy
from shared_memory_mcp.dream_transport import make_dream_server

GENERAL = {'dream_catalog', 'memory_audit', 'source_list', 'source_read', 'run_start',
           'run_observe', 'run_takeover', 'run_materials', 'draft_submit', 'draft_read',
           'coverage_mark', 'run_close', 'overview_read', 'issue_suggest'}


@pytest.mark.parametrize('harness', ['codex', 'pi', 'claude', 'webcodex'])
def test_general_schema_labels_cannot_change_authority(tmp_path, harness):
    pytest.importorskip('mcp')
    _, store, caller, *_ = environment(tmp_path)
    engine = Dreaming(store, 'fixture', {**caller, 'harness': harness})
    tools = asyncio.run(make_dream_server(engine).list_tools())
    assert {t.name for t in tools} == GENERAL
    catalog_schema = next(t.inputSchema for t in tools if t.name == 'dream_catalog')
    assert {'cursor', 'limit'} <= set(catalog_schema['properties'])
    for tool in tools:
        assert tool.inputSchema['additionalProperties'] is False
        assert not {'cwd', 'profile', 'caller', 'enable_publisher'} & set(tool.inputSchema.get('properties', {}))


def test_general_cli_and_stdio_discovers_audits_selects_and_publishes(tmp_path):
    pytest.importorskip('mcp')
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    _, store, caller, owner_caller, _, owner, _ = environment(tmp_path)
    catalog = cli(store, caller, 'catalog')
    assert catalog['target_projects'] == ['demo']
    listing = cli(store, caller, 'source-list', '--grant-id', 'owner')
    assert listing['items'][0]['kind'] == 'file'
    page = cli(store, caller, 'source-read', data={'grant_id': 'owner'})
    assert page['selection']['page']
    # Historical memory is ordinary canonical v1, deliberately outside a live Run.
    historical = store.propose(owner_caller, {'kind': 'observation', 'title': 'Historical fixture', 'body': 'Only historical navigation.',
        'scope': 'project', 'sources': [{'uri': owner.as_uri()}]}, 'historical-fixture')
    historical_id = historical['record']['id']
    store.delete(owner_caller, historical_id,
                 {'reason': 'Synthetic historical withdrawal', 'evidence': [{'uri': owner.as_uri()}]},
                 'historical-withdrawal')
    audited = cli(store, caller, 'audit', '--target-project', 'demo', '--filters-stdin',
                  data={'ids': [historical_id], 'statuses': ['withdrawn']})
    assert audited['items'][0]['id'] == historical_id

    async def sequence():
        advisory = StdioServerParameters(command=sys.executable, args=args_for(store, caller, 'serve'), env=ENV)
        async with stdio_client(advisory) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                assert {t.name for t in (await session.list_tools()).tools} == GENERAL
                assert payload(await session.call_tool('dream_catalog', {}))['publisher'] is False
                audit = payload(await session.call_tool('memory_audit', {'target_project': 'demo'}))
                assert any(item['id'] == historical_id and item['effective_status'] == 'withdrawn'
                           for item in audit['items']), audit
                listed = payload(await session.call_tool('source_list', {'grant_id': 'owner'}))
                assert listed['items']
                public = payload(await session.call_tool('source_read', {'selection': {'grant_id': 'owner'}}))
                for name, arguments in [
                    ('run_start', {'target_project': 'runner'}),
                    ('source_read', {'selection': {'grant_id': 'absent'}}),
                    ('source_read', {'selection': {'grant_id': 'owner', 'path': '/etc/passwd'}}),
                    ('dream_catalog', {'cwd': caller['cwd']}),
                    ('run_start', {'profile': 'other', 'enable_publisher': True}),
                    ('draft_publish', {}), ('create', {}), ('run_shell', {'command': 'false'})]:
                    assert (await session.call_tool(name, arguments)).isError, name
                started = payload(await session.call_tool('run_start', {'target_project': 'demo', 'sources': [public['selection']]}))
                rid, gen = started['run_id'], started['generation']
                material = payload(await session.call_tool('run_materials', {'run_id': rid}))
                event = next(iter(material['sources'].values()))['events'][0]['key']
                frozen = payload(await session.call_tool('draft_submit', {'run_id': rid, 'generation': gen,
                    'operations': [record_op('A', claim(event))]}))
                assert payload(await session.call_tool('draft_read', {'run_id': rid, 'revision': frozen['draft_revision']}))['operations']
        publisher = StdioServerParameters(command=sys.executable, args=args_for(store, caller, 'serve', '--enable-publisher'), env=ENV)
        async with stdio_client(publisher) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                applied = payload(await session.call_tool('draft_publish', {'run_id': rid, 'generation': gen,
                    'revision': frozen['draft_revision']}))
                assert applied['status'] == 'applied'
                marked = payload(await session.call_tool('coverage_mark', {'run_id': rid, 'generation': gen,
                    'statuses': {event: 'processed'}}))
                assert marked
                assert payload(await session.call_tool('run_close', {'run_id': rid, 'generation': gen}))['status'] == 'closed'
        return rid
    rid = asyncio.run(sequence())
    records = store._load('demo')
    published = next(r for r in records if r['title'] == 'fixture-coverage')
    consumed = store.read(owner_caller, [published['id']])
    assert consumed['items'][0]['id'] == published['id']
    assert published['scope'] == 'project' and published['provenance']['cwd'] == caller['cwd']
    assert published['provenance']['session_id'] == caller['session_id']
    assert rid


def test_general_cli_selector_injection_and_partial_fixed_binding_are_denied(tmp_path):
    _, store, caller, *_ = environment(tmp_path)
    assert cli(store, caller, 'start', '--selectors-stdin', data={'cwd': caller['cwd']}, expected=2)['status'] == 'error'
    assert cli(store, caller, 'serve', '--run-id', '0' * 32, expected=2)['status'] == 'error'
    start = cli(store, caller, 'start', '--target-project', 'demo', '--sources', json.dumps([{'grant_id': 'owner'}]))
    assert start['status'] == 'created'


def test_general_methods_independent_targets_and_explicit_attempt_takeover(tmp_path):
    pytest.importorskip('mcp')
    from shared_memory_mcp.core import MemoryError
    engine, store, caller, _, policy, _, _ = environment(tmp_path)
    second = tmp_path / 'second'; second.mkdir()
    store.register('second', [second])
    policy = deepcopy(policy)
    policy['profiles']['fixture']['target_projects'].append('second')
    from shared_memory_mcp.core import _digest
    configure_policy(store, policy, expected_revision=_digest(json.loads((store.root / 'dreaming/policy.json').read_text())))
    engine = Dreaming(store, 'fixture', caller, publisher=True)
    with pytest.raises(MemoryError, match='Select one authorized target'):
        engine.start()
    first = engine.start(target_project='demo', sources=[{'grant_id': 'owner'}])
    other = engine.start(target_project='second', sources=[{'grant_id': 'owner'}])
    assert first['run_id'] != other['run_id']
    assert engine.inspect(first['run_id'])['target'] == 'demo'
    assert engine.inspect(other['run_id'])['target'] == 'second'
    replacement = Dreaming(store, 'fixture', {**caller, 'session_id': 'synthetic-replacement'}, publisher=True)
    with pytest.raises(MemoryError) as denied:
        replacement.mark_processed(first['run_id'], first['generation'], {})
    assert denied.value.code == 'attempt_identity_mismatch'
    adopted = replacement.takeover(first['run_id'], first['generation'])
    assert adopted['generation'] == 2
    with pytest.raises(MemoryError) as stale:
        engine.mark_processed(first['run_id'], first['generation'], {})
    assert stale.value.code == 'stale_attempt'
    assert engine.inspect(other['run_id'])['generation'] == 1
    advisory = Dreaming(store, 'fixture', replacement.caller)
    with pytest.raises(MemoryError) as denied:
        advisory.publish(first['run_id'], 2, '0' * 64)
    assert denied.value.code == 'advisory_only'


def test_cli_rejects_selected_stale_source_page_without_starting_run(tmp_path):
    _, store, caller, _, _, owner, _ = environment(tmp_path)
    public = cli(store, caller, 'source-read', data={'grant_id': 'owner'})
    owner.write_text(owner.read_text() + 'Changed after discovery.\n')
    result = cli(store, caller, 'start', '--selectors-stdin',
                 data={'target_project': 'demo', 'sources': [public['selection']]}, expected=2)
    assert result['diagnostic']['code'] == 'source_changed'
    assert cli(store, caller, 'catalog')['active_runs'] == []


def test_catalog_cli_pages_allowed_runs_after_target_revocation(tmp_path):
    engine, store, caller, _, policy, _, _ = environment(tmp_path)
    second = tmp_path / 'catalog-second'; second.mkdir()
    store.register('catalog-second', [second])
    policy = deepcopy(policy)
    policy['profiles']['fixture']['target_projects'].append('catalog-second')
    from shared_memory_mcp.core import _digest
    def configure():
        configure_policy(store, policy, expected_revision=_digest(
            json.loads((store.root / 'dreaming/policy.json').read_text())))
    configure()
    first = engine.start(target_project='demo', sources=[{'grant_id': 'owner'}])
    another = engine.start(target_project='demo', sources=[{'grant_id': 'human'}])
    engine.start(target_project='catalog-second', sources=[{'grant_id': 'owner'}])
    policy['profiles']['fixture']['target_projects'].remove('catalog-second')
    configure()
    page = cli(store, caller, 'catalog', '--limit', '1')
    assert len(page['active_runs']) == 1 and page['next_cursor'] and page['revision']
    continuation = cli(store, caller, 'catalog', '--limit', '1', '--cursor', page['next_cursor'])
    assert len(continuation['active_runs']) == 1 and continuation['next_cursor'] is None
    assert continuation['revision'] == page['revision']
    assert {r['id'] for r in page['active_runs'] + continuation['active_runs']} == {
        first['run_id'], another['run_id']}
