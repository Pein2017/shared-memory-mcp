"""Context selection, correction identity and the actual serialized byte contract."""
import json
import pytest
from shared_memory_mcp.core import MemoryError
from shared_memory_mcp.context_packet import exposure_size
from dreaming_helpers import environment


def capture(store, caller, owner, key, text, role='background', modes=None, relations=None, replaces=None):
    rec = {'kind': 'observation', 'title': key, 'body': text, 'scope': 'project', 'sources': [{'uri': owner.as_uri()}]}
    details = {'conditions': 'Frozen fixture conditions; not transfer evidence.', 'extensions': {'narrative': {'id': key, 'role': role}}}
    if modes: details['task_modes'] = modes
    if relations: details['relations'] = relations
    if replaces: details['extensions']['narrative']['replaces'] = replaces
    return store.capture(caller, rec, key, {'reason': 'Fixture semantic/source review', 'evidence': rec['sources']}, details)


def test_cross_mode_evidence_remains_and_preferences_are_strict(tmp_path):
    _, store, _, caller, _, owner, _ = environment(tmp_path)
    background = capture(store, caller, owner, 'goal', 'Enumerate physical objects without duplicate owners.', 'goal')
    a = capture(store, caller, owner, 'materialization', 'Both arms ran HF; vLLM was not executed.', 'outcome', ['general'])
    capture(store, caller, owner, 'research-hypothesis', 'Materialization requires a causal contrast.', 'branch', ['research'],
            [{'type': 'conflicts_with', 'uri': 'record:' + a['id']}])
    capture(store, caller, owner, 'style', 'Use concise operational answers for support work.', 'preference', ['general'])
    packet = store.context(caller, 'materialization', task_mode='research')
    assert 'Both arms ran HF' in packet['text'] and 'not executed' in packet['text']
    assert 'Enumerate physical objects' in packet['text']
    assert 'concise operational answers' not in packet['text']
    lookup = store.search(caller, 'materialization', task_mode='research')
    assert a['id'] in {r['id'] for r in lookup['items']}
    restricted = store.context(caller, 'materialization', task_mode='research',
        mode_restriction={'mode': 'research', 'basis': 'explicit-user-restriction'})
    assert 'Both arms ran HF' not in restricted['text']
    # The claim cannot survive a user restriction that excludes its necessary contrary evidence.
    assert 'Materialization requires a causal contrast.' not in restricted['text']


def test_stable_bootstrap_and_single_combined_budget(tmp_path):
    _, store, _, caller, _, owner, _ = environment(tmp_path)
    capture(store, caller, owner, 'goal', 'Long-term goal: unique physical owner coverage.', 'goal')
    capture(store, caller, owner, 'airport', 'Airport results are conditional; preservation failed.', 'branch', ['research'])
    first = store.context(caller)
    bound = store.context(caller, 'airport', task_mode='research')
    def part(packet, kind):
        p = next(p for p in packet['parts'] if p['kind'] == kind)
        return packet['text'][p['start']:p['end']]
    assert part(first, 'bootstrap') == part(bound, 'bootstrap')
    assert 'preservation failed' in part(bound, 'task')
    assert exposure_size(bound) <= 8000
    assert store.context(caller, 'airport', task_mode='research', previous_revision=bound['packet_revision'])['unchanged']


def test_whole_background_that_fits_combined_budget_is_delivered(tmp_path):
    _, store, _, caller, _, owner, _ = environment(tmp_path)
    body = 'Dated finite-panel outcome; no transfer established. ' * 70
    capture(store, caller, owner, 'retained-account', body)
    packet = store.context(caller)
    assert packet['status'] == 'ok' and body in packet['text']
    assert 'not transfer evidence' in packet['text']
    assert exposure_size(packet) <= 8000


@pytest.mark.parametrize('cap', [128, 512, 1800, 3400, 8000])
def test_cjk_escaping_qualifiers_respect_actual_exposure(tmp_path, cap):
    _, store, _, caller, _, owner, _ = environment(tmp_path)
    capture(store, caller, owner, 'cjk-record', '中文的条件化观察。"引用"\\路径\n' * 50, 'milestone')
    packet = store.context(caller, max_bytes=cap)
    assert exposure_size(packet) <= cap
    if packet['status'] == 'ok' and packet['items']:
        assert 'not transfer evidence' in packet['text']


def test_explicit_record_replacement_and_no_predecessor_revival(tmp_path):
    _, store, _, caller, _, owner, _ = environment(tmp_path)
    old = capture(store, caller, owner, 'old-plan', 'Route is active.', 'current')
    new = capture(store, caller, owner, 'new-plan', 'Route is paused.', 'current', replaces=['record:' + old['id']])
    assert 'Route is active.' not in store.context(caller)['text']
    assert not store.read(caller, [old['id']])['items']
    store.delete(caller, new['id'], {'reason': 'Withdrawal fixture', 'evidence': [{'uri': owner.as_uri()}]}, 'delete-new')
    assert 'Route is active.' not in store.context(caller)['text']
    assert store.read(caller, [old['id']], include_inactive=True)['items']
