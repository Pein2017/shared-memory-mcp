"""Task 5.2: a production-shaped history driven only by `next` through the public operations.

The executor makes only its own decisions: the draft's record, the accepted-gap note and the
reviewed outcome at close. Everything else (run id, revisions, cursors, keys) comes from `next`.
"""
from copy import deepcopy
import json
from pathlib import Path
import shutil

from dreaming_helpers import claim, environment, review
from shared_memory_mcp.core import _decode, _digest
from shared_memory_mcp.dreaming import configure_policy
from shared_memory_mcp.operations import call

FIXTURE = Path(__file__).parent / 'fixtures' / 'dreaming' / 'production'
A = {'id': 'production-a', 'question': 'Review the fixture history for durable project findings.'}
B = {'id': 'production-b', 'question': 'A later, different question over the same target.'}
NOTE = 'Compaction originals and unselected Claude branches are not recoverable here; reviewed public text only.'


def production_store(tmp_path):
    engine, store, caller, owner_caller, policy, owner, human = environment(tmp_path)
    history = tmp_path / 'history'
    shutil.copytree(FIXTURE, history)
    updated = deepcopy(policy)
    profile = updated['profiles']['fixture']
    profile.update(read_access='inherited', history_roots=[
        {'path': str(history / 'codex'), 'format': 'codex', 'schema': 'codex-rollout-v1', 'native_version': '0.162.1'},
        {'path': str(history / 'claude'), 'format': 'claude', 'schema': 'claude-jsonl-v1', 'native_versions': ['2.1.296']}])
    profile['source_grants'] = profile['source_grants'][:1]
    profile['budgets'].update(source_bytes=1048576, events=128)
    configure_policy(store, updated, expected_revision=_digest(policy))
    for index in range(2):
        store.propose(owner_caller, {'scope': 'project', 'kind': 'observation', 'title': f'Existing candidate {index}',
                                     'body': 'Synthetic candidate awaiting review.', 'sources': [{'uri': owner.as_uri()}]},
                      f'production-candidate-{index}')
    public = {k: caller[k] for k in ('cwd', 'harness', 'session_id', 'actor')}
    return engine, store, public, history


def follow(store, response, decide):
    """Call exactly the `next` tool and arguments; `decide` may only add the executor's own choices."""
    tools, listings = [], []
    while response.get('next'):
        step = response['next']
        arguments = decide(step, listings, deepcopy(step['args']))
        response = call(store, step['tool'], arguments)
        tools.append(step['tool'])
        if step['tool'] == 'dream_materials':
            listings.append(response['item'])
        assert len(tools) < 30, tools
    return response, tools, listings


def codex_keys(listings):
    return [e['key'] for item in listings for sid, m in item.get('sources', {}).items()
            for e in m['events'] if e.get('raw_digest') and e['role'] in {'user', 'assistant'} and sid.startswith('inherited-')
            and not e['delegated'] and 'agent_id' not in e and e.get('preview', '').startswith('Fixture answer')]


def test_production_history_reaches_reviewed_objective_then_pends_only_appended_material(tmp_path):
    engine, store, caller, history = production_store(tmp_path)

    def decide(step, listings, arguments):
        if step['tool'] == 'dream_draft':
            key = codex_keys(listings)[0]
            arguments['operations'].append({'id': 'finding', 'action': 'record_create', 'review': review([key]),
                                            'claim': claim(key, level='report', text='The fixture rollout reports one synthetic result.')})
        if step['tool'] == 'dream_close':
            arguments.update(objective_outcome='reviewed',
                             accept_gaps=[{**gap, 'note': NOTE} for gap in step['optional']['accept_gaps']])
        return arguments

    started = call(store, 'dream_start', {'caller': caller, 'review_objective': A})
    closed, tools, listings = follow(store, started, decide)
    assert tools[0] == 'dream_materials' and tools[-3:] == ['dream_draft', 'dream_publish', 'dream_close']
    assert closed['item']['objective_completion'] == 'reviewed'
    run = engine._run(closed['item']['run_id'])
    paths = {sid: Path(spec['path']) for sid, spec in ((s['id'], s) for s in run['profile_snapshot']['sources'])}
    session = next(sid for sid, p in paths.items() if p.name == 'prod-session.jsonl')
    worker = next(sid for sid, p in paths.items() if p.name == 'agent-b0worker.jsonl')
    codex = next(sid for sid, p in paths.items() if p.suffix == '.jsonl' and 'codex' in p.parts)
    # The only permanent gap is the compaction; both Claude transcripts resolve a default leaf.
    accepted = {(g['source_id'], g['reason']) for g in closed['item']['objective_progress']['accepted_gaps']}
    assert accepted == {(session, 'compaction_originals_not_proven')}
    assert codex not in {sid for sid, _ in accepted}
    # The benign Codex metadata never became a gap and the worker's events are delegated with its identity.
    events = {sid: m['events'] for item in listings for sid, m in item.get('sources', {}).items()}
    assert [(e['role'], e['delegated'], e.get('agent_id')) for e in events[worker]] == [
        ('user', True, 'b0worker'), ('assistant', True, 'b0worker')]
    assert run['materials'][codex]['coverage']['complete']
    text = json.dumps(listings) + json.dumps(closed)
    assert 'SKIPPED_' not in text
    # Exactly one published record, citing the Codex event it was reviewed against.
    published = [r for r in store._load('demo') if r['status'] == 'active']
    assert len(published) == 1
    notes = [_decode(s['note'][len('dream-source-v1:'):]) for s in published[0]['sources'] if s.get('note', '').startswith('dream-source-v1:')]
    assert notes and {n['source_id'] for n in notes} == {codex} and notes[0]['event_key'] == codex_keys(listings)[0]
    assert {r['title'] for r in store._load('demo') if r['status'] == 'candidate'} == {'Existing candidate 0', 'Existing candidate 1'}

    rollout = history / 'codex' / 'rollout-fixture.jsonl'
    rollout.write_text(rollout.read_text() + json.dumps({'timestamp': '2026-10-12T11:00:00.000Z', 'type': 'response_item',
        'payload': {'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': 'Appended fixture result.'}]}}) + '\n')
    second = call(store, 'dream_start', {'caller': caller, 'review_objective': B})
    progress = second['item']['objective_progress']
    assert progress['remaining_sources'] == 1 and progress['remaining_memory'] == 0
    assert {g['source_id'] for g in progress['accepted_gaps']} == {session}
    listing = call(store, 'dream_materials', second['next']['args'])['item']
    pending = [e for m in listing['sources'].values() for e in m['events']]
    assert [e['preview'] for e in pending] == ['Appended fixture result.'] and listing['memory'] == []
