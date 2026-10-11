"""Regression contract: disposable stores only, no provider or production data."""
from copy import deepcopy
import json

import pytest

from shared_memory_mcp.adapters import handle_hook
from shared_memory_mcp.core import MemoryError
from dreaming_helpers import environment, begin, claim, view_op, freeze_publish


def publish_account(engine):
    rid, gen, source, _ = begin(engine)
    c = claim(source, text='The airport route is active; no transfer is established.')
    _, result = freeze_publish(engine, rid, gen, [view_op('account', c)])
    assert result['status'] == 'applied', result
    return rid, gen, engine.overview('research', scenario='research')


def correction_input(owner, previous):
    record = {'kind': 'decision', 'title': 'Airport route pause',
              'body': 'The airport route is paused. Historical finite-fit results remain; no transfer is established.',
              'scope': 'project', 'sources': [{'uri': owner.as_uri()}]}
    details = {'summary': record['body'], 'conditions': 'The airport route only; not the preparing multi-scene branch.',
               'statement_type': 'user_decision', 'extensions': {'narrative': {
                   'id': 'airport.plan', 'role': 'current',
                   'replaces': [f"view:research:{previous['revision']}:0"]}}}
    review = {'reason': 'Synthetic direct-current-message review.', 'evidence': record['sources']}
    return record, details, review


def test_pending_review_over_unchanged_sources_is_actionable(tmp_path):
    engine, *_ = environment(tmp_path)
    rid, gen, _, _ = begin(engine)
    keys = [e['key'] for m in engine.materials(rid)['sources'].values() for e in m['events']]
    engine.mark_processed(rid, gen, {key: 'pending-review' for key in keys})
    closed = engine.close(rid, gen)
    assert closed['pending_review'] == len(keys)
    again = engine.start()
    assert again['status'] != 'no-change', again
    assert again.get('model_required') is True, again


def test_source_drift_retains_dated_account(tmp_path):
    engine, _, _, _, _, owner, _ = environment(tmp_path)
    _, _, previous = publish_account(engine)
    original = owner.read_text()
    assert 'coverage 7' in original
    owner.write_text(original.replace('coverage 7', 'coverage 8', 1))
    current = engine.overview('research', scenario='research')
    assert 'no transfer is established' in current['text'], current
    assert current['status'] == 'stale'
    assert current['as_of'] == previous['as_of']


def test_small_explicit_budget_is_not_valid_empty_success(tmp_path):
    engine, *_ = environment(tmp_path)
    publish_account(engine)
    limited = engine.overview('research', scenario='research', max_chars=100)
    assert limited['status'] == 'budget-limited', limited
    assert limited.get('continuation') or limited.get('navigation'), limited


def test_ordinary_correction_replaces_source_only_overview(tmp_path):
    engine, store, _, caller, _, owner, _ = environment(tmp_path)
    _, _, previous = publish_account(engine)
    original = owner.read_bytes()
    record, details, review = correction_input(owner, previous)
    store.capture(caller, record, 'fixture-pause', review, details)
    current = engine.overview('research', scenario='research')
    assert 'The airport route is active' not in current['text'], current
    packet = store.context(caller)
    assert 'The airport route is paused' in packet['text'], packet
    assert 'Historical finite-fit results remain' in packet['text']
    assert 'no transfer is established' in packet['text']
    assert owner.read_bytes() == original


def test_live_correction_without_native_locator_reaches_native_hook(tmp_path):
    engine, store, _, caller, _, owner, _ = environment(tmp_path)
    _, _, previous = publish_account(engine)
    record, details, review = correction_input(owner, previous)
    basis = {'kind': 'direct-current-user', 'excerpt': 'Pause the airport route; keep its historical results.',
             'original_locator': None, 'history_gap': 'Current message is not yet in readable native history.',
             'review_method': 'Foreground Agent reviewed the direct unquoted current user message.'}
    result = store.capture(caller, record, 'fixture-live-pause', review, details, live_correction=basis)
    read = store.read(caller, [result['id']])['items'][0]
    audit = read['details']['extensions']['live_review']
    assert audit['assurance'] == 'agent-reviewed'
    assert audit['caller']['session_id'] == caller['session_id']
    assert audit['original_locator'] is None and audit['history_gap']
    assert not audit.get('event_id') and not audit.get('operator_attestation')
    hook = handle_hook(store, 'codex', {'hook_event_name': 'SessionStart', 'source': 'startup',
                                      'cwd': caller['cwd'], 'session_id': 'fixture-consuming-session'})
    delivered = hook['hookSpecificOutput']['additionalContext']
    assert 'The airport route is paused' in delivered
    assert 'The airport route is active' not in delivered
    assert 'no transfer is established' in delivered
    assert len(json.dumps(hook, ensure_ascii=False).encode()) <= 8000


@pytest.mark.parametrize('kind', ['historical', 'quoted', 'delegated', 'ambiguous'])
def test_historical_or_ambiguous_message_cannot_use_live_correction(tmp_path, kind):
    engine, store, _, caller, _, owner, _ = environment(tmp_path)
    _, _, previous = publish_account(engine)
    record, details, review = correction_input(owner, previous)
    basis = {'kind': kind, 'excerpt': 'Pause the route.', 'original_locator': None,
             'history_gap': 'Fixture', 'review_method': 'Fixture review'}
    with pytest.raises(MemoryError):
        store.capture(caller, record, 'invalid-live', review, details, live_correction=basis)
