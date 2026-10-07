"""Consequential denial, crash and incremental boundaries on real disposable stores."""
from copy import deepcopy
import hashlib
import json
import os

import pytest

from dreaming_helpers import environment, begin, claim, record_op, review, view_op, freeze_publish
from shared_memory_mcp.core import MemoryError, _digest
from shared_memory_mcp.dreaming import Dreaming, configure_policy, add_disposition
from shared_memory_mcp.dream_sources import read_source


def mark_all(engine, run_id, generation):
    keys = [e['key'] for material in engine.materials(run_id)['sources'].values() for e in material['events']]
    engine.mark_processed(run_id, generation, {k: 'processed' for k in keys})


def set_policy(store, old, change):
    policy = deepcopy(old)
    change(policy['profiles']['fixture'])
    configure_policy(store, policy, expected_revision=_digest(old))
    return policy


@pytest.mark.parametrize('action', ['record_approve', 'collaboration_publish', 'record_supersede', 'view_publish', 'record_withdraw'])
def test_active_actions_cannot_bypass_admission_with_candidate_visibility(tmp_path, action):
    engine, store, *_ = environment(tmp_path)
    rid, gen, source, _ = begin(engine)
    op = {'id': 'bypass', 'action': action, 'visibility': 'candidate', 'record_id': 'a' * 32,
          'claim': claim(source), 'review': review([source], decision='pending')}
    with pytest.raises(MemoryError) as error:
        engine.freeze(rid, gen, [op])
    assert error.value.code == 'invalid_input'
    assert store._load('demo') == []


@pytest.mark.parametrize('change', ['path', 'attestation', 'derived'])
def test_changed_source_grant_cannot_replay_cached_excerpt_or_old_draft(tmp_path, change):
    engine, store, _, _, policy, owner, _ = environment(tmp_path)
    rid, gen, key, _ = begin(engine)
    frozen = engine.freeze(rid, gen, [record_op('A', claim(key))])
    def alter(profile):
        source = profile['source_grants'][0]
        if change == 'path':
            source['path'] = str(owner.with_name('unrelated.md'))
        elif change == 'attestation':
            source['attestations'] = {'0' * 64: {'subject': 'Pein', 'basis': 'Different fixture grant'}}
        else:
            source['derived'] = True
    set_policy(store, policy, alter)
    with pytest.raises(MemoryError):
        engine.materials(rid, 'owner')
    assert 'owner' not in engine.materials(rid)['sources']
    assert engine.candidate_diff(rid, frozen['draft_revision'])['operations'] == []
    result = engine.publish(rid, gen, frozen['draft_revision'])
    assert result['status'] == 'blocked' and store._load('demo') == []


def test_profile_target_change_never_retargets_an_existing_run(tmp_path):
    engine, store, _, _, policy, *_ = environment(tmp_path)
    rid, gen, key, _ = begin(engine)
    set_policy(store, policy, lambda p: p.update(target_projects=['runner']))
    for action in (lambda: engine.materials(rid), lambda: engine.freeze(rid, gen, [record_op('X', claim(key))])):
        with pytest.raises(MemoryError) as error:
            action()
        assert error.value.code == 'dream_access_denied'
    assert store._load('demo') == store._load('runner') == []


def test_no_effect_intent_can_be_explicitly_abandoned_after_revocation(tmp_path, monkeypatch):
    engine, store, _, _, policy, *_ = environment(tmp_path)
    rid, gen, key, _ = begin(engine)
    frozen = engine.freeze(rid, gen, [record_op('A', claim(key))])
    def crash(point, operation):
        if point == 'intent-saved':
            raise RuntimeError('fixture interruption')
    monkeypatch.setattr(engine, '_fault', crash)
    with pytest.raises(RuntimeError):
        engine.publish(rid, gen, frozen['draft_revision'])
    set_policy(store, policy, lambda p: p.update(actions=[]))
    result = engine.publish(rid, gen, frozen['draft_revision'])
    assert result['status'] == 'blocked'
    assert engine.close(rid, gen, abandon_reason='Fixture revoked grant, proven no canonical effect')['partial']
    assert store._load('demo') == []


