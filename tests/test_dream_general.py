"""Harness-neutral selection and scoped canonical consumer boundaries."""
from copy import deepcopy
import pytest
from dreaming_helpers import environment, claim, record_op, review
from shared_memory_mcp.core import MemoryError, _digest
from shared_memory_mcp.dreaming import Dreaming, configure_policy


def configure(store, policy, modify):
    updated = deepcopy(policy)
    modify(updated['profiles']['fixture'])
    configure_policy(store, updated, expected_revision=_digest(policy))
    return updated


def start_owner(engine, *, target='demo'):
    run = engine.start(target_project=target, sources=[{'grant_id': 'owner'}])
    key = engine.materials(run['run_id'])['sources']['owner']['events'][0]['key']
    return run, key


def publish(engine, run, operations):
    draft = engine.freeze(run['run_id'], run['generation'], operations)
    result = engine.publish(run['run_id'], run['generation'], draft['draft_revision'])
    assert result['status'] == 'applied', result
    return draft


def test_authorized_selection_audit_scoped_create_withdraw_core_consumer(tmp_path):
    engine, store, _, owner_caller, _, owner, _ = environment(tmp_path)
    scope = store._resolve(owner_caller)
    existing = store.propose(owner_caller, {'scope': 'worktree', 'kind': 'observation', 'title': 'old fixture',
        'body': 'Previous scoped fixture candidate.', 'sources': [{'uri': owner.as_uri()}]}, 'old-scoped')['record']['id']
    audit = engine.audit(ids=[existing])
    assert audit['items'][0]['scope'] == 'worktree'
    assert audit['items'][0]['effective_status'] == 'candidate'
    run, key = start_owner(engine)
    qualifier = {'scope': 'task', 'worktree_id': scope['worktree_id'], 'task_id': 'task-control'}
    operation = {**record_op('create', claim(key)), 'qualifier': qualifier}
    draft = publish(engine, run, [operation])
    identifier = draft['operations'][0]['reserved_id']
    task_caller = {**owner_caller, 'task_id': 'task-control'}
    record = store.read(task_caller, [identifier])['items'][0]
    assert {k: record[k] for k in qualifier} == qualifier
    assert store.read(owner_caller, [identifier])['items'] == []
    withdrawal = {'id': 'withdraw', 'action': 'record_withdraw', 'record_id': identifier, 'review': review([key])}
    second = publish(engine, run, [withdrawal])
    marker = engine.audit(ids=[second['operations'][0]['reserved_id']])['items'][0]
    assert store.read(task_caller, [identifier])['items'] == []
    assert {k: marker[k] for k in qualifier} == qualifier
    assert marker['withdraws'] == identifier
    assert not engine.audit(ids=[identifier])['items'][0]['usability']['usable']


def test_target_and_source_lanes_and_same_selection_resume(tmp_path):
    engine, store, _, _, policy, *_ = environment(tmp_path)
    configure(store, policy, lambda p: p.update(target_projects=['demo', 'runner']))
    with pytest.raises(MemoryError) as error:
        engine.start()
    assert error.value.code == 'target_required'
    first, _ = start_owner(engine)
    second, _ = start_owner(engine, target='runner')
    human = engine.start(target_project='demo', sources=[{'grant_id': 'human'}])
    assert len({first['run_id'], second['run_id'], human['run_id']}) == 3
    assert start_owner_resume(engine)['run_id'] == first['run_id']
    assert len(engine.catalog()['active_runs']) == 3
    for action in (lambda: engine.start(target_project='denied'),
                   lambda: engine.start(target_project='demo', sources=[{'grant_id': 'denied'}]),
                   lambda: engine.audit(target_project='denied')):
        with pytest.raises(MemoryError):
            action()


def start_owner_resume(engine):
    return engine.start(target_project='demo', sources=[{'grant_id': 'owner'}])


