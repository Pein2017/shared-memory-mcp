from copy import deepcopy
import hashlib
import json
import pytest

from shared_memory_mcp.core import MemoryError
from shared_memory_mcp.dream_records import collaboration
from shared_memory_mcp.dreaming import Dreaming, add_disposition, configure_policy
from dreaming_helpers import environment, begin, claim, review, record_op, view_op, freeze_publish


@pytest.fixture
def env(tmp_path):
    return environment(tmp_path)


def test_real_canonical_vertical_and_withdrawal_invalidation(env):
    engine, store, caller, owner_caller, _, _, _ = env
    rid, gen, source, _ = begin(engine)
    c = claim(source)
    frozen, result = freeze_publish(engine, rid, gen, [record_op('A', c), view_op('V', claim('op:A'))])
    assert result['status'] == 'applied', result
    record_id = frozen['operations'][0]['reserved_id']
    current = engine.overview('research', scenario='research')
    assert current['status'] == 'valid' and 'Counterevidence:' in current['text']
    assert store.context(owner_caller)['items'] == []
    record = store.read(owner_caller, [record_id])['items'][0]
    assert record['project_id'] == 'demo' and record['provenance']['cwd'] == caller['cwd']
    original = (store.root / f'records/demo/{record_id}.md').read_bytes()
    store.delete(owner_caller, record_id, {'reason': 'Fixture withdrawal', 'evidence': record['sources']}, 'withdraw-fixture')
    assert (store.root / f'records/demo/{record_id}.md').read_bytes() == original
    for historical in [None, current['revision']]:
        hidden = engine.overview('research', scenario='research', historical=historical)
        assert hidden['status'] == 'invalidated' and hidden['text'] == ''


@pytest.mark.parametrize('boundary', ['intent-saved', 'effect-0-written', 'receipt-written'])
def test_fault_recovery_and_old_attempt_fence(env, monkeypatch, boundary):
    engine, store, caller, _, _, _, _ = env
    rid, gen, source, _ = begin(engine)
    frozen = engine.freeze(rid, gen, [record_op('A', claim(source))])
    def crash(point, operation):
        if point == boundary:
            raise RuntimeError('injected fixture crash')
    monkeypatch.setattr(engine, '_fault', crash)
    with pytest.raises(RuntimeError, match='injected'):
        engine.publish(rid, gen, frozen['draft_revision'])
    next_caller = {**caller, 'harness': 'pi', 'session_id': 'fixture-executor-B'}
    resumed = Dreaming(store, 'fixture', next_caller, publisher=True)
    assert resumed.takeover(rid, gen)['generation'] == 2
    result = resumed.publish(rid, 2, frozen['draft_revision'])
    assert result['status'] == 'applied', result
    records = store._load('demo')
    assert len(records) == 1
    expected_executor = next_caller if boundary == 'intent-saved' else caller
    assert records[0]['provenance']['session_id'] == expected_executor['session_id']
    with pytest.raises(MemoryError, match='generation'):
        engine.publish(rid, gen, frozen['draft_revision'])
    assert resumed.publish(rid, 2, frozen['draft_revision'])['status'] == 'applied'
    assert len(store._load('demo')) == 1


def test_view_revision_crash_does_not_activate_orphan(env, monkeypatch):
    engine, store, caller, _, _, _, _ = env
    rid, gen, source, _ = begin(engine)
    frozen = engine.freeze(rid, gen, [view_op('V', claim(source))])
    def crash(point, operation):
        if point == 'effect-0-written':
            raise RuntimeError('view crash')
    monkeypatch.setattr(engine, '_fault', crash)
    with pytest.raises(RuntimeError):
        engine.publish(rid, gen, frozen['draft_revision'])
    assert engine.overview('research', scenario='research')['status'] == 'navigation'
    resumed = Dreaming(store, 'fixture', {**caller, 'harness': 'claude', 'session_id': 'fixture-C'}, publisher=True)
    resumed.takeover(rid, gen)
    assert resumed.publish(rid, 2, frozen['draft_revision'])['status'] == 'applied'
    assert resumed.overview('research', scenario='research')['status'] == 'valid'
    assert len(list((store.root / 'dreaming/views/demo/research/revisions').glob('*.json'))) == 1


