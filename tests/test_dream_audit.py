"""Disposable canonical-store checks for the curator audit boundary."""
import json
import pytest

from shared_memory_mcp.core import MemoryError, MemoryStore, _digest, _json
from shared_memory_mcp.dream_audit import audit_memory
from shared_memory_mcp.dream_records import collaboration_effect
from shared_memory_mcp.dreaming import DISPOSITIONS


@pytest.fixture
def env(tmp_path):
    project = tmp_path / 'project'; project.mkdir()
    other = tmp_path / 'other'; other.mkdir()
    store = MemoryStore(tmp_path / 'store'); store.init()
    store.register('demo', [project]); store.register('other', [other])
    caller = {'cwd': str(project), 'harness': 'codex', 'session_id': 'audit-fixture', 'actor': 'auditor'}
    profile = {'target_projects': ['demo'], 'source_grants': []}
    return store, caller, profile


def create(env, name, *, scope='project', body='original', expires=None):
    store, caller, _ = env
    record = {'kind': 'observation', 'title': name, 'body': body, 'scope': scope,
              'sources': [{'uri': 'file:///synthetic/evidence'}]}
    if expires: record['expires_at'] = expires
    return store.propose({**caller, 'task_id': name}, record, 'proposal-' + name)['record']['id']


def promote(env, id):
    store, caller, _ = env
    store.promote(caller, id, {'reason': 'fixture review', 'evidence': [{'uri': 'file:///synthetic/review'}]}, 'promote-' + id)


def test_all_qualifiers_lifecycle_and_original_provenance(env):
    store, caller, profile = env
    candidate = create(env, 'candidate')
    active = create(env, 'active'); promote(env, active)
    task = create(env, 'task', scope='task')
    worktree = create(env, 'worktree', scope='worktree')
    expired = create(env, 'expired', expires='2000-01-01T00:00:00Z')
    retired = create(env, 'retired'); promote(env, retired)
    review = {'reason': 'retirement fixture', 'evidence': [{'uri': 'file:///synthetic/review'}]}
    store.curate(caller, retired, review, 'curation', retired=True, details={'summary': 'preserved'})
    withdrawn = create(env, 'withdrawn'); promote(env, withdrawn)
    store.delete(caller, withdrawn, review, 'withdraw')
    old = create(env, 'old'); promote(env, old)
    new = create(env, 'new')
    store.supersede(caller, new, [old], review, 'supersession')
    result = audit_memory(store, profile, target_project='demo', max_chars=100000)
    records = {r['id']: r for r in result['items']}
    assert {candidate, active, task, worktree, expired, retired, withdrawn, old, new} <= records.keys()
    assert records[task]['task_id'] == 'task'
    assert records[old]['effective_status'] == 'superseded'
    assert records[withdrawn]['effective_status'] == 'withdrawn'
    assert records[expired]['effective_status'] == 'expired'
    assert records[retired]['lifecycle_status'] == 'active' and records[retired]['recall_retired']
    assert records[retired]['curation_audit'][0]['payload']['context']['cwd'] == caller['cwd']
    assert records[active]['promotion'] and records[active]['review']['reviewer']['cwd'] == caller['cwd']
    assert records[active]['usability']['usable'] and not records[candidate]['usability']['usable']
    assert store.read(caller, [task], include_inactive=True)['items'] == []


def test_denied_target_and_cursor_filter_binding(env):
    store, _, profile = env
    create(env, 'one'); create(env, 'two')
    with pytest.raises(MemoryError) as error:
        audit_memory(store, profile, target_project='other')
    assert error.value.code == 'target_forbidden'
    page = audit_memory(store, profile, target_project='demo', limit=1)
    for changes in [{'query': 'one'}, {'collection': 'collaboration'}, {'statuses': ['active']}, {'scopes': ['task']}, {'ids': [page['items'][0]['id']]}]:
        with pytest.raises(MemoryError) as error:
            audit_memory(store, profile, target_project='demo', cursor=page['next_cursor'], limit=1, **changes)
        assert error.value.code == 'invalid_cursor'


def test_curation_and_corpus_changes_reject_continuation(env):
    store, caller, profile = env
    id = create(env, 'one'); create(env, 'two')
    page = audit_memory(store, profile, target_project='demo', limit=1)
    store.curate(caller, id, {'reason': 'fixture', 'evidence': [{'uri': 'file:///synthetic/review'}]}, 'changed', details={'summary': 'new'})
    with pytest.raises(MemoryError) as error:
        audit_memory(store, profile, target_project='demo', cursor=page['next_cursor'], limit=1)
    assert error.value.code == 'stale_audit'


