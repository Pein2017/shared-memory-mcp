"""CoordExp lens uses real research owners as operator-configured routes, not hardcoded model claims."""
from copy import deepcopy
import json
from pathlib import Path

from dreaming_helpers import environment
from shared_memory_mcp.core import _digest
from shared_memory_mcp.dreaming import configure_policy


REPO = Path(__file__).resolve().parents[1]
ROOT = Path('/data/CoordExp/.worktrees/research-probes/research')


def test_coordexp_lens_source_manifest_is_current_scoped_and_versioned():
    routing = json.loads((REPO/'examples/coordexp-research-routing.json').read_text())
    manifest = json.loads((REPO/'examples/coordexp-research-grants.json').read_text())
    assert routing['context']['version'] == manifest['version'] == 1
    owners = routing['context']['owners']
    ids = {o['id'] for o in owners}
    assert {'research-index','short-continuation-result','instance-designation-result',
            'airport-composition-result','physical-owner-question'} <= ids
    topics = {t['id'] for t in routing['topics']}
    assert {'research-entry','greedy-credit','visual-use','physical-evaluation'} <= topics
    from shared_memory_mcp.owner_checks import validate_owners
    validate_owners(owners, routing['topics'])
    grants = {g['id']:g for g in manifest['source_grants']}
    assert {o['grant_id'] for o in owners} == set(grants)
    for grant in grants.values():
        assert grant['kind'] == 'file' and grant['format'] == 'document' and grant['schema'] == 'document-v1'
        assert Path(grant['path']).is_file() and Path(grant['path']).is_relative_to(ROOT)
    # Configured lens keeps these separations without storing a synthetic "latest result".
    description = routing['description'].lower()
    for term in ('physical-owner','annotation', 'supplied', 'natural', 'transfer',
                 'preservation', 'technical'):
        assert term in description
    assert not (REPO/'examples/coordexp-research-routing.json').resolve().is_relative_to(
        Path('/data/CoordExp/.shared-memory'))


def test_coordexp_config_retrieves_current_index_result_and_question_without_ingestion(tmp_path, monkeypatch):
    engine, store, _, caller, _, owner, _ = environment(tmp_path)
    example = json.loads((REPO/'examples/coordexp-research-routing.json').read_text())
    index = owner
    recent = owner.parent/'short-results.md'
    question = owner.parent/'greedy-question.md'
    index.write_text('Current research index: sparse-token experiment is stopped; separate newer branch is on HOLD.\n')
    recent.write_text('Short-continuation result: conditional owner progress, zero immediate strict successors. No training intervention.\n')
    question.write_text('Current airport decision: STOP; contrary to the retained short-continuation result. Natural empty-history coverage remains unproven.\n')
    selected = {'research-index': (index, 'index'),
                'short-continuation-result': (recent, 'result'),
                'greedy-compilation-question': (question, 'question')}
    routing = deepcopy(example)
    store._publish(store.root/'routing/demo.json', (json.dumps(routing)+'\n').encode())
    policy, _ = engine._policy()
    updated = deepcopy(policy)
    for spec in routing['context']['owners']:
        source = selected[spec['id']][0] if spec['id'] in selected else owner.parent/(spec['id']+'.md')
        if spec['id'] not in selected:
            source.write_text('Unselected configured owner: requires a separate bounded read.\n')
        updated['profiles']['fixture']['source_grants'].append({
            'id':spec['grant_id'], 'kind':'file', 'path':str(source),
            'format':'document', 'schema':'document-v1'})
    configure_policy(store, updated, expected_revision=_digest(policy))
    from shared_memory_mcp import dream_sources
    original = dream_sources._open_source
    opened = []
    def observe(source):
        opened.append(source['path'])
        return original(source)
    monkeypatch.setattr(dream_sources, '_open_source', observe)
    a = store.context(caller, query='airport research status', task_mode='research', current_status=True)
    assert a['status'] == 'ok', a
    assert a['owner_checks']['status'] == 'partial', a['owner_checks']
    assert {item['id'] for item in a['owner_checks']['items']} == set(selected)
    assert set(opened) == {str(path) for path, _ in selected.values()} and len(opened) == 3
    assert not a['owner_checks'].get('undelivered'), a['owner_checks']
    gaps = a['owner_checks']['gaps']
    assert {gap['id'] for gap in gaps} == {'research-story', 'preservation-question', 'airport-composition-result'}
    assert all(gap['reason'] == 'owner_selection_limit' and Path(gap['read_hint']['path']).is_file() for gap in gaps)
    assert 'sparse-token experiment is stopped' in a['text']
    assert 'zero immediate strict successors' in a['text']
    assert 'Current airport decision: STOP' in a['text']
    # Hooks and Pi deliver text, so the missing coverage and original pointers must survive that projection.
    assert 'Current owner coverage: partial' in a['text']
    assert str(question) in a['text']
    assert all(gap['read_hint']['path'] in a['text'] for gap in gaps)
    assert a['current_state_verified'] is False
    assert len(json.dumps(a,ensure_ascii=False).encode()) <= 8000
    b = store.context(caller, query='airport research status', task_mode='general', current_status=True)
    assert b['owner_checks']['status'] == 'partial'
    # Original research sources remain independent and are never used as test writes.
    assert (ROOT/'index.md').is_file()
