"""Accepted memories are qualified inputs, not a mandate to replay raw history."""
from copy import deepcopy
from shared_memory_mcp.core import _digest
from shared_memory_mcp.dreaming import configure_policy
from dreaming_helpers import begin, claim, environment, freeze_publish, record_op, view_op


def accepted(engine, *, level='recorded'):
    run, generation, key, _ = begin(engine)
    operation = record_op('initial', claim(key, level=level))
    frozen, result = freeze_publish(engine, run, generation, [operation])
    assert result['status'] == 'applied'
    return frozen['operations'][0]['reserved_id']


def test_accepted_memory_merge_without_raw_source_and_default_recall(tmp_path):
    engine, store, _, caller, _, owner, _ = environment(tmp_path)
    predecessor = accepted(engine)
    owner.unlink()
    started = engine.start(sources=[])
    ref = 'record:' + predecessor
    operation = record_op('absorbed', claim(ref))
    operation.update(action='record_supersede', predecessors=[predecessor])
    frozen, result = freeze_publish(engine, started['run_id'], 1, [operation])
    assert result['status'] == 'applied', result
    successor = frozen['operations'][0]['reserved_id']
    items = store.search(caller, 'fixture-coverage')['items']
    assert successor in {r['id'] for r in items}
    assert predecessor not in {r['id'] for r in items}
    historical = store.read(caller, [predecessor], include_inactive=True)['items'][0]
    assert historical['effective_status'] == 'superseded'


def test_memory_only_view_keeps_qualification_and_cannot_upgrade(tmp_path):
    engine, _, _, _, _, _, _ = environment(tmp_path)
    identifier = accepted(engine, level='hypothesis')
    started = engine.start(sources=[])
    ref = 'record:' + identifier
    _, rejected = freeze_publish(engine, started['run_id'], 1, [view_op('wrong', claim(ref))])
    assert rejected['status'] == 'blocked'
    assert rejected['unresolved'][0]['code'] == 'evidence_upgrade'
    _, result = freeze_publish(engine, started['run_id'], 1,
                               [view_op('qualified', claim(ref, level='hypothesis'))],
                               reconsider_reason='Keep the original evidence level.')
    assert result['status'] == 'applied', result
    view = engine.overview('research', scenario='research')
    assert 'hypothesis' in view['text']


def test_unrelated_policy_and_record_edits_do_not_block_publication(tmp_path):
    engine, store, _, owner_caller, policy, _, _ = environment(tmp_path)
    started = engine.start()
    key = engine.materials(started['run_id'])['sources']['owner']['events'][0]['key']
    frozen = engine.freeze(started['run_id'], 1, [record_op('new', claim(key))])
    record = {'scope': 'project', 'kind': 'observation', 'title': 'Unrelated accepted note',
              'body': 'Different evidence.', 'sources': [{'uri': 'https://example.org/other'}]}
    store.propose(owner_caller, record, 'unrelated-note')
    current = dict(policy)
    current['profiles'] = {**policy['profiles'], 'other': dict(policy['profiles']['fixture'])}
    configured = configure_policy(store, current, expected_revision=_digest(policy))
    assert configured['status'] == 'configured'
    result = engine.publish(started['run_id'], 1, frozen['draft_revision'])
    assert result['status'] == 'applied', result


def test_accepted_memory_revocation_still_blocks_synthesis(tmp_path):
    engine, store, _, caller, _, _, _ = environment(tmp_path)
    identifier = accepted(engine)
    started = engine.start(sources=[])
    ref = 'record:' + identifier
    frozen = engine.freeze(started['run_id'], 1, [record_op('later', claim(ref))])
    store.delete(caller, identifier, {'reason': 'Withdraw the fixture claim.',
                                    'evidence': [{'uri': 'https://example.org/withdrawal'}]}, 'withdraw-input')
    result = engine.publish(started['run_id'], 1, frozen['draft_revision'])
    assert result['status'] == 'blocked'


def test_catalog_publication_verification_accounts_for_consumed_prefix(tmp_path):
    engine, store, _, _, policy, _, _ = environment(tmp_path)
    page = engine.source_read({'grant_id': 'owner'})
    started = engine.start(sources=[page['selection']])
    material = engine.materials(started['run_id'])['sources']['owner']
    frozen = engine.freeze(started['run_id'], 1, [record_op('fenced', claim(material['events'][0]['key']))])
    changed = deepcopy(policy)
    changed['profiles']['fixture']['budgets']['source_bytes'] = material['version']['consumed'] + 1
    configure_policy(store, changed, expected_revision=_digest(policy))
    result = engine.publish(started['run_id'], 1, frozen['draft_revision'])
    assert result['status'] == 'blocked'
    assert result['unresolved'][0]['code'] == 'source_budget_exhausted'