def test_new_counter_record_changes_basis_even_when_target_unchanged(env):
    engine, store, _, owner_caller, _, owner, _ = env
    rid, gen, source, _ = begin(engine)
    frozen = engine.freeze(rid, gen, [record_op('A', claim(source))])
    store.propose(owner_caller, {'kind': 'observation', 'title': 'A contrary new record', 'body': 'Counterexample.',
                                 'scope': 'project', 'sources': [{'uri': owner.as_uri()}]}, 'external-change')
    result = engine.publish(rid, gen, frozen['draft_revision'])
    assert result['status'] == 'blocked' and result['unresolved'][0]['code'] == 'stale_basis'
    assert len(store._load('demo')) == 1


def test_partial_publication_preserves_A_and_blocks_B_view(env):
    engine, store, _, _, _, _, _ = env
    rid, gen, source, _ = begin(engine)
    risky = claim(source); risky['risks'] = ['execution-authority']
    frozen, result = freeze_publish(engine, rid, gen, [record_op('A', claim(source)), record_op('B', risky), view_op('V', claim('op:B'))])
    assert result['status'] == 'partial', result
    assert {e['operation_id'] for e in result['unresolved']} == {'B', 'V'}
    assert len(store._load('demo')) == 1
    assert engine.overview('research', scenario='research')['status'] == 'navigation'
    engine.publish(rid, gen, frozen['draft_revision'])
    assert len(store._load('demo')) == 1


def test_inferred_candidate_cannot_escape_through_view_then_reviewed_publish(env):
    engine, store, _, _, _, _, _ = env
    rid, gen, _, human = begin(engine)
    c = claim(human, level='inferred', text='The synthetic fixture suggests detailed research discussion.')
    create = {'id': 'P', 'action': 'collaboration_create', 'claim': c, 'review': review(c['refs']), 'visibility': 'active'}
    vc = deepcopy(c); vc['refs'] = ['op:P']
    frozen, result = freeze_publish(engine, rid, gen, [create, view_op('CV', vc, kind='collaboration')])
    assert result['status'] == 'partial', result
    candidate_id = frozen['operations'][0]['reserved_id']
    assert collaboration(store)[0]['effective_status'] == 'candidate'
    publish = {'id': 'review-P', 'action': 'collaboration_publish', 'record_id': candidate_id, 'claim': c, 'review': review(c['refs'])}
    vc['refs'] = ['op:review-P']
    _, result = freeze_publish(engine, rid, gen, [publish, view_op('CV2', vc, kind='collaboration')], reconsider_reason='Fixture explicit semantic candidate review.')
    assert result['status'] == 'applied', result
    view = engine.overview('collaboration', scenario='research')
    assert view['status'] == 'valid' and '[inferred]' in view['text']
    assert {p['id'] for p in store._registry()['projects']} == {'demo', 'runner'}
    assert store._load('demo') == []


def test_unknown_attribution_and_derivative_cannot_be_preferences(env):
    engine, _, _, _, _, _, _ = env
    rid, gen, source, _ = begin(engine)
    c = claim(source, level='explicit')
    _, result = freeze_publish(engine, rid, gen, [{'id': 'P', 'action': 'collaboration_create', 'claim': c,
                                                  'review': review(c['refs']), 'visibility': 'active'}])
    assert result['unresolved'][0]['code'] == 'human_attribution_required'