def test_revoked_selection_wrong_caller_and_cross_scope_supersession(tmp_path):
    engine, store, caller, owner_caller, policy, *_ = environment(tmp_path)
    run, key = start_owner(engine)
    scope = store._resolve(owner_caller)
    qualifier = {'scope': 'worktree', 'worktree_id': scope['worktree_id']}
    draft = publish(engine, run, [{**record_op('scoped', claim(key)), 'qualifier': qualifier}])
    identifier = draft['operations'][0]['reserved_id']
    replacement = {**record_op('cross', claim(key)), 'action': 'record_supersede', 'predecessors': [identifier]}
    with pytest.raises(MemoryError) as error:
        engine.freeze(run['run_id'], 1, [replacement])
    assert error.value.code == 'scope_mismatch'
    other = Dreaming(store, 'fixture', {**caller, 'session_id': 'other-harness-session', 'harness': 'pi'}, publisher=True)
    with pytest.raises(MemoryError) as error:
        other.materials(run['run_id'])
    assert error.value.code == 'attempt_identity_mismatch'
    configure(store, policy, lambda p: p.update(source_grants=[p['source_grants'][1]]))
    assert engine.materials(run['run_id'])['sources'] == {}
    assert store.read(owner_caller, [identifier])['items'] == []


def test_scoped_approval_same_scope_multi_predecessor_and_unknown_root(tmp_path):
    engine, store, _, owner_caller, _, *_ = environment(tmp_path)
    run, key = start_owner(engine)
    qualifier = {'scope': 'worktree', 'worktree_id': store._resolve(owner_caller)['worktree_id']}
    bad = {**record_op('bad', claim(key)), 'qualifier': {'scope': 'worktree', 'worktree_id': '0'*24}}
    with pytest.raises(MemoryError) as error:
        engine.freeze(run['run_id'], 1, [bad])
    assert error.value.code == 'scope_mismatch'
    ops = [{**record_op(name, claim(key), visibility='candidate'), 'qualifier': qualifier} for name in ('A','B')]
    created = publish(engine, run, ops)
    identifiers = [op['reserved_id'] for op in created['operations']]
    approvals = [{'id': f'approve{index}', 'action': 'record_approve', 'record_id': identifier,
                  'expected_content_digest': engine.audit(ids=[identifier])['items'][0]['content_digest'],
                  'claim': claim(key), 'review': review([key])} for index, identifier in enumerate(identifiers)]
    publish(engine, run, approvals)
    merged = {**record_op('merge', claim(key)), 'action': 'record_supersede', 'predecessors': identifiers, 'qualifier': qualifier}
    result = publish(engine, run, [merged])
    record = store.read(owner_caller, [result['operations'][0]['reserved_id']])['items'][0]
    assert record['scope'] == 'worktree' and set(record['supersedes']) == set(identifiers)



def test_v1_dream_policy_is_rejected_without_changing_v1_canonical_records(tmp_path):
    _, store, _, owner_caller, policy, owner, _ = environment(tmp_path)
    record = store.propose(owner_caller, {'scope': 'project', 'kind': 'observation', 'title': 'ordinary',
        'body': 'Canonical v1 survives policy cutover.', 'sources': [{'uri': owner.as_uri()}]}, 'ordinary-v1')['record']['id']
    old = deepcopy(policy); old['version'] = 1
    with pytest.raises(MemoryError) as error:
        configure_policy(store, old, expected_revision=_digest(policy))
    assert error.value.code == 'invalid_policy'
    assert store.read(owner_caller, [record], include_inactive=True)['items'][0]['version'] == 1