def test_reserved_withdrawal_id_cannot_overwrite_an_earlier_record(tmp_path):
    engine, store, *_ = environment(tmp_path)
    rid, gen, key, _ = begin(engine)
    frozen, _ = freeze_publish(engine, rid, gen, [record_op('A', claim(key)), record_op('B', claim(key))])
    target = frozen['operations'][1]['reserved_id']
    before = {p.name: p.read_bytes() for p in (store.root / 'records/demo').glob('*.md')}
    op = {'id': 'A', 'action': 'record_withdraw', 'record_id': target, 'review': review([key])}
    _, result = freeze_publish(engine, rid, gen, [op])
    assert result['status'] == 'blocked' and result['unresolved'][0]['code'] == 'id_collision'
    assert {p.name: p.read_bytes() for p in (store.root / 'records/demo').glob('*.md')} == before


@pytest.mark.parametrize('mutation', ['curation', 'lifecycle', 'predecessor'])
def test_changed_canonical_basis_blocks_publication(tmp_path, mutation):
    engine, store, _, owner_caller, _, owner, _ = environment(tmp_path)
    rid, gen, key, _ = begin(engine)
    initial, _ = freeze_publish(engine, rid, gen, [record_op('old', claim(key))])
    old = initial['operations'][0]['reserved_id']
    op = {**record_op('next', claim(key)), 'action': 'record_supersede', 'predecessors': [old]}
    frozen = engine.freeze(rid, gen, [op])
    audit = {'reason': 'Fixture owner correction', 'evidence': [{'uri': owner.as_uri()}]}
    if mutation == 'curation':
        store.curate(owner_caller, old, audit, 'external-curation', details={'conditions': 'Changed applicability'})
    elif mutation == 'lifecycle':
        store.curate(owner_caller, old, audit, 'external-retire', retired=True)
    else:
        store.delete(owner_caller, old, audit, 'external-withdraw')
    before = {p.name: p.read_bytes() for p in (store.root / 'records/demo').glob('*.md')}
    result = engine.publish(rid, gen, frozen['draft_revision'])
    assert result['status'] == 'blocked' and result['unresolved'][0]['code'] == 'stale_basis'
    assert {p.name: p.read_bytes() for p in (store.root / 'records/demo').glob('*.md')} == before


def test_rejected_backfill_stays_blocked_and_new_evidence_can_only_reopen_candidate(tmp_path):
    engine, store, caller, _, _, owner, _ = environment(tmp_path)
    rid, gen, key, _ = begin(engine)
    add_disposition(store, caller, target='demo', topic='fixture-coverage', scope='research',
                    source_keys=[key], kind='user_rejected', reason='Synthetic rejection')
    _, result = freeze_publish(engine, rid, gen, [record_op('bad', claim(key))])
    assert result['unresolved'][0]['code'] == 'blocked_disposition'
    engine.close(rid, gen, abandon_reason='Rejected fixture statement')
    owner.write_text('New fixture owner version reports an independent contrary observation.\n')
    rid, gen, new_key, _ = begin(engine)
    _, result = freeze_publish(engine, rid, gen, [record_op('active', claim(new_key)), record_op('candidate', claim(new_key), visibility='candidate')])
    assert result['status'] == 'partial'
    assert result['unresolved'][0]['code'] == 'reopen_candidate_only'
    assert [r['status'] for r in store._load('demo')] == ['candidate']


def test_source_alias_change_does_not_evade_no_reuse(tmp_path):
    engine, store, caller, _, policy, *_ = environment(tmp_path)
    rid, gen, key, _ = begin(engine)
    add_disposition(store, caller, target='demo', topic='*', scope='research', source_keys=['source:owner'],
                    kind='no_reuse', reason='Synthetic source-level prohibition')
    # Close without claiming a new baseline, then change only the administrative alias.
    engine.close(rid, gen, abandon_reason='Fixture source prohibited')
    set_policy(store, policy, lambda p: p['source_grants'][0].update(id='renamed-owner'))
    run = engine.start(reconsider='Explicit fixture backfill, not permission to override disposition')
    assert engine.materials(run['run_id'])['sources']['renamed-owner']['events'] == []