def test_research_stale_does_not_clear_collaboration_and_budget_keeps_whole_claim(env):
    engine, _, _, _, _, owner, _ = env
    rid, gen, source, human = begin(engine)
    c = claim(human, level='explicit', text='Synthetic explicit scoped preference.')
    create = {'id': 'P', 'action': 'collaboration_create', 'claim': c, 'review': review(c['refs']), 'visibility': 'active'}
    vc = deepcopy(c); vc['refs'] = ['op:P']
    _, result = freeze_publish(engine, rid, gen, [create, view_op('CV', vc, kind='collaboration'), view_op('RV', claim(source))])
    assert result['status'] == 'applied', result
    old = engine.overview('research', scenario='research')
    assert engine.overview('research', scenario='research', max_chars=10)['text'] == ''
    owner.write_text('The fixture owner now records a contrary result.\n')
    assert engine.overview('research', scenario='research')['status'] == 'stale'
    assert engine.overview('research', scenario='research', historical=old['revision'])['status'] == 'historical'
    assert engine.overview('collaboration', scenario='research')['status'] == 'valid'


def test_no_reuse_blocks_default_historical_and_ordinary_record_reads(env):
    engine, store, caller, owner_caller, _, _, _ = env
    rid, gen, source, _ = begin(engine)
    frozen, result = freeze_publish(engine, rid, gen, [record_op('A', claim(source)), view_op('V', claim('op:A'))])
    assert result['status'] == 'applied'
    record_id = frozen['operations'][0]['reserved_id']
    old = engine.overview('research', scenario='research')
    add_disposition(store, caller, target='demo', topic='*', scope='research', source_keys=[source], kind='no_reuse', reason='Synthetic privacy fixture.')
    for historical in [None, old['revision']]:
        assert engine.overview('research', scenario='research', historical=historical)['text'] == ''
    assert store.read(owner_caller, [record_id], include_inactive=True)['items'] == []
    assert engine.materials(rid)['sources']['owner']['events'] == []


def test_default_rerun_ignores_own_memory_and_logs(env):
    engine, _, _, _, _, _, _ = env
    rid, gen, source, _ = begin(engine)
    _, result = freeze_publish(engine, rid, gen, [record_op('A', claim(source)), view_op('V', claim('op:A'))])
    assert result['status'] == 'applied'
    keys = [e['key'] for m in engine.materials(rid)['sources'].values() for e in m['events']]
    engine.mark_processed(rid, gen, {key: 'processed' for key in keys})
    assert engine.close(rid, gen)['coverage'] == 'complete'
    rerun = engine.start()
    assert rerun['status'] == 'no-change' and rerun['model_required'] is False
    assert engine.inspect(rid)['model_calls'] == 0


def test_advisory_and_bound_executor_cannot_expand_authority(env):
    engine, store, caller, _, _, _, _ = env
    rid, gen, source, _ = begin(engine)
    advisory = Dreaming(store, 'fixture', caller)
    frozen = advisory.freeze(rid, gen, [record_op('A', claim(source))])
    with pytest.raises(MemoryError, match='draft only'):
        advisory.publish(rid, gen, frozen['draft_revision'])
    with pytest.raises(MemoryError):
        advisory.materials(rid, '/arbitrary/path')
    other = Dreaming(store, 'fixture', {**caller, 'session_id': 'unrelated'})
    with pytest.raises(MemoryError, match='authenticate'):
        other.freeze(rid, gen, [record_op('X', claim(source))])


def test_issue_identity_is_stable_across_observed_versions(env):
    engine, _, _, _, _, _, _ = env
    rid, gen, _, _ = begin(engine)
    kwargs = {'topic': 'owner-report', 'relation': 'check-against-artifact', 'note': 'Check the same fixture claim.'}
    first = engine.suggest_issue(rid, gen, **kwargs, observations={'commit': 'a'}, semantic_reviewed=True)
    again = engine.suggest_issue(rid, gen, **kwargs, observations={'commit': 'b'}, semantic_reviewed=False)
    assert first['id'] == again['id'] and first['notify']
    assert not again['notify'] and again['needs_semantic_review']
