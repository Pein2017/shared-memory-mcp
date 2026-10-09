"""Semantic continuation shares the existing protected physical lane."""
import pytest
from shared_memory_mcp.core import MemoryError
from dreaming_helpers import environment

A = {'id': 'branch-account', 'question': 'Review the branch account and turning points.'}
B = {'id': 'preservation', 'question': 'Review preservation counterexamples over the same owners.'}


def mark_all(engine, started, state):
    keys = [e['key'] for m in engine.materials(started['run_id'])['sources'].values() for e in m['events']]
    engine.mark_processed(started['run_id'], started['generation'], {key: state for key in keys})


def test_same_source_new_objective_and_active_lane(tmp_path):
    engine, *_ = environment(tmp_path)
    first = engine.start(review_objective=A)
    blocked = engine.start(review_objective=B)
    assert blocked['status'] == 'resume-required' and blocked['run_id'] == first['run_id']
    mark_all(engine, first, 'processed')
    engine.close(first['run_id'], first['generation'], objective_outcome='reviewed')
    unchanged = engine.start(review_objective=A)
    assert unchanged['status'] == 'no-change' and unchanged['objective_completion'] == 'reviewed'
    new = engine.start(review_objective=B)
    assert new['status'] == 'created' and new['model_required']
    assert engine.inspect(new['run_id'])['processed'] == {}
    assert new['review_objective'] == B


def test_pending_objective_cannot_claim_completion(tmp_path):
    engine, *_ = environment(tmp_path)
    first = engine.start(review_objective=A)
    mark_all(engine, first, 'pending-review')
    with pytest.raises(MemoryError, match='pending'):
        engine.close(first['run_id'], first['generation'], objective_outcome='reviewed')
    engine.close(first['run_id'], first['generation'])
    continued = engine.start(review_objective=A)
    assert continued['status'] == 'created' and continued['pending_review'] > 0
    assert continued['source_changes'] == 'unchanged'
    assert continued['objective_completion'] == 'pending'


def test_processing_alone_is_not_objective_review(tmp_path):
    engine, *_ = environment(tmp_path)
    first = engine.start(review_objective=A)
    mark_all(engine, first, 'processed')
    engine.close(first['run_id'], first['generation'])
    continued = engine.start(review_objective=A)
    assert continued['status'] == 'created'
    mark_all(engine, continued, 'no-signal')
    engine.close(continued['run_id'], continued['generation'], objective_outcome='disposed')
    assert engine.start(review_objective=A)['status'] == 'no-change'


def test_readable_changed_source_and_objective_identity(tmp_path):
    engine, _, _, _, _, owner, _ = environment(tmp_path)
    first = engine.start(review_objective=A)
    mark_all(engine, first, 'processed')
    engine.close(first['run_id'], first['generation'], objective_outcome='reviewed')
    with pytest.raises(MemoryError, match='objective'):
        engine.start(review_objective={**A, 'question': 'A different question under the same id'})
    owner.write_text(owner.read_text() + '\nPreservation failed on the guard cohort.\n')
    changed = engine.start(review_objective=A)
    delta = engine.changes(changed['run_id'])
    assert delta['source_changes'] == 'changed'
    assert any('Preservation failed' in x.get('diff', '') for x in delta['sources'])
    assert delta['objective_completion'] == 'pending'
