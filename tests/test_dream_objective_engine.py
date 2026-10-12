"""Retained engine callers exercise objective close and checkpoint recovery."""
from copy import deepcopy
import json

import pytest

from dreaming_helpers import environment
from shared_memory_mcp.core import MemoryError, _digest, _json
from shared_memory_mcp.dreaming import configure_policy


OBJECTIVE = {'id': 'engine-baseline', 'question': 'Review the applicable fixture history.'}


def test_claude_history_root_reaches_catalog_and_retained_materials(tmp_path):
    from test_dream_sources import claude_message, line
    engine, store, _, _, policy, _, _ = environment(tmp_path)
    root = tmp_path / 'claude-projects'
    project = root / 'encoded-project'
    project.mkdir(parents=True)
    (project / 'session.jsonl').write_bytes(line(claude_message('claude-event', None, text='Historical Claude text.')))
    updated = deepcopy(policy)
    history = {'path': str(root), 'format': 'claude', 'schema': 'claude-jsonl-v1', 'native_version': 'fixture-v1'}
    updated['profiles']['fixture'].update(read_access='inherited', history_roots=[history])
    configure_policy(store, updated, expected_revision=_digest(policy))
    assert engine.catalog()['history_roots'] == [history]
    run = engine.start(review_objective=OBJECTIVE)
    sources = engine.materials(run['run_id'])['sources']
    events = [event for source in sources.values() for event in source['events'] if event['harness'] == 'claude']
    assert [event['text'] for event in events] == ['Historical Claude text.']
    assert events[0]['branch'] == 'default-leaf' and events[0]['human'] == 'unknown'


