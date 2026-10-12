"""The ordinary public names operate on explicitly selected, isolated collections."""
from copy import deepcopy
import json

import pytest

from shared_memory_mcp.core import MemoryError
from shared_memory_mcp.cli import call_operation
from dreaming_helpers import environment, claim


def invoke(store, caller, tool, collection, **kwargs):
    return call_operation(store, tool, {'caller': caller, 'collection': collection, **kwargs})


def live():
    return {'kind': 'direct-current-user', 'excerpt': 'For this project, use the revised installation path.',
            'original_locator': None, 'history_gap': 'No native event locator in this synthetic live turn.',
            'review_method': 'Direct current message, not a historical or quoted message.'}


def preference(owner):
    c = claim(owner.as_uri(), text='Use /new/project-path for this project only.', level='explicit')
    c['task_modes'] = ['general']
    c['narrative'] = {'id': 'installation.path', 'role': 'preference', 'compact': c['text']}
    c['scenarios'] = ['general']
    return {'claim': c, 'scope': 'project', 'sources': [{'uri': owner.as_uri()}]}


def review(record):
    return {'reason': 'Fixture source and applicability review.', 'evidence': record['sources']}


def test_live_collaboration_capture_is_shared_normal_lifecycle(tmp_path):
    _, store, _, caller, _, owner, _ = environment(tmp_path)
    record = preference(owner)
    result = invoke(store, caller, 'capture', 'collaboration', record=record,
                    idempotency_key='live-pref', review=review(record), live_correction=live())
    replay = invoke(store, caller, 'capture', 'collaboration', record=record,
                    idempotency_key='live-pref', review=review(record), live_correction=live())
    assert replay['item']['id'] == result['item']['id'] and replay['replayed']
    full = invoke(store, caller, 'read', 'collaboration', ids=[result['item']['id']])['items'][0]
    assert full['live_review']['assurance'] == 'agent-reviewed'
    assert full['live_review']['caller']['session_id'] == caller['session_id']
    assert '/new/project-path' in store.context(caller, task_mode='general')['text']
    assert '/new/project-path' not in store.context(caller, task_mode='research')['text']
    assert '/new/project-path' not in store.context(caller)['text']
    invoke(store, caller, 'withdraw', 'collaboration', id=result['item']['id'], review=review(record), idempotency_key='withdraw-pref')
    assert '/new/project-path' not in store.context(caller, task_mode='general')['text']
    assert invoke(store, caller, 'read', 'collaboration', ids=[result['item']['id']], include_inactive=True)['items'][0]['effective_status'] == 'withdrawn'


def test_inferred_preference_stays_candidate_until_review(tmp_path):
    _, store, _, caller, _, owner, _ = environment(tmp_path)
    record = preference(owner)
    record['claim']['level'] = 'inferred'
    made = invoke(store, caller, 'capture', 'collaboration', record=record,
                  review=review(record), live_correction=live(), idempotency_key='inferred')
    assert made['item']['effective_status'] == 'candidate'
    assert not invoke(store, caller, 'search', 'collaboration', query='installation')['items']
    invoke(store, caller, 'approve', 'collaboration', id=made['item']['id'],
           review=review(record), idempotency_key='inferred-review')
    full = invoke(store, caller, 'read', 'collaboration', ids=[made['item']['id']])['items'][0]
    assert full['claim']['level'] == 'inferred' and full['effective_status'] == 'active'


def test_history_is_explicit_source_linked_and_not_startup_knowledge(tmp_path):
    _, store, _, caller, _, owner, _ = environment(tmp_path)
    episode = {'harness': 'codex', 'session_id': 'source-session', 'cwd': caller['cwd'], 'project_id': 'demo',
               'branch': 'selected-main', 'task_modes': ['research'], 'task_state': 'unfinished',
               'ranges': [{'uri': owner.as_uri(), 'locator': 'lines:1-1', 'source_version': 'a' * 64}],
               'review_scope': 'Only the finite-fit task segment; not the complete session.',
               'coverage_refs': [], 'gaps': ['Remaining task segments are not reviewed.']}
    record = {'kind': 'episode', 'title': 'Finite fit episode', 'body': 'Historical task: finite fit succeeded, preservation unreviewed.',
              'scope': 'project', 'sources': [{'uri': owner.as_uri()}], 'episode': episode}
    result = invoke(store, caller, 'capture', 'history', record=record, review=review(record), idempotency_key='history')
    assert (store.root / 'history/demo/episodes' / (result['item']['id'] + '.md')).is_file()
    assert not (store.root / 'records/demo' / (result['item']['id'] + '.md')).exists()
    assert not store.search(caller, 'finite fit')['items']
    assert 'finite fit succeeded' not in store.context(caller, task_mode='research')['text']
    found = invoke(store, caller, 'search', 'history', query='finite fit')['items']
    assert found and found[0]['collection'] == 'history'
    raw = invoke(store, caller, 'read', 'history', ids=[result['item']['id']])['items'][0]
    assert raw['episode'] == episode
    invoke(store, caller, 'withdraw', 'history', id=result['item']['id'], review=review(record), idempotency_key='delete-history')
    assert not invoke(store, caller, 'search', 'history', query='finite fit')['items']
    assert invoke(store, caller, 'read', 'history', ids=[result['item']['id']], include_inactive=True)['items']
    with pytest.raises(MemoryError):
        invoke(store, caller, 'capture', 'project', record=record, review=review(record), idempotency_key='not-knowledge')


def test_collection_selection_and_live_assurance_cannot_expand_scope(tmp_path):
    _, store, _, caller, _, owner, _ = environment(tmp_path)
    record = preference(owner)
    record['claim']['projects'] = ['other']
    with pytest.raises(MemoryError):
        invoke(store, caller, 'capture', 'collaboration', record=record,
               review=review(record), live_correction=live(), idempotency_key='foreign')
    with pytest.raises(MemoryError):
        invoke(store, caller, 'search', '../records', query='anything')