def test_run_backfill_reads_next_batch_and_then_append_without_reprocessing(tmp_path):
    engine, store, _, _, policy, _, human = environment(tmp_path)
    header, original = human.read_text().splitlines()
    message = json.loads(original)
    events = []
    for i in range(5):
        entry = deepcopy(message); entry['id'] = 'event-' + str(i)
        events.append(entry)
    human.write_text(header + '\n' + ''.join(json.dumps(x) + '\n' for x in events))
    policy = set_policy(store, policy, lambda p: p.update(source_grants=[p['source_grants'][1]], budgets={**p['budgets'], 'events': 2}))
    before, meta = human.read_bytes(), human.stat()
    seen = []
    for _ in range(3):
        run = engine.start(); rid, gen = run['run_id'], run['generation']
        material = engine.materials(rid)['sources']['human']
        seen.extend(e['event_id'] for e in material['events'])
        mark_all(engine, rid, gen); engine.close(rid, gen)
    assert seen == ['event-0', 'event-1', 'event-2', 'event-3', 'event-4']
    assert engine.start()['status'] == 'no-change'
    assert human.read_bytes() == before and human.stat().st_mtime_ns == meta.st_mtime_ns
    entry = deepcopy(message); entry['id'] = 'new-event'
    with human.open('a') as stream:
        stream.write(json.dumps(entry) + '\n')
    run = engine.start()
    assert [e['event_id'] for e in engine.materials(run['run_id'])['sources']['human']['events']] == ['new-event']


def test_byte_boundary_retries_whole_event_and_excludes_analysis_channel(tmp_path):
    _, _, _, _, policy, _, human = environment(tmp_path)
    spec = {k: v for k, v in policy['profiles']['fixture']['source_grants'][1].items() if k != 'kind'}
    data = human.read_bytes(); header_size = data.index(b'\n') + 1
    first = read_source(spec, max_bytes=header_size + 12)
    assert first['cursor']['offset'] == header_size
    second = read_source(spec, cursor=first['cursor'])
    assert len(second['events']) == 1 and second['events'][0]['event_id'] == 'human-1'
    private = {'type': 'response_item', 'id': 'private', 'payload': {'type': 'message', 'role': 'assistant',
               'channel': 'analysis', 'content': [{'type': 'output_text', 'text': 'PRIVATE_REASONING'}]}}
    with human.open('a') as stream:
        stream.write(json.dumps(private) + '\n')
    assert 'PRIVATE_REASONING' not in json.dumps(read_source(spec)['events'])


def test_close_checkpoint_crash_recovers_without_new_model_work(tmp_path, monkeypatch):
    engine, _, *_ = environment(tmp_path)
    rid, gen, _, _ = begin(engine); mark_all(engine, rid, gen)
    def crash(point, operation):
        if point == 'run-closed':
            raise RuntimeError('close interruption')
    monkeypatch.setattr(engine, '_fault', crash)
    with pytest.raises(RuntimeError):
        engine.close(rid, gen)
    assert engine.start()['status'] == 'no-change'


def test_repair_and_elapsed_budgets_are_enforced_before_effect(tmp_path, monkeypatch):
    engine, store, _, _, policy, *_ = environment(tmp_path)
    set_policy(store, policy, lambda p: p['budgets'].update(repair_rounds=1))
    rid, gen, key, _ = begin(engine)
    freeze_publish(engine, rid, gen, [record_op('A', claim(key))])
    freeze_publish(engine, rid, gen, [record_op('B', claim(key))])
    with pytest.raises(MemoryError) as error:
        engine.freeze(rid, gen, [record_op('C', claim(key))])
    assert error.value.code == 'draft_limit' and len(store._load('demo')) == 2
    import shared_memory_mcp.dreaming as module
    monkeypatch.setattr(module, '_now', lambda: '2099-01-01T00:00:00Z')
    with pytest.raises(MemoryError) as error:
        engine.suggest_issue(rid, gen, topic='X', relation='owner', note='fixture', observations={})
    assert error.value.code == 'run_budget_exhausted'


