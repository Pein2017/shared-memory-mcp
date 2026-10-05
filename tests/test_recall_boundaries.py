"""Trust, recovery and real CLI boundaries retained by recall curation."""
import json
from pathlib import Path
import subprocess
import sys

import pytest
from shared_memory_mcp.core import MemoryError
from test_recall_curation import env, accepted, record, REVIEW


@pytest.mark.parametrize('details', [
    {'statement_type': []}, {'domain': []},
    {'source_roles': [{'uri': [], 'role': 'owner'}]},
    {'source_roles': [{'uri': 'file:///research/owner.md', 'role': []}]},
    {'relations': [{'type': [], 'uri': 'file:///research/owner.md'}]},
    {'extensions': {'non_finite': float('nan')}},
])
def test_bad_optional_metadata_is_rejected_before_capture(env, details):
    store, ctx, _ = env
    with pytest.raises(MemoryError):
        store.capture(ctx, record(), 'invalid', review=REVIEW, details=details)
    assert store.doctor()['projects']['demo'] == 0


def test_curation_and_routing_symlink_rejected(env, tmp_path):
    store, ctx, _ = env
    r = accepted(store, ctx, 'target')
    outside = tmp_path / 'outside'; outside.mkdir()
    (store.root / 'curation').symlink_to(outside, target_is_directory=True)
    with pytest.raises(MemoryError):
        store.curate(ctx, r['id'], REVIEW, 'escape', retired=True)
    assert list(outside.iterdir()) == []
    (store.root / 'routing').symlink_to(outside, target_is_directory=True)
    view = store.context(ctx)
    assert view['status'] == 'invalid' and view['text'] == ''


def test_doctor_includes_curation_integrity(env):
    store, ctx, _ = env
    r = accepted(store, ctx, 'target')
    store.curate(ctx, r['id'], REVIEW, 'meta', details={'domain': 'engineering'})
    p = store.root / 'curation/demo' / (r['id'] + '.json')
    data = json.loads(p.read_text()); data['content_digest'] = '0' * 64
    p.write_text(json.dumps(data))
    with pytest.raises(MemoryError):
        store.doctor()


def test_source_roles_and_origin_are_not_independent_evidence(env):
    store, ctx, _ = env
    r = accepted(store, ctx, 'target')
    details = {'source_roles': [{'uri': r['sources'][0]['uri'], 'role': 'derivative'}],
               'statement_type': 'interpretation', 'conditions': 'Original data not independently checked.'}
    store.curate(ctx, r['id'], REVIEW, 'metadata', details=details)
    item = store.search(ctx, 'pytest')['items'][0]
    assert item['sources'][0]['role'] == 'derivative'
    assert item['statement_type'] == 'interpretation'
    assert store.read(ctx, [r['id']])['items'][0]['sources'] == r['sources']


def test_retirement_cannot_restore_withdrawn_record(env):
    store, ctx, _ = env
    r = accepted(store, ctx, 'target')
    store.delete(ctx, r['id'], REVIEW, 'withdraw')
    store.curate(ctx, r['id'], REVIEW, 'unretire', retired=False)
    assert store.read(ctx, [r['id']])['missing_ids'] == [r['id']]
    assert store.read(ctx, [r['id']], True)['items'][0]['effective_status'] == 'withdrawn'


def test_webcodex_public_cli_bridge_uses_real_context(env):
    store, ctx, project = env
    r = accepted(store, ctx, 'target')
    context = {**ctx, 'harness': 'webcodex', 'session_id': 'wc_sess_isolated_cli'}
    command = [sys.executable, '-m', 'shared_memory_mcp.cli', '--root', str(store.root), 'call', '--tool', 'search']
    result = subprocess.run(command, input=json.dumps({'context': context, 'query': 'pytest'}),
                            text=True, capture_output=True, cwd=project)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload['scope']['cwd'] == str(project) and payload['items'][0]['id'] == r['id']
    invalid = subprocess.run(command, input='{"context":', text=True, capture_output=True, cwd=project)
    assert invalid.returncode != 0
    assert json.loads(invalid.stdout)['diagnostic']['code'] == 'invalid_input'
    nav = subprocess.run(command[:-1] + ['context'], input=json.dumps({'context': context}),
                         text=True, capture_output=True, cwd=project)
    assert nav.returncode == 0 and 'text' not in json.loads(nav.stdout)
    unknown = {**context, 'cwd': str(project.parent / 'absent-project')}
    failed = subprocess.run(command[:-1] + ['context'], input=json.dumps({'context': unknown}),
                            text=True, capture_output=True, cwd=project)
    assert failed.returncode == 2 and json.loads(failed.stdout)['status'] == 'unmapped'


def test_topic_siblings_are_not_automatically_query_synonyms(env):
    from test_recall_curation import routing
    store, ctx, _ = env
    routing(store)
    p = store.root / 'routing/demo.json'
    config = json.loads(p.read_text())
    config['topics'][0]['aliases'].append('CPU reduction')
    p.write_text(json.dumps(config))
    correct = accepted(store, ctx, 'pytest')
    accepted(store, ctx, 'cpu', title='CPU reduction', body='Thread-dependent sum.')
    result = store.search(ctx, 'pytest')
    assert [r['id'] for r in result['items']] == [correct['id']]
    assert 'cpu' not in result['query_expansion']