def historical_environment(tmp_path):
    engine, store, caller, owner_caller, policy, owner, human = environment(tmp_path)
    root = tmp_path / 'native'
    (root / 'older').mkdir(parents=True)
    for i in range(18):
        rows = [json.loads(row) for row in human.read_text().splitlines()]
        rows[0]['payload']['id'] = f'fixture-session-{i}'
        rows[1]['id'] = f'fixture-human-{i}'
        (root / 'older' / f'{i:02}.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
    updated = deepcopy(policy)
    updated['profiles']['fixture'].update(read_access='inherited', history_roots=[{
        'path': str(root), 'format': 'codex', 'schema': 'codex-rollout-v1', 'native_version': 'fixture-v1'}])
    updated['profiles']['fixture']['budgets'].update(source_bytes=1048576, events=128)
    configure_policy(store, updated, expected_revision=_digest(policy))
    return engine, store, owner_caller, owner, human, root


def mark_sources(engine, run):
    statuses = {}
    for sid, material in engine.materials(run['run_id'])['sources'].items():
        statuses.update({event['key']: 'no-signal' for event in material['events']})
        if not material['events'] and material['version']:
            statuses['source:' + sid] = 'no-signal'
    engine.mark_processed(run['run_id'], run['generation'], statuses)
    return set(statuses)


def test_historical_batches_expand_and_semantic_outcome_is_global(tmp_path):
    engine, _, _, _, human, root = historical_environment(tmp_path)
    first = engine.start(review_objective=OBJECTIVE)
    assert first['objective_progress']['remaining_sources'] == 20
    first_keys = mark_sources(engine, first)
    assert len(first_keys) == 16
    with pytest.raises(MemoryError) as error:
        engine.close(first['run_id'], 1, objective_outcome='reviewed')
    assert error.value.code == 'pending_objective'
    closed = engine.close(first['run_id'], 1)
    assert closed['objective_progress']['remaining_sources'] == 4
    correction = root / 'older-correction.jsonl'
    rows = [json.loads(row) for row in human.read_text().splitlines()]
    rows[0]['payload']['id'] = 'fixture-correction-session'
    rows[1]['id'] = 'fixture-correction-human'
    correction.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    second = engine.start(review_objective=OBJECTIVE, sources=[{
        'absolute_path': str(correction), 'format': 'codex', 'schema': 'codex-rollout-v1',
        'native_version': 'fixture-v1'}])
    assert second['run_id'] != first['run_id']
    assert second['objective_progress']['remaining_sources'] == 5
    assert not first_keys.intersection(mark_sources(engine, second))
    closed = engine.close(second['run_id'], 1, objective_outcome='reviewed')
    assert closed['objective_progress']['remaining_sources'] == 0
    assert engine.start(review_objective=OBJECTIVE)['status'] == 'no-change'


def test_closed_run_recovers_objective_before_index_write(tmp_path, monkeypatch):
    engine, store, *_ = historical_environment(tmp_path)
    first = engine.start(review_objective=OBJECTIVE)
    first_keys = mark_sources(engine, first)
    def crash(point, operation):
        if point == 'run-closed':
            raise RuntimeError('fixture close interruption')
    monkeypatch.setattr(engine, '_fault', crash)
    with pytest.raises(RuntimeError):
        engine.close(first['run_id'], 1)
    durable = engine._run(first['run_id'])
    assert durable['phase'] == 'closed'
    assert not (store.root / durable['objective_path']).exists()
    assert engine.inspect(first['run_id'])['objective_progress']['remaining_sources'] == 4
    monkeypatch.setattr(engine, '_fault', lambda *args: None)
    second = engine.start(review_objective=OBJECTIVE)
    assert second['objective_progress']['remaining_sources'] == 4
    assert not first_keys.intersection(mark_sources(engine, second))
    engine.close(second['run_id'], 1, objective_outcome='reviewed')
    assert engine.start(review_objective=OBJECTIVE)['status'] == 'no-change'


def test_technical_batch_review_does_not_establish_semantic_no_change(tmp_path):
    engine, *_ = environment(tmp_path)
    first = engine.start(review_objective=OBJECTIVE)
    mark_sources(engine, first)
    closed = engine.close(first['run_id'], 1)
    assert closed['objective_completion'] == 'pending'
    assert closed['objective_progress']['objective_completion'] == 'reviewable-complete'
    second = engine.start(review_objective=OBJECTIVE)
    assert second['status'] == 'created'
    assert engine.materials(second['run_id'])['sources'] == {}
    engine.close(second['run_id'], 1, objective_outcome='disposed')
    assert engine.start(review_objective=OBJECTIVE)['status'] == 'no-change'


def test_memory_pending_statuses_and_changed_revision_are_guarded(tmp_path):
    engine, store, _, owner_caller, _, owner, _ = environment(tmp_path)
    identifier = store.propose(owner_caller, {'scope': 'project', 'kind': 'observation',
        'title': 'Fixture backlog', 'body': 'An existing candidate also needs explicit review.',
        'sources': [{'uri': owner.as_uri()}]}, 'objective-memory')['record']['id']
    ref = 'record:' + identifier
    run = engine.start(review_objective=OBJECTIVE)
    assert run['objective_progress']['ready_memory'][0]['ref'] == ref
    mark_sources(engine, run)
    engine.mark_processed(run['run_id'], 1, {ref: 'pending-review'})
    with pytest.raises(MemoryError) as error:
        engine.close(run['run_id'], 1, objective_outcome='reviewed')
    assert error.value.code == 'pending_objective'
    engine.close(run['run_id'], 1)
    second = engine.start(review_objective=OBJECTIVE)
    assert second['objective_progress']['remaining_memory'] == 1
    engine.materials(second['run_id'], event_key=ref)
    engine.mark_processed(second['run_id'], 1, {ref: 'no-signal'})
    assert engine.changes(second['run_id'])['objective_progress']['ready_memory'][0]['ref'] == ref
    assert len(_json(engine.changes(second['run_id'], max_bytes=12000)).encode()) <= 12000
    store.promote(owner_caller, identifier, {'reason': 'Synthetic independent revision change.',
                  'evidence': [{'uri': owner.as_uri()}]}, 'objective-memory-promote')
    with pytest.raises(MemoryError) as error:
        engine.mark_processed(second['run_id'], 1, {ref: 'processed'})
    assert error.value.code == 'stale_dependency'
    with pytest.raises(MemoryError):
        engine.close(second['run_id'], 1, objective_outcome='reviewed')
    closed = engine.close(second['run_id'], 1, abandon_reason='Fixture revision must be re-reviewed.')
    assert closed['partial']


def test_completed_objective_changed_memory_needs_new_review(tmp_path):
    engine, store, _, owner_caller, _, owner, _ = environment(tmp_path)
    identifier = store.propose(owner_caller, {'scope': 'project', 'kind': 'observation',
        'title': 'Fixture changed increment', 'body': 'A revised canonical input needs another review.',
        'sources': [{'uri': owner.as_uri()}]}, 'increment-memory')['record']['id']
    ref = 'record:' + identifier
    first = engine.start(review_objective=OBJECTIVE)
    mark_sources(engine, first)
    engine.materials(first['run_id'], event_key=ref)
    engine.mark_processed(first['run_id'], 1, {ref: 'no-signal'})
    engine.close(first['run_id'], 1, objective_outcome='reviewed')
    store.promote(owner_caller, identifier, {'reason': 'Fixture later memory revision.',
                  'evidence': [{'uri': owner.as_uri()}]}, 'increment-memory-promote')
    second = engine.start(review_objective=OBJECTIVE)
    assert second['status'] == 'created'
    assert second['objective_progress']['remaining_memory'] == 1
    assert ref not in engine.inspect(second['run_id'])['processed']
    with pytest.raises(MemoryError) as error:
        engine.close(second['run_id'], 1, objective_outcome='reviewed')
    assert error.value.code == 'pending_objective'
    engine.materials(second['run_id'], event_key=ref)
    engine.mark_processed(second['run_id'], 1, {ref: 'no-signal'})
    engine.close(second['run_id'], 1, objective_outcome='reviewed')
    assert engine.start(review_objective=OBJECTIVE)['status'] == 'no-change'


@pytest.mark.parametrize('read_complete', [False, True])
def test_full_material_continuation_required_to_recover_excerpt_gap(tmp_path, read_complete):
    engine, store, _, _, policy, owner, _ = environment(tmp_path)
    owner.write_text('Fixture full owner text. ' * 400)
    updated = deepcopy(policy)
    updated['profiles']['fixture']['budgets']['source_bytes'] = 1048576
    configure_policy(store, updated, expected_revision=_digest(policy))
    run = engine.start(review_objective=OBJECTIVE)
    material = engine.materials(run['run_id'])['sources']['owner']
    event = material['events'][0]
    assert len(event['text']) == 4096
    assert event['excerpt_truncated']
    page = engine.materials(run['run_id'], 'owner', event_key=event['key'], max_chars=2048)
    assert not engine._run(run['run_id'])['material_reads'][event['key']]['complete']
    if read_complete:
        while page['page']['next_cursor']:
            page = engine.materials(run['run_id'], 'owner', event_key=event['key'], max_chars=2048,
                                    cursor=page['page']['next_cursor'])
        assert engine._run(run['run_id'])['material_reads'][event['key']]['complete']
    mark_sources(engine, run)
    if read_complete:
        closed = engine.close(run['run_id'], 1, objective_outcome='reviewed')
        assert closed['objective_progress']['remaining_sources'] == 0
        assert engine.start(review_objective=OBJECTIVE)['status'] == 'no-change'
    else:
        with pytest.raises(MemoryError) as error:
            engine.close(run['run_id'], 1, objective_outcome='reviewed')
        assert error.value.code == 'pending_objective'
        assert engine.inspect(run['run_id'])['objective_progress']['remaining_sources'] == 2
