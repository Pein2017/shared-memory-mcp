"""Published view consumption follows current, dependency-scoped authority."""
from copy import deepcopy
import json

import pytest

from dreaming_helpers import begin, claim, environment, freeze_publish, review, view_op
from shared_memory_mcp.core import MemoryError, _digest
from shared_memory_mcp.dreaming import Dreaming, configure_policy
from shared_memory_mcp import dream_views


def published(tmp_path, *, collaboration=False):
    env = environment(tmp_path)
    engine = env[0]
    rid, gen, owner, human = begin(engine)
    if collaboration:
        c = claim(human, level='explicit')
        create = {'id': 'P', 'action': 'collaboration_create', 'claim': c,
                  'review': review(c['refs']), 'visibility': 'active'}
        vc = {**c, 'refs': ['op:P']}
        ops = [create, view_op('V', vc, kind='collaboration')]
    else:
        ops = [view_op('V', claim(owner))]
    _, result = freeze_publish(engine, rid, gen, ops)
    assert result['status'] == 'applied', result
    kind = 'collaboration' if collaboration else 'research'
    current = engine.overview(kind, scenario='research')
    assert current['status'] == 'valid'
    return env, current


@pytest.mark.parametrize('change', ['profile', 'budgets', 'uncited-source', 'scenario', 'collaboration'])
def test_unrelated_policy_changes_preserve_current_and_historical_views(tmp_path, change):
    (engine, store, _, _, policy, _, _), current = published(tmp_path)
    updated = deepcopy(policy)
    profile = updated['profiles']['fixture']
    if change == 'profile':
        updated['profiles']['unrelated'] = deepcopy(profile)
    elif change == 'budgets':
        profile['budgets']['view_chars'] = 10
        profile['budgets']['seconds'] += 1
    elif change == 'uncited-source':
        profile['source_grants'][1]['attestations'] = {}
    elif change == 'scenario':
        profile['scenarios'].append('general')
    else:
        updated['collaboration_projects'] = []
    configure_policy(store, updated, expected_revision=_digest(policy))
    for historical in [None, current['revision']]:
        result = engine.overview('research', scenario='research', historical=historical)
        assert result['status'] == ('historical' if historical else 'valid')
        # Publication/execution budgets do not cap ordinary consumption.
        assert result['text'] == current['text']
    if change == 'budgets':
        limited = engine.overview('research', scenario='research', max_chars=10)
        assert limited['status'] == 'budget-limited' and limited['text'] == ''


@pytest.mark.parametrize('change', ['grant', 'attestation', 'scenario', 'target', 'executor', 'collaboration'])
@pytest.mark.parametrize('during_io', [False, True])
def test_relevant_revocation_blocks_current_and_historical_views(tmp_path, monkeypatch, change, during_io):
    is_collab = change in {'attestation', 'collaboration'}
    (engine, store, _, _, policy, _, _), current = published(tmp_path, collaboration=is_collab)
    updated = deepcopy(policy)
    profile = updated['profiles']['fixture']
    if change == 'grant':
        profile['source_grants'] = profile['source_grants'][1:]
    elif change == 'attestation':
        profile['source_grants'][1]['attestations'] = {}
    elif change == 'scenario':
        profile['scenarios'].remove('research')
    elif change == 'target':
        profile['target_projects'] = ['runner']
    elif change == 'executor':
        profile['executor_projects'] = ['demo']
    else:
        updated['collaboration_projects'] = []
    kind = 'collaboration' if is_collab else 'research'
    original_check = dream_views.check_snapshot
    for historical in [None, current['revision']]:
        if during_io:
            def revoke(spec, version):
                result = original_check(spec, version)
                configure_policy(store, updated, expected_revision=_digest(policy))
                return result
            monkeypatch.setattr(dream_views, 'check_snapshot', revoke)
        else:
            configure_policy(store, updated, expected_revision=_digest(policy))
        try:
            result = engine.overview(kind, scenario='research', historical=historical, target_project='demo')
        except MemoryError as exc:
            assert exc.code == 'dream_access_denied'
        else:
            assert result['text'] == ''
            assert result['status'] in {'invalidated', 'navigation'}
        configure_policy(store, policy, expected_revision=_digest(updated))


def test_empty_scenario_navigates_to_authorized_claim_scenarios(tmp_path):
    (engine, store, _, _, policy, _, _), current = published(tmp_path)
    result = engine.overview('research', scenario='engineering')
    assert result['status'] == 'navigation' and result['text'] == ''
    assert result['available_scenarios'] == ['research']
    assert result['revision'] == current['revision']
    updated = deepcopy(policy)
    updated['profiles']['fixture']['scenarios'] = ['engineering']
    configure_policy(store, updated, expected_revision=_digest(policy))
    result = engine.overview('research', scenario='research')
    assert result['status'] == 'navigation'
    assert result['available_scenarios'] == ['engineering']


def test_legacy_view_keeps_original_global_policy_fence(tmp_path):
    (engine, store, _, _, policy, _, _), current = published(tmp_path)
    base = store.root / 'dreaming/views/demo/research'
    document = json.loads((base / f"revisions/{current['revision']}.json").read_text())
    document.pop('read_policy_revision', None)
    revision = _digest(document)
    (base / f'revisions/{revision}.json').write_text(json.dumps(document))
    pointer = json.loads((base / 'current.json').read_text())
    pointer['revision'] = revision
    (base / 'current.json').write_text(json.dumps(pointer))
    assert engine.overview('research', scenario='research')['status'] == 'valid'
    updated = deepcopy(policy)
    updated['profiles']['unrelated'] = deepcopy(updated['profiles']['fixture'])
    configure_policy(store, updated, expected_revision=_digest(policy))
    for historical in [None, revision]:
        assert engine.overview('research', scenario='research', historical=historical)['status'] == 'invalidated'


