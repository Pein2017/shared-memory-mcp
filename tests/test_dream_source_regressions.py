"""Selected public history through the publisher on disposable CPU stores."""
from copy import deepcopy
import json
import hashlib

from dreaming_helpers import environment, claim, review, record_op, freeze_publish
from test_dream_sources import HEADER, line, codex_message, claude_message, attest
from shared_memory_mcp.core import _digest
from shared_memory_mcp.dreaming import Dreaming, configure_policy


def selected_engine(store, caller, policy, source):
    updated = deepcopy(policy)
    updated['profiles']['fixture']['source_grants'] = [{**{k: v for k, v in source.items() if k != 'leaf_id'}, 'kind': 'file'}]
    configure_policy(store, updated, expected_revision=_digest(policy))
    return Dreaming(store, 'fixture', caller, publisher=True)


def test_inherited_codex_user_cannot_publish_explicit_collaboration(tmp_path):
    _, store, caller, _, policy, _, path = environment(tmp_path)
    child = {'type': 'session_meta', 'payload': {'id': 'child', 'cli_version': 'fixture-v1',
             'source': {'subagent': {'parent_thread_id': 'fixture-session'}}}}
    user = codex_message('Synthetic preference inherited from parent.')
    path.write_bytes(b''.join(line(v) for v in [child, HEADER, user]))
    source = {**policy['profiles']['fixture']['source_grants'][1], 'attestations': attest(user)}
    engine = selected_engine(store, caller, policy, source)
    run = engine.start()
    rid, gen = run['run_id'], run['generation']
    events = engine.materials(rid)['sources']['human']['events']
    key = events[0]['key']
    operation = {'id': 'inherited', 'action': 'collaboration_create', 'visibility': 'active',
                 'claim': claim(key, level='explicit'), 'review': review([key])}
    _, result = freeze_publish(engine, rid, gen, [operation])
    assert result['status'] == 'blocked'
    assert result['unresolved'][0]['code'] == 'human_attribution_required'
    assert events[0]['session'] == 'child'
    assert store._load('demo') == []
    assert not list((store.root / 'collaboration/Pein/records').glob('*.md'))


def test_unselected_claude_branch_cannot_publish_but_selected_report_can(tmp_path):
    _, store, caller, _, policy, _, path = environment(tmp_path)
    values = [claude_message('A', None, role='user'),
              claude_message('B', 'A'), claude_message('C', 'A')]
    path.write_bytes(b''.join(line(v) for v in values))
    source = {'id': 'selected', 'path': str(path), 'format': 'claude',
              'schema': 'claude-jsonl-v1', 'native_version': 'fixture-v1', 'leaf_id': 'C'}
    engine = selected_engine(store, caller, policy, source)
    run = engine.start(sources=[{'grant_id': 'selected', 'leaf_id': 'C'}])
    rid, gen = run['run_id'], run['generation']
    wrong_key = _digest(['claude', 'fixture-c', 'B', hashlib.sha256(line(values[1])).hexdigest()])
    _, result = freeze_publish(engine, rid, gen, [record_op('wrong', claim(wrong_key, level='report'))])
    assert result['status'] == 'blocked'
    assert result['unresolved'][0]['code'] == 'unverifiable_source'
    assert store._load('demo') == []
    selected = engine.materials(rid)['sources']['selected']['events']
    assert [e['event_id'] for e in selected] == ['A', 'C']
    _, result = freeze_publish(engine, rid, gen, [record_op('right', claim(selected[1]['key'], level='report'))],
                               reconsider_reason='Replace blocked unselected report with selected branch evidence.')
    assert result['status'] == 'applied'
    records = store._load('demo')
    assert len(records) == 1 and records[0]['status'] == 'active'
    assert selected[1]['key'] in records[0]['body'] and wrong_key not in records[0]['body']


def two_branches(path):
    # File order A, C, B; C is the newest public message by timestamp, B is the last line.
    rows = [{**claude_message('A', None, role='user'), 'timestamp': '2026-10-12T10:00:00Z'},
            {**claude_message('C', 'A'), 'timestamp': '2026-10-12T10:05:00Z'},
            {**claude_message('B', 'A'), 'timestamp': '2026-10-12T10:03:00Z'}]
    path.write_bytes(b''.join(line(row) for row in rows))


def test_claude_default_leaf_publishes_newest_branch_and_keeps_sibling_navigation_only(tmp_path):
    _, store, caller, _, policy, _, path = environment(tmp_path)
    two_branches(path)
    source = {'id': 'unselected', 'path': str(path), 'format': 'claude',
              'schema': 'claude-jsonl-v1', 'native_version': 'fixture-v1'}
    engine = selected_engine(store, caller, policy, source)
    run = engine.start()
    rid, gen = run['run_id'], run['generation']
    events = {e['event_id']: e for e in engine.materials(rid)['sources']['unselected']['events']}
    assert {k: (e['branch'], e.get('assurance')) for k, e in events.items()} == {
        'A': ('default-leaf', 'default-leaf'), 'C': ('default-leaf', 'default-leaf'), 'B': ('unspecified', None)}
    _, sibling = freeze_publish(engine, rid, gen, [record_op('B', claim(events['B']['key'], level='report'))])
    assert sibling['status'] == 'blocked' and sibling['unresolved'][0]['code'] == 'unverified_branch'
    _, result = freeze_publish(engine, rid, gen, [record_op('C', claim(events['C']['key'], level='report'))],
                               reconsider_reason='Use the default-leaf branch evidence.')
    assert result['status'] == 'applied'
    record = store._load('demo')[0]
    notes = [json.loads(s['note'][len('dream-source-v1:'):]) for s in record['sources'] if s.get('note', '').startswith('dream-source-v1:')]
    assert [n['selection_assurance'] for n in notes] == ['default-leaf']  # the label stays with the record
    from dreaming_helpers import view_op
    _, viewed = freeze_publish(engine, rid, gen, [view_op('V', claim(events['C']['key'], level='report'))])
    assert viewed['status'] == 'applied'
    assert engine.overview('research', scenario='research')['items'][0]['selection_assurance'] == ['default-leaf']


def test_claude_explicit_older_leaf_overrides_the_default(tmp_path):
    _, store, caller, _, policy, _, path = environment(tmp_path)
    two_branches(path)
    source = {'id': 'explicit', 'path': str(path), 'format': 'claude', 'schema': 'claude-jsonl-v1',
              'native_version': 'fixture-v1', 'leaf_id': 'B'}
    engine = selected_engine(store, caller, policy, source)
    run = engine.start(sources=[{'grant_id': 'explicit', 'leaf_id': 'B'}])
    events = engine.materials(run['run_id'])['sources']['explicit']['events']
    assert [(e['event_id'], e['branch'], e.get('assurance')) for e in events] == [('A', 'B', None), ('B', 'B', None)]
