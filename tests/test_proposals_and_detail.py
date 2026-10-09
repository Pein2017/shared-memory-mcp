"""Proposal consumption and original narrative detail remain source scoped."""
import json
import pytest
from shared_memory_mcp.cli import call_operation
from shared_memory_mcp.core import MemoryError
from shared_memory_mcp.dreaming import add_disposition
from dreaming_helpers import environment, begin
from test_narrative_views import account


def test_proposal_resolution_is_discoverable_and_not_resurrected(tmp_path):
    engine, store, _, caller, _, owner, _ = environment(tmp_path)
    run, generation, source, _ = begin(engine)
    kwargs = dict(topic='preservation', relation='owner-clarification', note='Consider clarifying the limitation; this is a proposal, not an instruction.',
                  observations={'refs': [source]}, semantic_reviewed=True)
    suggested = engine.suggest_issue(run, generation, **kwargs)
    found = call_operation(store, 'issue_search', {'context': caller, 'query': 'preservation'})['items']
    assert len(found) == 1 and found[0]['id'] == suggested['id']
    request = {'context': caller, 'id': suggested['id'], 'disposition': 'handled', 'reason': 'Checked the scoped owner; no change is needed.',
               'expected_revision': found[0]['revision'], 'idempotency_key': 'resolve-proposal'}
    done = call_operation(store, 'issue_resolve', request)
    assert done['status'] == 'ok'
    assert call_operation(store, 'issue_resolve', request)['replayed']
    assert not call_operation(store, 'issue_search', {'context': caller, 'query': ''})['items']
    engine.suggest_issue(run, generation, **kwargs)
    assert not call_operation(store, 'issue_search', {'context': caller, 'query': ''})['items']
    historical = call_operation(store, 'issue_search', {'context': caller, 'query': '', 'include_resolved': True})
    assert historical['items'][0]['disposition'] == 'handled'
    add_disposition(store, caller, target='demo', topic='*', scope='research', source_keys=[source], kind='no_reuse', reason='Fixture source restriction')
    assert not call_operation(store, 'issue_search', {'context': caller, 'query': '', 'include_resolved': True})['items']


def test_full_narrative_detail_uses_exact_bounded_continuation(tmp_path):
    _, store, caller, _ = account(tmp_path)
    arguments = {'context': caller, 'view': 'research', 'scenario': 'research',
                 'unit_index': 0, 'compact': False, 'max_bytes': 2500}
    first = call_operation(store, 'overview_read', arguments)
    cursor = first['items'][0]['detail_page']
    pages = []
    while cursor:
        response = call_operation(store, 'overview_read', {**arguments, 'page': cursor})
        assert len(json.dumps(response, ensure_ascii=False).encode()) <= 2500
        pages.append(response['detail_page']['text'])
        cursor = response['next_page']
    restored = json.loads(''.join(pages))
    assert restored['text'].count('Detailed historical finite-fit description.') == 80
    assert 'Conditions:' in restored['text']
    assert restored['current_state_verified'] is False
