"""Proposal consumption and original narrative detail remain source scoped."""
import json
from copy import deepcopy
import pytest
from shared_memory_mcp.cli import call_operation
from shared_memory_mcp.core import MemoryError, _digest
from shared_memory_mcp.dreaming import add_disposition, configure_policy
from dreaming_helpers import environment, begin
from test_narrative_views import account


def test_proposal_resolution_is_discoverable_and_not_resurrected(tmp_path):
    engine, store, _, caller, _, owner, _ = environment(tmp_path)
    run, generation, source, _ = begin(engine)
    kwargs = dict(topic='preservation', relation='owner-clarification', note='Consider clarifying the limitation; this is a proposal, not an instruction.',
                  observations={'refs': [source]}, semantic_reviewed=True)
    suggested = engine.suggest_issue(run, generation, **kwargs)
    found = call_operation(store, 'issue_list', {'caller': caller, 'query': 'preservation'})['items']
    assert len(found) == 1 and found[0]['id'] == suggested['id']
    request = {'caller': caller, 'id': suggested['id'], 'disposition': 'handled', 'reason': 'Checked the scoped owner; no change is needed.',
               'expected_revision': found[0]['revision'], 'idempotency_key': 'resolve-proposal'}
    done = call_operation(store, 'issue_close', request)
    assert done['status'] == 'ok'
    assert call_operation(store, 'issue_close', request)['replayed']
    assert not call_operation(store, 'issue_list', {'caller': caller, 'query': ''})['items']
    engine.suggest_issue(run, generation, **kwargs)
    assert not call_operation(store, 'issue_list', {'caller': caller, 'query': ''})['items']
    historical = call_operation(store, 'issue_list', {'caller': caller, 'query': '', 'include_resolved': True})
    assert historical['items'][0]['disposition'] == 'handled'
    add_disposition(store, caller, target='demo', topic='*', scope='research', source_keys=[source], kind='no_reuse', reason='Fixture source restriction')
    assert not call_operation(store, 'issue_list', {'caller': caller, 'query': '', 'include_resolved': True})['items']


def test_full_narrative_detail_uses_exact_bounded_continuation(tmp_path):
    _, store, caller, _ = account(tmp_path)
    arguments = {'caller': caller, 'view': 'research', 'scenario': 'research',
                 'unit_index': 0, 'compact': False, 'max_bytes': 2500}
    first = call_operation(store, 'overview', arguments)
    cursor = first['items'][0]['cursor']
    pages = []
    while cursor:
        response = call_operation(store, 'overview', {**arguments, 'cursor': cursor})
        assert len(json.dumps(response, ensure_ascii=False).encode()) <= 2500
        pages.append(response['detail_page']['text'])
        cursor = response['next_cursor']
    restored = json.loads(''.join(pages))
    assert restored['text'].count('Detailed historical finite-fit description.') == 80
    assert 'Conditions:' in restored['text']
    assert restored['current_state_verified'] is False


def test_proposal_reports_current_actions_without_rewriting_old_observation(tmp_path):
    engine, store, _, caller, policy, _, _ = environment(tmp_path)
    old = deepcopy(policy)
    old_actions = ['record_create', 'record_approve', 'view_publish']
    old['profiles']['fixture']['actions'] = old_actions
    configure_policy(store, old, expected_revision=_digest(policy))
    run, generation, source, _ = begin(engine)
    suggested = engine.suggest_issue(run, generation, topic='record-actions', relation='policy-gap',
        note='The observed profile lacks replacement and withdrawal actions.',
        observations={'refs': [source], 'current_actions': old_actions}, semantic_reviewed=True)
    path = store.root / 'dreaming/issues' / (suggested['id'] + '.json')
    original = path.read_bytes()
    before = call_operation(store, 'issue_list', {'caller': caller})['items'][0]
    configure_policy(store, policy, expected_revision=_digest(old))
    after = call_operation(store, 'issue_list', {'caller': caller})['items'][0]
    assert after['current_actions'] == sorted(policy['profiles']['fixture']['actions'])
    assert before['observed_actions_changed'] is False and after['observed_actions_changed'] is True
    assert after['observations']['current_actions'] == old_actions
    assert before['revision'] == after['revision'] and path.read_bytes() == original
    assert after['authority'] == 'advisory-only' and after['disposition'] == 'pending'