def test_selected_page_does_not_copy_unrelated_text_and_append_keeps_memory(tmp_path):
    import json
    engine, store, _, owner_caller, _, _, human = environment(tmp_path)
    unrelated = 'UNRELATED-PUBLIC-TEXT-MUST-NOT-BECOME-SOURCE-METADATA'
    with human.open('a') as stream:
        stream.write(json.dumps({'type': 'response_item', 'id': 'unrelated', 'payload': {
            'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': unrelated}]}}) + '\n')
    page = engine.source_read({'grant_id': 'human'})
    run = engine.start(sources=[page['selection']])
    key = engine.materials(run['run_id'])['sources']['human']['events'][0]['key']
    draft = publish(engine, run, [record_op('create', claim(key, level='report'))])
    identifier = draft['operations'][0]['reserved_id']
    raw = (store.root / f'records/demo/{identifier}.md').read_text()
    assert unrelated not in raw
    assert '_catalog_page' in raw and 'source_spec' in raw
    assert store.read(owner_caller, [identifier])['items'][0]['id'] == identifier
    with human.open('a') as stream:
        stream.write(json.dumps({'type': 'response_item', 'id': 'later', 'payload': {
            'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': 'Later unrelated append.'}]}}) + '\n')
    assert store.read(owner_caller, [identifier])['items'][0]['id'] == identifier
    frozen = engine.freeze(run['run_id'], 1, [record_op('new', claim(key, level='report'))])
    assert engine.publish(run['run_id'], 1, frozen['draft_revision'])['status'] == 'blocked'


def test_materialized_page_obeys_run_event_budget(tmp_path):
    import json
    engine, store, _, _, policy, _, human = environment(tmp_path)
    with human.open('a') as stream:
        stream.write(json.dumps({'type': 'response_item', 'id': 'extra', 'payload': {'type': 'message',
            'role': 'assistant', 'content': [{'type': 'output_text', 'text': 'Extra public event.'}]}}) + '\n')
    page = engine.source_read({'grant_id': 'human'})
    assert len(page['events']) == 2
    configure(store, policy, lambda p: p.update(budgets={**p['budgets'], 'events': 1}))
    run = engine.start(sources=[page['selection']])
    material = engine.materials(run['run_id'])['sources']['human']
    assert material['events'] == []
    assert material['coverage']['gaps'][0]['reason'] == 'source_budget_exhausted'


def test_catalog_revoked_target_and_revision_fenced_run_pagination(tmp_path):
    engine, store, _, _, policy, *_ = environment(tmp_path)
    policy = configure(store, policy, lambda p: p.update(target_projects=['demo', 'runner']))
    first, _ = start_owner(engine)
    second, _ = start_owner(engine, target='runner')
    page = engine.catalog(limit=1)
    assert len(page['active_runs']) == 1 and page['next_cursor']
    next_page = engine.catalog(limit=1, cursor=page['next_cursor'])
    assert {page['active_runs'][0]['id'], next_page['active_runs'][0]['id']} == {first['run_id'], second['run_id']}
    assert all('attestations' not in grant for grant in page['source_grants'])
    configure(store, policy, lambda p: p.update(target_projects=['demo']))
    current = engine.catalog()
    assert [item['id'] for item in current['active_runs']] == [first['run_id']]
    with pytest.raises(MemoryError) as error:
        engine.catalog(cursor=page['next_cursor'])
    assert error.value.code == 'stale_cursor'


@pytest.mark.parametrize('caller_method', ['propose', 'capture'])
def test_ordinary_candidate_exact_approval_preserves_payload_and_sources(tmp_path, caller_method):
    engine, store, _, owner_caller, _, owner, _ = environment(tmp_path)
    payload = {'scope': 'worktree', 'kind': 'hypothesis' if caller_method == 'capture' else 'decision',
        'title': 'Ordinary agent candidate',
        'body': 'Arbitrary ordinary Markdown.\n\nConditions and counterevidence belong to this original payload.',
        'sources': [{'uri': 'file://localhost' + str(owner)}]}
    if caller_method == 'propose':
        proposed = store.propose(owner_caller, payload, 'ordinary-reviewed')['record']
    else:
        captured = store.capture(owner_caller, payload, 'ordinary-reviewed')
        proposed = store.read(owner_caller, [captured['id']], include_inactive=True)['items'][0]
    audited = engine.audit(ids=[proposed['id']])['items'][0]
    assert audited['body'] == proposed['body']
    run, key = start_owner(engine)
    operation = {'id': 'approve', 'action': 'record_approve', 'record_id': proposed['id'],
                 'expected_content_digest': audited['content_digest'], 'claim': claim(key), 'review': review([key])}
    publish(engine, run, [operation])
    active = store.read(owner_caller, [proposed['id']])['items'][0]
    for field in ('body', 'kind', 'title', 'sources', 'content_digest', 'provenance', 'scope', 'worktree_id'):
        assert active[field] == proposed[field]
    assert active['effective_status'] == 'active'