def test_no_reuse_inspectable_but_not_recalled(env):
    store, caller, profile = env
    id = create(env, 'blocked'); promote(env, id)
    payload = {'target': 'demo', 'topic': '*', 'scope': 'research', 'source_keys': ['source-uri:file:///synthetic/evidence'],
               'kind': 'no_reuse', 'reason': 'synthetic prohibition', 'executor': caller}
    ledger = {'version': 1, 'items': [{**payload, 'id': _digest(payload), 'at': '2026-10-07T00:00:00Z'}]}
    with store._gate(): store._publish(store.root / DISPOSITIONS, (_json(ledger) + '\n').encode())
    record = audit_memory(store, profile, target_project='demo', ids=[id])['items'][0]
    assert record['body'] == 'original' and not record['usability']['usable']
    assert record['usability']['restrictions']
    assert store.read(caller, [id], include_inactive=True)['items'] == []


def test_large_record_reconstructs_without_drop(env):
    store, _, profile = env
    id = create(env, 'large', body='长' * 9000)
    parts, cursor, offsets = [], None, []
    for _ in range(200):
        page = audit_memory(store, profile, target_project='demo', ids=[id], max_chars=400, cursor=cursor)
        item = page['items'][0]
        parts.append(item['content_slice']); offsets.append(item['offset'])
        cursor = page['next_cursor']
        if cursor is None: break
    assert cursor is None and offsets == sorted(set(offsets))
    decoded = json.loads(''.join(parts))
    assert decoded['id'] == id and decoded['body'] == '长' * 9000 and decoded['proposal']
    assert decoded['provenance']['session_id'] == 'audit-fixture'


def test_collaboration_explicit_collection_and_target_filter(env):
    store, caller, profile = env
    ids = []
    for target in ['demo', 'other']:
        claim = {'topic': target, 'text': 'fixture preference', 'level': 'inferred', 'conditions': 'fixture only',
                 'exceptions': [], 'counterevidence': [], 'scenarios': ['research'], 'projects': [target],
                 'refs': ['source:event'], 'risks': []}
        operation = {'action': 'collaboration_create', 'reserved_id': _digest(target)[:32], 'claim': claim,
                     'key': target, 'digest': _digest(claim), 'review': {'decision': 'approve', 'reason': 'fixture',
                     'scope_checked': True, 'counterexamples_checked': True, 'checked_refs': claim['refs']}}
        with store._gate():
            path, data = collaboration_effect(store, operation, caller)
            store._publish(store.root / path, data)
        ids.append(operation['reserved_id'])
    assert audit_memory(store, profile, target_project='demo')['items'] == []
    records = audit_memory(store, profile, target_project='demo', collection='collaboration')['items']
    assert [r['id'] for r in records] == ids[:1] and records[0]['events']


def test_revoked_grant_keeps_audit_content_but_denies_source_and_reuse(env, tmp_path):
    from shared_memory_mcp.dream_catalog import SourceCatalog
    from shared_memory_mcp.dreaming import POLICY
    store, caller, _ = env
    source = tmp_path / 'owner.txt'; source.write_text('fixture source')
    replacement = tmp_path / 'replacement.txt'; replacement.write_text('different source')
    grant = {'id': 'owner', 'kind': 'file', 'path': str(source), 'format': 'document', 'schema': 'document-v1'}
    profile = {'target_projects': ['demo'], 'source_grants': [grant]}
    spec = SourceCatalog(store, 'audit', profile).resolve()[0]
    binding = {'profile': 'audit', 'source_id': spec['id'], 'source_spec': spec,
               'source_grant': _digest(spec), 'event_key': 'fixture-event', 'lineage': []}
    record = {'kind': 'observation', 'title': 'bound-source', 'body': 'retained original', 'scope': 'project',
              'sources': [{'uri': source.as_uri(), 'note': 'dream-source-v1:' + _json(binding)}]}
    id = store.propose(caller, record, 'bound-source')['record']['id']; promote(env, id)
    def policy(profile):
        with store._gate():
            store._publish(store.root / POLICY, (_json({'version': 2, 'profiles': {'audit': profile}}) + '\n').encode())
    policy(profile)
    assert audit_memory(store, profile, target_project='demo')['items'][0]['usability']['usable']
    changed = {**profile, 'source_grants': [{**grant, 'id': 'replacement', 'path': str(replacement)}]}
    policy(changed)
    record = audit_memory(store, changed, target_project='demo')['items'][0]
    assert record['body'] == 'retained original' and not record['usability']['usable']
    assert store.read(caller, [id], include_inactive=True)['items'] == []
    with pytest.raises(MemoryError):
        SourceCatalog(store, 'audit', changed).read({'grant_id': 'owner'})


