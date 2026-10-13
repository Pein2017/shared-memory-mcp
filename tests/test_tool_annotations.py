"""The advertised safety contract follows observable local persistence effects."""
import asyncio

import pytest

from dreaming_helpers import environment
from shared_memory_mcp.operations import call


def test_catalog_annotations_match_effects(tmp_path):
    pytest.importorskip('mcp')
    from shared_memory_mcp.server import make_server

    _, store, _, _, _, _, _ = environment(tmp_path)
    tools = {t.name: t for t in asyncio.run(make_server(store).list_tools())}
    reads = {'context', 'search', 'read', 'source_list', 'source_read', 'dream_status', 'overview', 'issue_list'}
    append_only = {'capture', 'dream_start'}
    for name, tool in tools.items():
        hints = tool.annotations.model_dump(exclude_none=True)
        assert hints['readOnlyHint'] is (name in reads), name
        assert hints['destructiveHint'] is (name not in reads | append_only), name
        assert hints['idempotentHint'] is (name not in {'dream_draft', 'issue_open'}), name
        assert hints['openWorldHint'] is False, name
    assert 'read progress' in tools['dream_materials'].description
    assert 'replace' in tools['dream_draft'].description
    assert 'update' in tools['issue_open'].description


def test_identical_draft_calls_create_new_drafts(tmp_path):
    _, store, _, caller, _, _, _ = environment(tmp_path)
    started = call(store, 'dream_start', {'caller': caller,
        'review_objective': {'id': 'annotations', 'question': 'Review fixture source.'}})
    run_id = started['item']['run_id']
    materials = call(store, 'dream_materials', {'caller': caller, 'run_id': run_id})
    event = materials['item']['sources']['owner']['events'][0]['key']
    call(store, 'dream_materials', {'caller': caller, 'run_id': run_id, 'source_id': 'owner', 'event_key': event})
    args = {'caller': caller, 'run_id': run_id, 'expected_revision': started['revision'],
            'operations': [{'type': 'coverage', 'statuses': {event: 'processed'}}]}
    first = call(store, 'dream_draft', args)
    second = call(store, 'dream_draft', args)
    assert first['revision'] != second['revision']
    status = call(store, 'dream_status', {'caller': caller, 'run_id': run_id})
    assert len(status['item']['drafts']) == 2


def test_issue_upsert_replaces_retained_content(tmp_path):
    _, store, _, caller, _, _, _ = environment(tmp_path)
    started = call(store, 'dream_start', {'caller': caller,
        'review_objective': {'id': 'issues', 'question': 'Review fixture source.'}})
    args = {'caller': caller, 'run_id': started['item']['run_id'], 'expected_revision': started['revision'],
            'topic': 'fixture', 'relation': 'owner', 'note': 'Original proposal', 'observations': {},
            'semantic_reviewed': True}
    first = call(store, 'issue_open', args)
    repeated = call(store, 'issue_open', args)
    assert first['item']['notify'] is True
    assert repeated['item']['notify'] is False
    changed = call(store, 'issue_open', {**args, 'note': 'Revised proposal'})
    assert changed['item']['id'] == first['item']['id']
    listed = call(store, 'issue_list', {'caller': caller})
    assert [item['note'] for item in listed['items']] == ['Revised proposal']


def test_material_read_can_reset_saved_page_progress(tmp_path):
    _, store, _, caller, _, owner, _ = environment(tmp_path)
    owner.write_text('Fixture source. ' * 1000)
    started = call(store, 'dream_start', {'caller': caller,
        'review_objective': {'id': 'materials', 'question': 'Review fixture source.'}})
    run_id = started['item']['run_id']
    material = call(store, 'dream_materials', {'caller': caller, 'run_id': run_id})
    key = material['item']['sources']['owner']['events'][0]['key']
    args = {'caller': caller, 'run_id': run_id, 'source_id': 'owner', 'event_key': key}
    call(store, 'dream_materials', {**args, 'max_bytes': 262144})
    import json
    run_file = store.root / 'dreaming' / 'runs' / run_id / 'run.json'
    assert json.loads(run_file.read_text())['material_reads'][key]['complete'] is True
    call(store, 'dream_materials', {**args, 'max_bytes': 2048})
    assert json.loads(run_file.read_text())['material_reads'][key]['complete'] is False
    assert owner.read_text() == 'Fixture source. ' * 1000