def test_report_cannot_be_laundered_as_recorded_through_view(tmp_path):
    engine, store, *_ = environment(tmp_path)
    rid, gen, key, _ = begin(engine)
    _, result = freeze_publish(engine, rid, gen, [record_op('report', claim(key, level='report')), view_op('V', claim('op:report'))])
    assert result['status'] == 'partial' and result['unresolved'][0]['code'] == 'evidence_upgrade'
    assert engine.overview('research', scenario='research')['status'] == 'navigation'


def test_budget_skipped_source_is_not_claimed_unchanged(tmp_path):
    engine, store, _, _, policy, *_ = environment(tmp_path)
    set_policy(store, policy, lambda p: p['budgets'].update(events=1))
    for _ in range(4):
        run = engine.start()
        assert run['status'] != 'no-change'
        if run['status'] == 'blocked':
            assert run['model_required'] is False and run['unchecked_sources']
            break
        mark_all(engine, run['run_id'], run['generation'])
        engine.close(run['run_id'], run['generation'])


def test_issue_pending_then_review_does_not_lose_first_notification(tmp_path):
    engine, *_ = environment(tmp_path)
    rid, gen, _, _ = begin(engine)
    args = {'topic': 'fixture', 'relation': 'owner', 'note': 'Review this stable issue.', 'observations': {'revision': 'one'}}
    assert not engine.suggest_issue(rid, gen, **args)['notify']
    assert engine.suggest_issue(rid, gen, **args, semantic_reviewed=True)['notify']
    assert not engine.suggest_issue(rid, gen, **args, semantic_reviewed=True)['notify']


def test_uri_no_use_also_hides_existing_untagged_records_without_rewriting(tmp_path):
    engine, store, caller, owner_caller, _, owner, _ = environment(tmp_path)
    record = {'kind': 'observation', 'scope': 'project', 'title': 'fixture-coverage',
              'body': 'Legacy fixture source report.', 'sources': [{'uri': owner.as_uri()}]}
    proposal = store.propose(owner_caller, record, 'legacy-fixture')['record']
    audit = {'reason': 'Fixture review', 'evidence': record['sources']}
    store.promote(owner_caller, proposal['id'], audit, 'legacy-publish')
    path = store.root / 'records/demo' / (proposal['id'] + '.md')
    before = path.read_bytes()
    assert store.read(owner_caller, [proposal['id']])['items']
    add_disposition(store, caller, target='demo', topic='*', scope='research', source_keys=['source:owner'],
                    kind='no_reuse', reason='Synthetic URI-level privacy prohibition')
    assert store.read(owner_caller, [proposal['id']], include_inactive=True)['items'] == []
    assert path.read_bytes() == before


@pytest.mark.parametrize('disposition_form', ['source-id', 'localhost', 'percent-encoded'])
def test_uri_no_use_matches_local_file_identity_on_both_sides(tmp_path, disposition_form):
    engine, store, caller, owner_caller, _, owner, _ = environment(tmp_path)
    aliases = [owner.as_uri(), 'file://localhost' + str(owner), owner.as_uri().replace('owner.md', '%6fwner.md')]
    uris = aliases + ['file://remote-host' + str(owner)]
    ids, before = [], {}
    for index, uri in enumerate(uris):
        record = {'kind': 'observation', 'scope': 'project', 'title': 'fixture-coverage',
                  'body': 'Synthetic legacy source report.', 'sources': [{'uri': uri}]}
        identifier = store.propose(owner_caller, record, f'alias-{index}')['record']['id']
        store.promote(owner_caller, identifier, {'reason': 'Fixture review', 'evidence': record['sources']}, f'publish-{index}')
        ids.append(identifier)
        path = store.root / 'records/demo' / (identifier + '.md')
        before[path] = path.read_bytes()
    key = 'source:owner' if disposition_form == 'source-id' else 'source-uri:' + aliases[1 if disposition_form == 'localhost' else 2]
    add_disposition(store, caller, target='demo', topic='*', scope='research', source_keys=[key],
                    kind='no_reuse', reason='Synthetic source-use prohibition')
    for include_inactive in (False, True):
        result = store.read(owner_caller, ids, include_inactive=include_inactive)
        assert [item['id'] for item in result['items']] == [ids[-1]]
    run = engine.start()
    assert engine.materials(run['run_id'])['sources']['owner']['events'] == []
    assert all(path.read_bytes() == data for path, data in before.items())


