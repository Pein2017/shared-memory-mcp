"""Unit-scoped freshness, compact rendition and removal on current revocation."""
from copy import deepcopy
import json

from shared_memory_mcp.core import _digest
from shared_memory_mcp.dreaming import configure_policy, add_disposition
from shared_memory_mcp.configuration import ViewReader
from dreaming_helpers import environment, begin, claim, view_op, freeze_publish


def account(tmp_path):
    engine, store, _, caller, _, owner, _ = environment(tmp_path)
    branch = tmp_path / 'branch.md'
    branch.write_text('The route is active. Preservation was not demonstrated.\n')
    policy, _ = engine._policy()
    new = deepcopy(policy)
    new['version'] = 3
    new['bindings'] = {'demo': 'fixture'}
    new['profiles']['fixture']['reader_projects'] = ['demo']
    new['profiles']['fixture']['source_grants'].append({
        'id': 'branch', 'kind': 'file', 'path': str(branch), 'format': 'document', 'schema': 'document-v1'})
    configure_policy(store, new, expected_revision=_digest(policy))
    started = engine.start(review_objective={'id': 'account', 'question': 'Summarize milestones and this branch.'})
    mats = engine.materials(started['run_id'])['sources']
    refs = {key: value['events'][0]['key'] for key, value in mats.items()}
    first = claim(refs['owner'], text='Detailed historical finite-fit description. ' * 80)
    first['narrative'] = {'id': 'capacity.milestone', 'role': 'milestone',
                          'compact': 'Finite-panel fit is a historical milestone, not transfer.'}
    second = claim(refs['branch'], text='The route is active. Preservation was not demonstrated.')
    second['narrative'] = {'id': 'airport.plan', 'role': 'current',
                           'compact': 'Airport route active; preservation not demonstrated.'}
    second['counterevidence'] = ['The guard cohort lost clear source objects.']
    operation = view_op('account', first)
    operation['claims'] = [first, second]
    operation['review']['checked_refs'] = [*first['refs'], *second['refs']]
    _, result = freeze_publish(engine, started['run_id'], started['generation'], [operation])
    assert result['status'] == 'applied', result
    return engine, store, caller, branch


def test_compact_default_is_useful_and_qualified(tmp_path):
    engine, store, caller, _ = account(tmp_path)
    view = engine.overview('research', scenario='research')
    assert 'Finite-panel fit is a historical milestone, not transfer.' in view['text']
    assert 'Detailed historical finite-fit description.' not in view['text']
    assert 'guard cohort lost' in view['text']
    assert len(json.dumps(view, ensure_ascii=False).encode()) <= 8000
    packet = store.context(caller, task_mode='research')
    assert 'Finite-panel fit' in packet['text'] and 'guard cohort lost' in packet['text']


def test_unrelated_source_drift_marks_only_its_unit(tmp_path):
    engine, _, _, branch = account(tmp_path)
    before = engine.overview('research', scenario='research')
    branch.write_text(branch.read_text().replace('active', 'paused'))
    after = engine.overview('research', scenario='research')
    assert after['as_of'] == before['as_of']
    assert 'Finite-panel fit' in after['text'] and 'Airport route active' in after['text']
    units = {u['unit_id']: u for u in after['items']}
    assert units['capacity.milestone']['freshness'] == 'as-of'
    assert units['airport.plan']['freshness'] == 'needs-check'
    assert not after['current_state_verified']


def test_revoked_unit_never_leaks_through_historical_context(tmp_path):
    engine, store, caller, branch = account(tmp_path)
    old = engine.overview('research', scenario='research')
    add_disposition(store, caller, target='demo', topic='*', scope='research',
                    source_keys=['source-uri:' + branch.as_uri()], kind='no_reuse', reason='Fixture withdrawal of branch source.')
    for view in [engine.overview('research', scenario='research'),
                 engine.overview('research', scenario='research', historical=old['revision'])]:
        assert 'Finite-panel fit' in view['text']
        assert 'Airport route active' not in view['text']
        assert 'guard cohort lost' not in json.dumps(view)
        assert view['unavailable_units']


def test_view_reader_does_not_require_execution_membership(tmp_path):
    engine, store, caller, _ = account(tmp_path)
    policy, _ = engine._policy()
    updated = deepcopy(policy)
    executor = tmp_path / 'read-only-consumer-executor'
    executor.mkdir()
    store.register('tools', [str(executor)])
    updated['profiles']['fixture']['executor_projects'] = ['tools']
    configure_policy(store, updated, expected_revision=_digest(policy))
    view = ViewReader(store, caller).overview('research', scenario='research')
    assert 'Finite-panel fit' in view['text']