def test_equivalent_reader_profile_retains_existing_access(tmp_path):
    (engine, store, caller, _, policy, _, _), current = published(tmp_path)
    updated = deepcopy(policy)
    updated['profiles']['reader'] = deepcopy(updated['profiles']['fixture'])
    configure_policy(store, updated, expected_revision=_digest(policy))
    reader = Dreaming(store, 'reader', caller)
    assert reader.overview('research', scenario='research')['text'] == current['text']


def test_execution_budget_change_during_io_does_not_blank_reader(tmp_path, monkeypatch):
    (engine, store, _, _, policy, _, _), _ = published(tmp_path)
    updated = deepcopy(policy)
    updated['profiles']['fixture']['budgets']['view_chars'] = 10
    original_check = dream_views.check_snapshot
    def shrink(spec, version):
        result = original_check(spec, version)
        configure_policy(store, updated, expected_revision=_digest(policy))
        return result
    monkeypatch.setattr(dream_views, 'check_snapshot', shrink)
    result = engine.overview('research', scenario='research')
    assert result['status'] == 'valid'
    assert result['text'] and result['omitted_claims'] == 0


def test_inferred_collaboration_permission_remains_a_read_dependency(tmp_path):
    engine, store, _, _, policy, _, _ = environment(tmp_path)
    rid, gen, _, human = begin(engine)
    c = claim(human, level='inferred')
    create = {'id': 'P', 'action': 'collaboration_create', 'claim': c,
              'review': review(c['refs']), 'visibility': 'candidate'}
    frozen, result = freeze_publish(engine, rid, gen, [create])
    assert result['status'] == 'applied'
    promote = {'id': 'promote', 'action': 'collaboration_publish', 'claim': c,
               'record_id': frozen['operations'][0]['reserved_id'], 'review': review(c['refs'])}
    vc = {**c, 'refs': ['op:promote']}
    _, result = freeze_publish(engine, rid, gen, [promote, view_op('V', vc, kind='collaboration')],
                               reconsider_reason='Review the retained inferred candidate.')
    assert result['status'] == 'applied', result
    current = engine.overview('collaboration', scenario='research')
    assert current['status'] == 'valid'
    updated = deepcopy(policy)
    updated['profiles']['fixture']['allow_inferred'] = False
    configure_policy(store, updated, expected_revision=_digest(policy))
    for historical in [None, current['revision']]:
        result = engine.overview('collaboration', scenario='research', historical=historical)
        assert result['status'] == 'invalidated' and result['text'] == ''


def test_unrelated_policy_edit_still_blocks_frozen_view_publication(tmp_path):
    engine, store, _, _, policy, _, _ = environment(tmp_path)
    rid, gen, source, _ = begin(engine)
    draft = engine.freeze(rid, gen, [view_op('V', claim(source))])
    updated = deepcopy(policy)
    updated['profiles']['unrelated'] = deepcopy(updated['profiles']['fixture'])
    configure_policy(store, updated, expected_revision=_digest(policy))
    result = engine.publish(rid, gen, draft['draft_revision'])
    assert result['status'] == 'blocked'
    assert result['unresolved'][0]['code'] == 'stale_basis'
    assert engine.overview('research', scenario='research')['status'] == 'navigation'


def test_pi_view_persists_ancestry_proof_and_legacy_view_is_unverifiable(tmp_path):
    engine, store, _, _, policy, owner, _ = environment(tmp_path)
    native = owner.parent / 'pi.jsonl'
    native.write_text('\n'.join(json.dumps(x) for x in [
        {'type': 'session', 'id': 'pi-fixture', 'version': 3},
        {'type': 'message', 'id': 'A', 'parentId': None,
         'message': {'role': 'assistant', 'content': [{'type': 'text', 'text': 'Synthetic Pi report.'}]}}
    ]) + '\n')
    updated = deepcopy(policy)
    updated['profiles']['fixture']['source_grants'] = [
        {'id': 'pi', 'path': str(native), 'kind': 'file', 'format': 'pi', 'schema': 'pi-session-v3'}]
    configure_policy(store, updated, expected_revision=_digest(policy))
    run = engine.start(sources=[{'grant_id': 'pi', 'leaf_id': 'A'}])
    key = engine.materials(run['run_id'])['sources']['pi']['events'][0]['key']
    _, result = freeze_publish(engine, run['run_id'], run['generation'], [view_op('V', claim(key, level='report'))])
    assert result['status'] == 'applied', result
    current = engine.overview('research', scenario='research')
    assert current['status'] == 'valid'
    base = store.root / 'dreaming/views/demo/research'
    document = json.loads((base / f"revisions/{current['revision']}.json").read_text())
    assert document['sources']['pi'].pop('ancestry_verified') is True
    document.pop('read_policy_revision')
    revision = _digest(document)
    (base / f'revisions/{revision}.json').write_text(json.dumps(document))
    pointer = json.loads((base / 'current.json').read_text())
    pointer['revision'] = revision
    (base / 'current.json').write_text(json.dumps(pointer))
    for historical in [None, revision]:
        result = engine.overview('research', scenario='research', historical=historical)
        assert result['status'] == 'unverifiable' and result['text'] == ''