@pytest.mark.parametrize('settlement', ['partial-close', 'reviewed-replacement'])
def test_receipt_recovery_preserves_external_promotion_and_review_fence(tmp_path, monkeypatch, settlement):
    engine, store, caller, owner_caller, _, owner, _ = environment(tmp_path)
    rid, gen, key, _ = begin(engine)
    frozen = engine.freeze(rid, gen, [record_op('A', claim(key), visibility='candidate'), record_op('B', claim(key))])
    def crash(point, operation):
        if point == 'effect-0-written':
            raise RuntimeError('receipt interruption')
    monkeypatch.setattr(engine, '_fault', crash)
    with pytest.raises(RuntimeError):
        engine.publish(rid, gen, frozen['draft_revision'])
    identifier = frozen['operations'][0]['reserved_id']
    store.promote(owner_caller, identifier, {'reason': 'Independent review', 'evidence': [{'uri': owner.as_uri()}]}, 'external-promotion')
    path = store.root / 'records/demo' / (identifier + '.md')
    promoted_bytes = path.read_bytes()
    resumed = Dreaming(store, 'fixture', {**caller, 'harness': 'pi', 'session_id': 'fixture-executor-B'}, publisher=True)
    resumed.takeover(rid, gen)
    result = resumed.publish(rid, 2, frozen['draft_revision'])
    assert result['status'] == 'partial'
    assert len(result['applied']) == 1 and result['applied'][0]['replayed']
    receipt = result['applied'][0]
    assert receipt['executor'] == engine.caller and receipt['acknowledged_by'] == resumed.caller
    assert [(e['operation_id'], e['code']) for e in result['unresolved']] == [('B', 'stale_basis')]
    assert path.read_bytes() == promoted_bytes and len(store._load('demo')) == 1
    if settlement == 'partial-close':
        closed = resumed.close(rid, 2, abandon_reason='Reviewed external promotion; preserve it and abandon B')
        assert closed['partial'] and resumed.start()['status'] != 'resume-required'
    else:
        _, result = freeze_publish(resumed, rid, 2, [record_op('C', claim(key))], reconsider_reason='Reviewed external promotion and revised remaining work')
        assert result['status'] == 'applied' and len(store._load('demo')) == 2
    assert path.read_bytes() == promoted_bytes


@pytest.mark.parametrize('changed_binding', ['proposal-key', 'proposal-digest', 'provenance'])
def test_same_content_does_not_prove_another_candidate_create_effect(tmp_path, monkeypatch, changed_binding):
    engine, store, _, owner_caller, _, owner, _ = environment(tmp_path)
    rid, gen, key, _ = begin(engine)
    frozen = engine.freeze(rid, gen, [record_op('A', claim(key), visibility='candidate')])
    def crash(point, operation):
        if point == 'effect-0-written':
            raise RuntimeError('receipt interruption')
    monkeypatch.setattr(engine, '_fault', crash)
    with pytest.raises(RuntimeError):
        engine.publish(rid, gen, frozen['draft_revision'])
    identifier = frozen['operations'][0]['reserved_id']
    store.promote(owner_caller, identifier, {'reason': 'Fixture review', 'evidence': [{'uri': owner.as_uri()}]}, 'external-promotion')
    record = store._load('demo')[0]
    original_digest = record['content_digest']
    if changed_binding == 'provenance':
        record['provenance']['session_id'] = 'different-author'
    else:
        record['proposal']['key' if changed_binding == 'proposal-key' else 'digest'] = '0' * 64
    store._write(record)  # Disposable adversarial fixture: same content, different operation binding.
    assert store._load('demo')[0]['content_digest'] == original_digest
    monkeypatch.setattr(engine, '_fault', lambda *args: None)
    result = engine.publish(rid, gen, frozen['draft_revision'])
    assert result['status'] == 'blocked' and result['applied'] == []
    assert engine.inspect(rid)['receipts'] == {}
