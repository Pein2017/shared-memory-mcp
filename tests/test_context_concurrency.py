"""Current access and explicit corrections are fenced independently of source drift."""
from copy import deepcopy
import json

import pytest
from shared_memory_mcp.core import MemoryError, _digest
from shared_memory_mcp.dreaming import configure_policy
from dreaming_helpers import environment, begin, claim, view_op, freeze_publish, record_op
from test_task_aware_slice import publish_account, correction_input


def test_background_does_not_reread_all_original_sources(tmp_path, monkeypatch):
    import shared_memory_mcp.dream_views as views
    engine, store, _, caller, _, _, _ = environment(tmp_path)
    publish_account(engine)
    def unexpected(*args):
        raise AssertionError('Ordinary as-of background must not reread the original corpus')
    monkeypatch.setattr(views, 'check_snapshot', unexpected)
    packet = store.context(caller)
    assert 'The airport route is active' in packet['text']
    assert 'current_state_verified' not in packet or packet['current_state_verified'] is False


def test_context_discards_in_flight_withdrawal_not_old_claim(tmp_path, monkeypatch):
    import shared_memory_mcp.view_units as views
    engine, store, _, caller, _, owner, _ = environment(tmp_path)
    record = {'kind': 'decision', 'title': 'fixture', 'body': 'Sensitive old current plan.',
              'scope': 'project', 'sources': [{'uri': owner.as_uri()}]}
    review = {'reason': 'Fixture review', 'evidence': record['sources']}
    made = store.capture(caller, record, 'fixture-record', review,
        {'extensions': {'narrative': {'id': 'current.plan', 'role': 'current'}}})
    publish_account(engine)
    original = views.collect_units
    raced = False
    def concurrent(*args, **kwargs):
        nonlocal raced
        result = original(*args, **kwargs)
        if not raced:
            raced = True
            store.delete(caller, made['id'], review, 'concurrent-withdrawal')
        return result
    monkeypatch.setattr(views, 'collect_units', concurrent)
    packet = store.context(caller)
    assert 'Sensitive old current plan.' not in json.dumps(packet)
    assert packet['status'] == 'changed-during-read'
    assert packet['diagnostic']['code'] == 'context_basis_changed'


def test_correction_of_source_only_view_requires_current_grant(tmp_path):
    engine, store, _, caller, _, owner, _ = environment(tmp_path)
    _, _, old = publish_account(engine)
    record, details, review = correction_input(owner, old)
    policy, _ = engine._policy()
    new = deepcopy(policy)
    new['profiles']['fixture']['source_grants'] = [g for g in new['profiles']['fixture']['source_grants'] if g['id'] != 'owner']
    configure_policy(store, new, expected_revision=_digest(policy))
    with pytest.raises(MemoryError):
        store.capture(caller, record, 'revoked-target', review, details)
    assert not store.search(caller, 'Airport route pause')['items']


def test_ordinary_correction_blocks_frozen_dream_publication(tmp_path):
    engine, store, _, caller, _, owner, _ = environment(tmp_path)
    rid, gen, old = publish_account(engine)
    material = engine.materials(rid)['sources']['owner']['events'][0]['key']
    operation = record_op('later', claim(material, text='Old interpretation that was frozen before the correction.'))
    frozen = engine.freeze(rid, gen, [operation])
    record, details, review = correction_input(owner, old)
    store.capture(caller, record, 'ordinary-before-dream', review, details)
    result = engine.publish(rid, gen, frozen['draft_revision'])
    assert result['status'] == 'blocked' and not result['applied']
    assert 'The airport route is paused' in store.context(caller)['text']
    assert not store.search(caller, 'Old interpretation')['items']


def test_live_capture_recovers_after_actual_publication_boundary(tmp_path, monkeypatch):
    engine, store, _, caller, _, owner, _ = environment(tmp_path)
    _, _, old = publish_account(engine)
    record, details, review = correction_input(owner, old)
    live = {'kind': 'direct-current-user', 'excerpt': 'Pause the airport route, not the project.',
            'original_locator': None, 'history_gap': 'No readable native event yet.',
            'review_method': 'Reviewed the direct current user message.'}
    original = store._publish
    raised = False
    def fail_after_write(path, data):
        nonlocal raised
        original(path, data)
        if not raised and path.suffix == '.md' and b'capture-review:crash-live' in data:
            raised = True
            raise RuntimeError('Synthetic disconnect after the canonical effect became visible')
    monkeypatch.setattr(store, '_publish', fail_after_write)
    with pytest.raises(RuntimeError):
        store.capture(caller, record, 'crash-live', review, details, live_correction=live)
    recovered = store.capture(caller, record, 'crash-live', review, details, live_correction=live)
    assert recovered['replayed']
    assert len(store.search(caller, 'Airport route pause')['items']) == 1
    with pytest.raises(MemoryError):
        store.capture(caller, record, 'crash-live', review, details,
                      live_correction={**live, 'excerpt': 'Changed request under the same key'})