def test_restriction_change_fences_page_and_missing_ids_are_explicit(env):
    from shared_memory_mcp.dreaming import POLICY
    store, _, profile = env
    create(env, 'one'); create(env, 'two')
    page = audit_memory(store, profile, target_project='demo', limit=1)
    with store._gate(): store._publish(store.root / POLICY, (_json({'version': 2, 'profiles': {'audit': profile}}) + '\n').encode())
    with pytest.raises(MemoryError) as error:
        audit_memory(store, profile, target_project='demo', limit=1, cursor=page['next_cursor'])
    assert error.value.code == 'stale_audit'
    result = audit_memory(store, profile, target_project='demo', ids=['0' * 32])
    assert result['missing_ids'] == ['0' * 32] and result['items'] == []


def test_malformed_cursor_and_source_binding_fail_closed(env):
    import base64
    store, caller, profile = env
    record = {'kind': 'observation', 'title': 'malformed', 'body': 'inspectable', 'scope': 'project',
              'sources': [{'uri': 'file:///synthetic/evidence', 'note': 'dream-source-v1:not-json'}]}
    id = store.propose(caller, record, 'malformed')['record']['id']; promote(env, id)
    item = audit_memory(store, profile, target_project='demo')['items'][0]
    assert item['body'] == 'inspectable' and not item['usability']['usable']
    assert {'kind': 'invalid_source_binding'} in item['usability']['restrictions']
    for cursor in ['invalid!', base64.urlsafe_b64encode(b'not-json').decode()]:
        with pytest.raises(MemoryError) as error:
            audit_memory(store, profile, target_project='demo', cursor=cursor)
        assert error.value.code == 'invalid_cursor'


def test_collaboration_dependency_retirement_is_visible_and_unusable(env):
    store, caller, profile = env
    id = create(env, 'dependency'); promote(env, id)
    claim = {'topic': 'dependent', 'text': 'fixture preference', 'level': 'inferred', 'conditions': 'fixture only',
             'exceptions': [], 'counterevidence': [], 'scenarios': ['research'], 'projects': ['demo'],
             'refs': ['record:' + id], 'risks': []}
    cid = '1' * 32
    review = {'decision': 'approve', 'reason': 'fixture', 'scope_checked': True,
              'counterexamples_checked': True, 'checked_refs': claim['refs']}
    for action, key in [('collaboration_create', 'create'), ('collaboration_publish', 'publish')]:
        operation = {'action': action, 'reserved_id': cid, 'record_id': cid, 'claim': claim,
                     'key': key, 'digest': _digest([claim, action]), 'review': review}
        with store._gate():
            path, data = collaboration_effect(store, operation, caller)
            store._publish(store.root / path, data)
    item = audit_memory(store, profile, target_project='demo', collection='collaboration')['items'][0]
    assert item['effective_status'] == 'active' and item['usability']['usable']
    store.curate(caller, id, {'reason': 'fixture', 'evidence': [{'uri': 'file:///synthetic/review'}]}, 'retire-dependency', retired=True)
    item = audit_memory(store, profile, target_project='demo', collection='collaboration')['items'][0]
    assert item['effective_status'] == 'active' and not item['usability']['usable']
    assert {'kind': 'dependency_unusable', 'reference': 'record:' + id} in item['usability']['restrictions']
    assert len(item['events']) == 2 and item['claim'] == claim


def test_filters_are_exact_and_retired_is_not_active(env):
    store, caller, profile = env
    active = create(env, 'matching-active'); promote(env, active)
    retired = create(env, 'matching-retired'); promote(env, retired)
    store.curate(caller, retired, {'reason': 'fixture', 'evidence': [{'uri': 'file:///synthetic/review'}]}, 'retire-filter', retired=True)
    create(env, 'matching-task', scope='task')
    filtered = audit_memory(store, profile, target_project='demo', query='matching', statuses=['active'], scopes=['project'])
    assert [r['id'] for r in filtered['items']] == [active]
    result = audit_memory(store, profile, target_project='demo', statuses=['retired'])
    assert [r['id'] for r in result['items']] == [retired] and result['items'][0]['lifecycle_status'] == 'active'


def test_current_policy_revocation_fails_under_backend_gate(env):
    from shared_memory_mcp.dreaming import POLICY
    store, _, profile = env
    create(env, 'retained')
    with store._gate():
        store._publish(store.root / POLICY, (_json({'version': 2, 'profiles': {}}) + '\n').encode())
    with pytest.raises(MemoryError) as error:
        audit_memory(store, profile, target_project='demo')
    assert error.value.code == 'stale_profile'