@pytest.mark.parametrize('restriction', ['wrong_digest', 'unrelated_source', 'no_reuse', 'wrong_locator', 'retired'])
def test_ordinary_approval_retains_exact_digest_and_original_source_restrictions(tmp_path, restriction):
    from shared_memory_mcp.dreaming import add_disposition
    engine, store, _, owner_caller, _, owner, human = environment(tmp_path)
    source = {'uri': human.as_uri() if restriction == 'unrelated_source' else owner.as_uri()}
    if restriction == 'wrong_locator':
        source['locator'] = 'nonexistent-owner-location'
    proposed = store.propose(owner_caller, {'scope': 'project', 'kind': 'hypothesis', 'title': 'restricted original',
        'body': 'Original arbitrary hypothesis.', 'sources': [source]}, 'restricted-original')['record']
    run, key = start_owner(engine)
    if restriction == 'no_reuse':
        add_disposition(store, owner_caller, target='demo', topic='*', scope='research',
                        source_keys=['source-uri:' + owner.as_uri()], kind='no_reuse', reason='Fixture no reuse')
    elif restriction == 'retired':
        store.curate(owner_caller, proposed['id'], {'reason': 'Fixture retirement', 'evidence': [source]}, 'retire-candidate', retired=True)
    operation = {'id': 'approve', 'action': 'record_approve', 'record_id': proposed['id'],
                 'expected_content_digest': '0'*64 if restriction == 'wrong_digest' else proposed['content_digest'],
                 'claim': claim(key, level='hypothesis'), 'review': review([key])}
    draft = engine.freeze(run['run_id'], 1, [operation])
    result = engine.publish(run['run_id'], 1, draft['draft_revision'])
    assert result['status'] == 'blocked'
    assert result['unresolved'][0]['code'] in {'stale_record', 'unverifiable_source', 'source_forbidden', 'no_reuse'}
    assert next(r for r in store._load('demo') if r['id'] == proposed['id'])['status'] == 'candidate'


def test_collaboration_effect_binds_compact_sources_and_preserves_lifecycle(tmp_path):
    from shared_memory_mcp.dream_records import collaboration
    engine, store, _, _, _, *_ = environment(tmp_path)
    run = engine.start(sources=[{'grant_id': 'human'}])
    key = engine.materials(run['run_id'])['sources']['human']['events'][0]['key']
    c = claim(key, level='inferred', text='Synthetic inferred collaboration candidate.')
    created = publish(engine, run, [{'id': 'collab', 'action': 'collaboration_create', 'claim': c, 'review': review([key])}])
    identifier = created['operations'][0]['reserved_id']
    original = next(record for record in collaboration(store) if record['id'] == identifier)
    assert original['effective_status'] == 'candidate'
    assert original['sources'][0]['note'].startswith('dream-source-v1:')
    assert 'input_text' not in original['sources'][0]['note']
    publish(engine, run, [{'id': 'promote', 'action': 'collaboration_publish', 'record_id': identifier, 'claim': c, 'review': review([key])}])
    promoted = next(record for record in collaboration(store) if record['id'] == identifier)
    assert promoted['effective_status'] == 'active' and promoted['sources'] == original['sources']
    publish(engine, run, [{'id': 'withdraw', 'action': 'collaboration_withdraw', 'record_id': identifier, 'review': review([key])}])
    withdrawn = next(record for record in collaboration(store) if record['id'] == identifier)
    assert withdrawn['effective_status'] == 'withdrawn' and withdrawn['sources'] == original['sources']