@pytest.mark.parametrize('prohibition', ['source_id', 'uri', 'lineage'])
def test_published_collaboration_source_bindings_enforce_no_reuse(tmp_path, prohibition):
    from dreaming_helpers import environment, begin, claim, review, freeze_publish
    from shared_memory_mcp.dreaming import add_disposition, configure_policy
    engine, store, caller, _, policy, _, human = environment(tmp_path)
    previous = _digest(policy)
    policy['profiles']['fixture']['source_grants'][1]['lineage'] = ['lineage:audit-fixture']
    configure_policy(store, policy, expected_revision=previous)
    run, generation, _, human_key = begin(engine)
    c = claim(human_key, level='explicit')
    frozen, result = freeze_publish(engine, run, generation, [{'id': 'C', 'action': 'collaboration_create',
        'claim': c, 'review': review(c['refs'])}])
    assert result['status'] == 'applied'
    id = frozen['operations'][0]['reserved_id']
    item = engine.audit(target_project='demo', collection='collaboration', ids=[id])['items'][0]
    assert item['usability']['usable']
    source_key = {'source_id': 'source:human', 'uri': 'source-uri:' + human.as_uri(),
                  'lineage': 'lineage:audit-fixture'}[prohibition]
    add_disposition(store, caller, target='demo', topic='*', scope='collaboration',
                    source_keys=[source_key], kind='no_reuse', reason='synthetic collaboration ban')
    item = engine.audit(target_project='demo', collection='collaboration', ids=[id])['items'][0]
    assert not item['usability']['usable']
    assert any(r['kind'] == 'no_reuse' for r in item['usability']['restrictions'])
    assert item['claim'] == c and item['body'] and item['events'] and item['sources']
    assert engine.materials(run)['sources']['human']['events'] == []
    with store._gate(), pytest.raises(MemoryError) as error:
        engine._admit(engine._run(run), c, review(c['refs']), scope='collaboration')
    assert error.value.code == 'source_forbidden'


def test_legacy_direct_collaboration_event_is_unknown_without_binding(env):
    store, caller, profile = env
    claim = {'topic': 'old-direct-event', 'text': 'fixture preference', 'level': 'explicit', 'conditions': 'fixture only',
             'exceptions': [], 'counterevidence': [], 'scenarios': ['research'], 'projects': ['demo'],
             'refs': ['f' * 64], 'risks': []}
    operation = {'action': 'collaboration_create', 'reserved_id': '2' * 32, 'claim': claim,
                 'key': 'legacy', 'digest': _digest(claim), 'review': {'decision': 'approve', 'reason': 'fixture',
                 'scope_checked': True, 'counterexamples_checked': True, 'checked_refs': claim['refs']}}
    with store._gate():
        path, data = collaboration_effect(store, operation, caller)
        store._publish(store.root / path, data)
    item = audit_memory(store, profile, target_project='demo', collection='collaboration')['items'][0]
    assert item['claim'] == claim and item['effective_status'] == 'active'
    assert not item['usability']['usable']
    assert {'kind': 'source_binding_unknown', 'references': claim['refs']} in item['usability']['restrictions']


def test_collaboration_grant_revocation_and_collection_specific_dispositions(tmp_path):
    from dreaming_helpers import environment, begin, claim, review, freeze_publish
    from shared_memory_mcp.dreaming import add_disposition, configure_policy
    engine, store, caller, _, policy, _, human = environment(tmp_path)
    run, generation, _, human_key = begin(engine)
    c = claim(human_key, level='explicit')
    frozen, result = freeze_publish(engine, run, generation, [{'id': 'C', 'action': 'collaboration_create',
        'claim': c, 'review': review(c['refs'])}])
    assert result['status'] == 'applied'
    id = frozen['operations'][0]['reserved_id']
    add_disposition(store, caller, target='demo', topic='*', scope='research',
                    source_keys=['source-uri:' + human.as_uri()], kind='no_reuse', reason='synthetic research-only ban')
    item = engine.audit(target_project='demo', collection='collaboration', ids=[id])['items'][0]
    assert item['usability']['usable']
    previous = _digest(policy)
    policy['profiles']['fixture']['source_grants'] = policy['profiles']['fixture']['source_grants'][:1]
    configure_policy(store, policy, expected_revision=previous)
    item = engine.audit(target_project='demo', collection='collaboration', ids=[id])['items'][0]
    assert item['claim'] == c and item['body'] and item['sources']
    assert not item['usability']['usable']
    assert any(r['kind'] == 'source_forbidden' for r in item['usability']['restrictions'])
    with pytest.raises(MemoryError):
        engine.source_read({'grant_id': 'human'})
