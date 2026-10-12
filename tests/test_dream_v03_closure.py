"""WP2 Dreaming closure: reader allowlists, target-keyed positions, gaps, verified coverage, paging.

Fixtures under tests/fixtures/dreaming copy real Codex 0.162 / Claude 2.1.296 field shapes with synthetic text.
"""
from copy import deepcopy
import json
from pathlib import Path
import shutil

import pytest

from dreaming_helpers import environment
from shared_memory_mcp.core import MemoryError, _digest
from shared_memory_mcp.dream_sources import read_source
from shared_memory_mcp.dreaming import Dreaming, configure_policy

FIXTURES = Path(__file__).parent / 'fixtures' / 'dreaming'
SKIPPED = ('SKIPPED_', 'fixture-tool-use', 'SKIPPED_SIGNATURE')
OBJECTIVE = {'id': 'closure-a', 'question': 'Review the fixture history for durable findings.'}


def no_skipped_payload(value):
    text = json.dumps(value)
    return not any(marker in text for marker in SKIPPED)


def codex_spec(path):
    return {'id': 'codex', 'path': str(path), 'format': 'codex', 'schema': 'codex-rollout-v1', 'native_version': '0.162.1'}


def claude_spec(path, **options):
    return {'id': 'claude', 'path': str(path), 'format': 'claude', 'schema': 'claude-jsonl-v1', **options}


# --- 2.1 reader allowlists --------------------------------------------------

def test_codex_benign_metadata_is_skipped_without_gap_or_payload():
    result = read_source(codex_spec(FIXTURES / 'codex-0.162-benign-metadata.jsonl'))
    assert [e['role'] for e in result['events']] == ['user', 'assistant']
    assert result['coverage']['complete'] and result['coverage']['gaps'] == []
    assert no_skipped_payload(result)


def test_claude_attachment_navigation_records_bridge_ancestry_without_gap_or_payload():
    spec = claude_spec(FIXTURES / 'claude-project' / 'fixture-session-1.jsonl', native_version='2.1.296', leaf_id='c-reply-1')
    result = read_source(spec)
    # The reply descends through a thinking-only turn and an attachment; both stay private bridges.
    assert [e['event_id'] for e in result['events']] == ['c-user-1', 'c-reply-1']
    assert result['coverage']['complete'] and result['coverage']['gaps'] == []
    assert no_skipped_payload(result) and 'claude_links' not in result['cursor']['state']


def test_claude_subagent_transcript_is_delegated_with_agent_id_under_mixed_versions():
    path = FIXTURES / 'claude-project' / 'fixture-session-1' / 'subagents' / 'agent-a0fixture.jsonl'
    with pytest.raises(MemoryError):
        read_source(claude_spec(path, leaf_id='s-reply-1'))  # a Claude source still needs its version contract
    single = read_source(claude_spec(path, native_version='2.1.296', leaf_id='s-reply-1'))
    assert single['events'] == [] and {g['reason'] for g in single['coverage']['gaps']} == {'unknown_native_version'}
    result = read_source(claude_spec(path, native_versions=['2.1.296', '2.1.297'], leaf_id='s-reply-1'))
    assert result['coverage']['complete']
    assert [(e['event_id'], e['delegated'], e['agent_id'], e['human']) for e in result['events']] == [
        ('s-user-1', True, 'a0fixture', 'unknown'), ('s-reply-1', True, 'a0fixture', 'unknown')]
    assert no_skipped_payload(result)


def claude_history(tmp_path):
    engine, store, caller, owner_caller, policy, owner, human = environment(tmp_path)
    root = tmp_path / 'claude-projects'
    shutil.copytree(FIXTURES / 'claude-project', root / 'encoded-project')
    updated = deepcopy(policy)
    updated['profiles']['fixture'].update(read_access='inherited', history_roots=[{
        'path': str(root), 'format': 'claude', 'schema': 'claude-jsonl-v1', 'native_versions': ['2.1.296', '2.1.297']}])
    updated['profiles']['fixture']['budgets'].update(source_bytes=1048576, events=128)
    configure_policy(store, updated, expected_revision=_digest(policy))
    return engine, store, owner_caller, root


def test_history_root_discovers_subagent_transcripts_and_never_exposes_skipped_payload(tmp_path):
    engine, store, _, root = claude_history(tmp_path)
    assert engine.catalog()['history_roots'][0]['native_versions'] == ['2.1.296', '2.1.297']
    started = engine.start(review_objective=OBJECTIVE)
    materials = engine.materials(started['run_id'])['sources']
    events = [e for m in materials.values() for e in m['events']]
    delegated = [e for e in events if e.get('agent_id') == 'a0fixture']
    assert [e['text'] for e in delegated] == ['Fixture delegated instruction for the worker.', 'Fixture worker report: done.']
    assert all(e['delegated'] for e in delegated)
    assert not any(g['reason'] == 'unknown_native_version' for m in materials.values() for g in m['coverage']['gaps'])
    for response in (started, materials, engine.inspect(started['run_id']), engine.changes(started['run_id']),
                     engine.material_summary(started['run_id'])):
        assert no_skipped_payload(response)
    assert no_skipped_payload(json.loads((store.root / f"dreaming/runs/{started['run_id']}/run.json").read_text()))


# --- 2.7 catalog discovery ---------------------------------------------------

def test_catalog_skips_closed_or_deleted_runs_and_exact_profile_lanes(tmp_path):
    engine, store, caller, _, policy, _, _ = environment(tmp_path)
    updated = deepcopy(policy)
    updated['profiles']['fixture-b'] = deepcopy(updated['profiles']['fixture'])
    configure_policy(store, updated, expected_revision=_digest(policy))
    other = Dreaming(store, 'fixture-b', caller, publisher=True)
    live = other.start()
    assert engine.catalog()['active_runs'] == []  # profile `fixture` must not read `fixture-b-*` lanes
    assert [r['id'] for r in other.catalog()['active_runs']] == [live['run_id']]
    first = engine.start()
    engine.close(first['run_id'], 1, abandon_reason='Fixture closed lane marker.')
    shutil.rmtree(store.root / 'dreaming' / 'runs' / first['run_id'])
    assert engine.catalog()['active_runs'] == []
    assert set(engine.start(review_objective=OBJECTIVE)) >= {'run_id'}


# --- shared fixtures ---------------------------------------------------------

def codex_file(path, session, texts, *, extra=()):
    rows = [{'type': 'session_meta', 'payload': {'id': session, 'cli_version': 'fixture-v1', 'source': 'cli'}}]
    rows += [{'type': 'response_item', 'id': f'{session}-{i}', 'payload': {'type': 'message', 'role': 'assistant',
              'content': [{'type': 'output_text', 'text': text}]}} for i, text in enumerate(texts)]
    rows += list(extra)
    path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
    return path


def codex_history(tmp_path, files):
    """Profile with only an inherited Codex history root holding `files` {name: (texts, extra)}."""
    engine, store, caller, owner_caller, policy, owner, human = environment(tmp_path)
    root = tmp_path / 'codex-history'
    root.mkdir()
    for name, (texts, extra) in files.items():
        codex_file(root / f'{name}.jsonl', 'session-' + name, texts, extra=extra)
    updated = deepcopy(policy)
    updated['profiles']['fixture'].update(read_access='inherited', history_roots=[{
        'path': str(root), 'format': 'codex', 'schema': 'codex-rollout-v1', 'native_version': 'fixture-v1'}])
    updated['profiles']['fixture']['source_grants'] = updated['profiles']['fixture']['source_grants'][:1]
    updated['profiles']['fixture']['budgets'].update(source_bytes=1048576, events=128)
    configure_policy(store, updated, expected_revision=_digest(policy))
    return engine, store, owner_caller, root


def by_path(engine, run_id):
    run = engine._run(run_id)
    return {Path(spec['path']).name: spec['id'] for spec in run['profile_snapshot']['sources']}


def read_and_mark(engine, run_id, *, only=None, status='no-signal'):
    """Serve material through the whole-set read, then mark the chosen sources' events."""
    statuses = {}
    for sid, material in engine.materials(run_id)['sources'].items():
        if only is None or sid in only:
            statuses.update({e['key']: status for e in material['events']})
    statuses.update({ref: status for ref in engine._run(run_id).get('memory_inputs', {})} if only is None else {})
    for ref in (engine._run(run_id).get('memory_inputs', {}) if only is None else {}):
        engine.materials(run_id, event_key=ref)
    if statuses:
        engine.mark_processed(run_id, engine._run(run_id)['generation'], statuses)
    return statuses


B = {'id': 'closure-b', 'question': 'A different question over the same target.'}
UNKNOWN = {'type': 'future_native_record', 'payload': {'private': 'SKIPPED_UNKNOWN_PAYLOAD'}}


# --- 2.2 target-keyed positions ---------------------------------------------

def test_second_objective_reports_reviewed_positions_and_pends_only_new_material(tmp_path):
    engine, store, _, root = codex_history(tmp_path, {'one': (['First fixture finding.'], ()), 'two': (['Second fixture finding.'], ())})
    first = engine.start(review_objective=OBJECTIVE)
    assert first['objective_progress']['remaining_sources'] == 3  # two history files plus the owner grant
    read_and_mark(engine, first['run_id'])
    engine.close(first['run_id'], 1, objective_outcome='reviewed')
    codex_file(root / 'three.jsonl', 'session-three', ['Third, newly appended fixture session.'])
    second = engine.start(review_objective=B)
    progress = second['objective_progress']
    # RED before re-keying: objective B restarted from zero and pended all three sources.
    assert progress['remaining_sources'] == 1
    assert {r['status'] for r in progress['reviewed_sources']} == {'processed'} and len(progress['reviewed_sources']) == 3
    assert all(r['reviewed_offset'] == r['cutoff'] for r in progress['reviewed_sources'])
    assert set(by_path(engine, second['run_id'])) == {'three.jsonl'}
    assert engine.inspect(second['run_id'])['processed'] == {}  # semantic marks do not transfer


def test_interrupted_run_never_advances_past_unserved_material(tmp_path):
    engine, store, _, root = codex_history(tmp_path, {'one': (['First fixture finding.'], ()), 'two': (['Second fixture finding.'], ())})
    first = engine.start(review_objective=OBJECTIVE)
    ids = by_path(engine, first['run_id'])
    unserved = engine._run(first['run_id'])['materials'][ids['two.jsonl']]['events'][0]['key']
    with pytest.raises(MemoryError) as error:
        engine.mark_processed(first['run_id'], 1, {unserved: 'processed'})
    assert error.value.code == 'unserved_event' and unserved in str(error.value)
    engine.materials(first['run_id'], ids['one.jsonl'], event_key=engine._run(first['run_id'])['materials'][ids['one.jsonl']]['events'][0]['key'])
    read_and_mark(engine, first['run_id'], only={ids['one.jsonl']})
    engine.close(first['run_id'], 1, abandon_reason='Fixture interruption mid-batch.')
    second = engine.start(review_objective=B)
    reviewed = {r['source_id'] for r in second['objective_progress']['reviewed_sources']}
    assert reviewed == {ids['one.jsonl']}
    assert set(by_path(engine, second['run_id'])) == {'two.jsonl', 'owner.md'}


def test_legacy_objective_checkpoints_merge_conservatively_once(tmp_path):
    from shared_memory_mcp.dream_incremental import load_objective, save_objective
    engine, store, _, root = codex_history(tmp_path, {'one': (['First fixture finding.'], ()), 'two': (['Second fixture finding.'], ())})
    first = engine.start(review_objective=OBJECTIVE)
    ids = by_path(engine, first['run_id'])
    read_and_mark(engine, first['run_id'])
    engine.close(first['run_id'], 1, objective_outcome='reviewed')
    # Rewrite the store into the legacy shape: objective-keyed progress plus a second objective index
    # whose checkpoint disagrees about `two` (never reviewed there).
    run_path = store.root / f"dreaming/runs/{first['run_id']}/run.json"
    run = json.loads(run_path.read_text())
    progress = load_objective(store, run['objective_progress'])
    progress.pop('target_keyed')
    run['objective_progress'] = save_objective(store, progress)
    run_path.write_text(json.dumps(run))
    other = deepcopy(progress)
    other['review_objective'] = {'id': 'legacy-x', 'question': 'An older objective.'}
    other['sources'][ids['two.jsonl']].update(reviewed_offset=0, status='pending', cursor=None, pending_page=None)
    legacy_id = 'f' * 32
    (store.root / f'dreaming/runs/{legacy_id}').mkdir()
    (store.root / f'dreaming/runs/{legacy_id}/run.json').write_text(json.dumps(
        {**run, 'id': legacy_id, 'review_objective': other['review_objective'], 'objective_progress': save_objective(store, other)}))
    (store.root / f"dreaming/checkpoints/fixture-{_digest(['demo', 'legacy-x'])}-objective.json").write_text(json.dumps({'run_id': legacy_id}))
    second = engine.start(review_objective=B)
    assert {r['source_id'] for r in second['objective_progress']['reviewed_sources']} == {ids['one.jsonl'], 'owner'}
    assert set(by_path(engine, second['run_id'])) == {'two.jsonl'}
    assert load_objective(store, engine._run(second['run_id'])['objective_progress'])['target_keyed'] is True


def test_reread_range_returns_a_reviewed_source_to_pending(tmp_path):
    engine, store, _, root = codex_history(tmp_path, {'one': (['First fixture finding.'], ())})
    first = engine.start(review_objective=OBJECTIVE)
    sid = by_path(engine, first['run_id'])['one.jsonl']
    read_and_mark(engine, first['run_id'])
    engine.close(first['run_id'], 1, objective_outcome='reviewed')
    with pytest.raises(MemoryError) as error:
        engine.start(review_objective={**B, 'reread': [{'source_id': 'unknown-source', 'range': [0, 10]}]})
    assert error.value.code == 'invalid_objective'
    again = engine.start(review_objective={**B, 'reread': [{'source_id': sid, 'range': [0, 10]}]})
    assert set(by_path(engine, again['run_id'])) == {'one.jsonl'}


# --- 2.3 accepted permanent gaps --------------------------------------------

def test_unaccepted_gap_stays_pending_and_accepted_gap_is_not_restaged(tmp_path):
    engine, store, _, root = codex_history(tmp_path, {'clean': (['Clean fixture finding.'], ()),
                                                       'gapped': (['Gapped fixture finding.'], (UNKNOWN,))})
    first = engine.start(review_objective=OBJECTIVE)
    gapped = by_path(engine, first['run_id'])['gapped.jsonl']
    read_and_mark(engine, first['run_id'])
    with pytest.raises(MemoryError) as error:
        engine.close(first['run_id'], 1, objective_outcome='reviewed')
    assert error.value.code == 'pending_objective' and gapped in str(error.value) and 'unknown_event_schema' in str(error.value)
    with pytest.raises(MemoryError) as error:
        engine.close(first['run_id'], 1, accept_gaps=[{'source_id': gapped, 'reason': 'bounded_partial', 'note': 'x'}])
    assert error.value.code == 'invalid_input'
    closed = engine.close(first['run_id'], 1)
    assert {(g['source_id'], g['reason']) for g in closed['outstanding_gaps']} == {(gapped, 'unknown_event_schema')}
    second = engine.start(review_objective=OBJECTIVE)
    assert set(by_path(engine, second['run_id'])) == {'gapped.jsonl'}  # unaccepted: the same page is staged again
    read_and_mark(engine, second['run_id'])
    closed = engine.close(second['run_id'], 1, objective_outcome='reviewed', accept_gaps=[
        {'source_id': gapped, 'reason': 'unknown_event_schema', 'note': 'Unknown future record carries no public text.'}])
    assert closed['objective_completion'] == 'reviewed'
    assert engine.start(review_objective=OBJECTIVE)['status'] == 'no-change'
    third = engine.start(review_objective=B)
    accepted = third['objective_progress']['accepted_gaps']
    assert [(g['source_id'], g['reason'], g['note']) for g in accepted] == [
        (gapped, 'unknown_event_schema', 'Unknown future record carries no public text.')]
    assert by_path(engine, third['run_id']) == {}  # not re-staged under a new objective either
    assert no_skipped_payload(third)


def test_view_citing_a_source_reports_its_accepted_gap(tmp_path):
    from dreaming_helpers import claim, review
    engine, store, _, root = codex_history(tmp_path, {'gapped': (['Gapped fixture finding.'], (UNKNOWN,))})
    first = engine.start(review_objective=OBJECTIVE)
    gapped = by_path(engine, first['run_id'])['gapped.jsonl']
    read_and_mark(engine, first['run_id'])
    engine.close(first['run_id'], 1, accept_gaps=[{'source_id': gapped, 'reason': 'unknown_event_schema', 'note': 'Fixture note.'}])
    again = engine.start(review_objective={**B, 'reread': [{'source_id': gapped, 'range': [0, 1]}]})
    key = engine.materials(again['run_id'])['sources'][gapped]['events'][0]['key']
    c = claim(key, level='report')
    frozen = engine.freeze(again['run_id'], 1, [{'id': 'V', 'action': 'view_publish', 'view': 'research', 'claims': [c], 'review': review([key])}])
    assert engine.publish(again['run_id'], 1, frozen['draft_revision'])['status'] == 'applied'
    unit = engine.overview('research', scenario='research')['items'][0]
    assert unit['sources'][0]['accepted_gaps'][0]['note'] == 'Fixture note.'


# --- 2.4 verified coverage inside drafts --------------------------------------

def test_marking_unserved_event_is_rejected_and_marks_publish_with_the_receipt(tmp_path):
    from dreaming_helpers import claim, record_op
    engine, store, *_ = environment(tmp_path)
    run = engine.start(review_objective=OBJECTIVE)
    rid = run['run_id']
    owner_key = engine._run(rid)['materials']['owner']['events'][0]['key']
    with pytest.raises(MemoryError) as error:
        engine.freeze(rid, 1, [], coverage={owner_key: 'processed'})
    assert error.value.code == 'unserved_event' and owner_key in str(error.value)
    assert engine._run(rid)['processed'] == {} and engine._run(rid)['drafts'] == []
    engine.materials(rid, 'owner', event_key=owner_key)
    frozen = engine.freeze(rid, 1, [record_op('fact', claim(owner_key))], coverage={owner_key: 'processed'})
    assert engine._run(rid)['processed'] == {}  # staged in the draft, not yet effective
    published = engine.publish(rid, 1, frozen['draft_revision'])
    after = engine._run(rid)
    assert published['coverage'] == 'applied' and after['processed'] == {owner_key: 'processed'}
    assert f'dream:{rid}:1:coverage' in after['receipts'] and f'dream:{rid}:1:fact' in after['receipts']


def test_marks_are_not_applied_when_the_drafts_effects_fail(tmp_path):
    engine, store, *_ = environment(tmp_path)
    rid = engine.start(review_objective=OBJECTIVE)['run_id']
    owner_key = engine._run(rid)['materials']['owner']['events'][0]['key']
    engine.materials(rid, 'owner', event_key=owner_key)
    from dreaming_helpers import claim, record_op
    # A personal-preference level is inadmissible for research memory, so the effect fails at publication.
    frozen = engine.freeze(rid, 1, [record_op('bad', claim(owner_key, level='explicit'))], coverage={owner_key: 'processed'})
    published = engine.publish(rid, 1, frozen['draft_revision'])
    assert published['status'] == 'blocked' and published['coverage'] == 'not-applied'
    assert engine._run(rid)['processed'] == {}


def test_coverage_only_draft_is_open_to_advisory_executor_but_effects_are_not(tmp_path):
    from dreaming_helpers import claim, record_op
    engine, store, caller, *_ = environment(tmp_path)
    advisory = Dreaming(store, 'fixture', caller)
    rid = advisory.start(review_objective=OBJECTIVE)['run_id']
    owner_key = advisory._run(rid)['materials']['owner']['events'][0]['key']
    advisory.materials(rid, 'owner', event_key=owner_key)
    effects = advisory.freeze(rid, 1, [record_op('fact', claim(owner_key))], coverage={owner_key: 'processed'})
    with pytest.raises(MemoryError) as error:
        advisory.publish(rid, 1, effects['draft_revision'])
    assert error.value.code == 'advisory_only'
    marks = advisory.freeze(rid, 1, [], coverage={owner_key: 'no-signal'}, reconsider_reason='Advisory keeps only coverage.')
    assert advisory.publish(rid, 1, marks['draft_revision'])['coverage'] == 'applied'
    assert advisory._run(rid)['processed'] == {owner_key: 'no-signal'} and store._load('demo') == []


def test_takeover_attempt_must_be_served_again(tmp_path):
    engine, store, caller, *_ = environment(tmp_path)
    rid = engine.start(review_objective=OBJECTIVE)['run_id']
    owner_key = engine._run(rid)['materials']['owner']['events'][0]['key']
    engine.materials(rid, 'owner', event_key=owner_key)
    other = Dreaming(store, 'fixture', {**caller, 'session_id': 'fixture-executor-B'}, publisher=True)
    other.takeover(rid, 1)
    with pytest.raises(MemoryError) as error:
        other.freeze(rid, 2, [], coverage={owner_key: 'processed'})
    assert error.value.code == 'unserved_event'


# --- 2.5 always-paged materials and 2.8 retention -----------------------------

def ninety_six(tmp_path):
    engine, store, caller, owner_caller, policy, owner, human = environment(tmp_path)
    codex_file(human, 'fixture-source-session', [f'Fixture message {i}: ' + 'detail ' * 60 for i in range(95)])
    updated = deepcopy(policy)
    updated['profiles']['fixture']['budgets'].update(source_bytes=1048576, events=128)
    configure_policy(store, updated, expected_revision=_digest(policy))
    return engine, store, caller, owner


def test_materials_without_event_selection_are_paged_within_max_bytes(tmp_path):
    from shared_memory_mcp.operations import call, size
    engine, store, caller, _ = ninety_six(tmp_path)
    started = call(store, 'dream_start', {'caller': caller, 'review_objective': OBJECTIVE})
    run_id = started['item']['run_id']
    assert sum(len(m['events']) for m in engine._run(run_id)['materials'].values()) == 96
    keys, arguments, pages = [], {'caller': caller, 'run_id': run_id, 'max_bytes': 4096}, 0
    while True:
        page = call(store, 'dream_materials', arguments)
        pages += 1
        assert size(page) <= 4096 and page['budget']['used_bytes'] <= 4096
        keys += [e['key'] for m in page['item']['sources'].values() for e in m['events']]
        if not page['next_cursor']:
            break
        assert page['next'] == {'tool': 'dream_materials', 'args': {**arguments, 'cursor': page['next_cursor']}}
        arguments = page['next']['args']
    assert pages > 1 and len(keys) == len(set(keys)) == 96
    with pytest.raises(MemoryError) as error:
        call(store, 'dream_materials', {'caller': caller, 'run_id': run_id, 'max_bytes': 100})
    assert error.value.code == 'response_budget'


def test_close_strips_run_text_but_keeps_receipts_keys_and_digests(tmp_path):
    from dreaming_helpers import claim, record_op
    engine, store, caller, _ = ninety_six(tmp_path)
    rid = engine.start(review_objective=OBJECTIVE)['run_id']
    owner_key = engine._run(rid)['materials']['owner']['events'][0]['key']
    engine.materials(rid, 'owner', event_key=owner_key)
    frozen = engine.freeze(rid, 1, [record_op('fact', claim(owner_key))], coverage={owner_key: 'processed'})
    engine.publish(rid, 1, frozen['draft_revision'])
    path = store.root / f'dreaming/runs/{rid}/run.json'
    before_bytes = path.read_bytes()
    before = json.loads(before_bytes)
    engine.close(rid, 1, abandon_reason='Fixture partial batch.')
    after_bytes = path.read_bytes()
    after = json.loads(after_bytes)
    assert len(after_bytes) < len(before_bytes)
    assert json.dumps(after['receipts'], sort_keys=True) == json.dumps(before['receipts'], sort_keys=True)
    identity = lambda run: [(e['key'], e['raw_digest'], e['text_chars']) for m in run['materials'].values() for e in m['events']]
    assert identity(after) == identity(before)
    assert not any('text' in e for m in after['materials'].values() for e in m['events'])
    summary = engine.material_summary(rid)
    assert summary['text_retained'] is False
    listed = [e for m in summary['sources'].values() for e in m['events']]
    assert listed and all(e['preview'] is None and len(e['key']) == 64 and len(e['raw_digest']) == 64 for e in listed)
    assert engine.materials(rid, 'owner', event_key=owner_key)['text_retained'] is False


# --- 2.6 next and the default objective ----------------------------------------

def test_scripted_executor_following_only_next_completes_a_batch(tmp_path):
    from shared_memory_mcp.operations import call
    engine, store, caller, owner_caller, policy, owner, human = environment(tmp_path)
    owner.write_text('Fixture owner text that is longer than one summary preview. ' * 8)
    response = call(store, 'dream_start', {'caller': caller, 'review_objective': OBJECTIVE})
    tools = ['dream_start']
    while response.get('next'):
        step = response['next']
        response = call(store, step['tool'], deepcopy(step['args']))  # verbatim, including any template
        tools.append(step['tool'])
        assert len(tools) < 20
    assert tools == ['dream_start', 'dream_materials', 'dream_materials', 'dream_draft', 'dream_publish', 'dream_close']
    run = engine._run(response['item']['run_id'])
    assert run['phase'] == 'closed' and set(run['processed']) == set(engine._events(run))


def test_default_objective_inventories_memory_and_reads_no_history(tmp_path, monkeypatch):
    import shared_memory_mcp.core as core
    engine, store, owner_caller, root = codex_history(tmp_path, {'one': (['History must stay unread.'], ())})
    owner = tmp_path / 'target' / 'owner.md'
    created = {}
    for index in range(12):
        monkeypatch.setattr(core, '_now', lambda index=index: f'2026-09-{10 + index:02}T00:00:00Z')
        title = 'Duplicated fixture title' if index in (4, 5) else f'Fixture candidate {index}'
        created[index] = store.propose(owner_caller, {'scope': 'project', 'kind': 'observation', 'title': title,
            'body': 'Synthetic candidate body.', 'sources': [{'uri': owner.as_uri()}]}, f'candidate-{index}')['record']['id']
    monkeypatch.undo()
    started = engine.start(default_objective=True)
    items = started['inventory']['items']
    candidates = [i for i in items if i['reason'] in {'candidate', 'stale-candidate'}]
    assert [i['ref'] for i in candidates] == ['record:' + created[i] for i in range(12)]  # oldest first
    assert all(i['reason'] == 'stale-candidate' and i['age_days'] > 7 for i in candidates)
    assert sorted(i['ref'] for i in items if i['reason'] == 'duplicate-title') == sorted(['record:' + created[4], 'record:' + created[5]])
    assert by_path(engine, started['run_id']) == {} and started['objective_progress']['remaining_sources'] == 0
    hint = engine.next_hint(started['run_id'])
    assert hint['suggested_event_key'] == 'record:' + created[0] and hint['suggested_source_id'] is None
    page = engine.materials(started['run_id'], event_key=hint['suggested_event_key'])
    assert page['memory']['record:' + created[0]]['text'].startswith('Fixture candidate 0')
    engine.mark_processed(started['run_id'], 1, {'record:' + created[0]: 'no-signal'})
    with pytest.raises(MemoryError) as error:
        engine.mark_processed(started['run_id'], 1, {'record:' + created[1]: 'no-signal'})
    assert error.value.code == 'unserved_event'


def test_default_inventory_lists_self_review_missing_sources_and_expired(tmp_path, monkeypatch):
    from shared_memory_mcp.dream_incremental import default_inventory
    engine, store, _, owner_caller, _, owner, _ = environment(tmp_path)
    gone = tmp_path / 'target' / 'gone.md'
    gone.write_text('Removed later.')
    def propose(title, source, key, **extra):
        return store.propose(owner_caller, {'scope': 'project', 'kind': 'observation', 'title': title, 'body': 'Synthetic.',
                                            'sources': [{'uri': source.as_uri()}], **extra}, key)['record']['id']
    self_reviewed = propose('Self reviewed', owner, 'self')
    store.promote(owner_caller, self_reviewed, {'reason': 'Same session review.', 'evidence': [{'uri': owner.as_uri()}]}, 'self-promote')
    missing = propose('Missing source', gone, 'missing')
    gone.unlink()
    expired = propose('Expired active', owner, 'expired', expires_at='2099-01-01T00:00:00Z')
    store.promote(owner_caller, expired, {'reason': 'Reviewed before expiry.', 'evidence': [{'uri': owner.as_uri()}]}, 'expired-promote')
    import datetime as clock
    import shared_memory_mcp.core as core
    class Later(clock.datetime):
        @classmethod
        def now(cls, tz=None):
            return clock.datetime(2100, 1, 1, tzinfo=tz)
    monkeypatch.setattr(core, 'datetime', Later)  # Only the lifecycle clock moves past expiry.
    reasons = {(i['ref'], i['reason']) for i in default_inventory(store, 'demo', {})['items']}
    assert ('record:' + self_reviewed, 'self-reviewed') in reasons and ('record:' + missing, 'missing-source') in reasons
    assert ('record:' + expired, 'expired-active') in reasons


# --- 2.7 views and budgets ------------------------------------------------------

def test_refreshed_view_carries_one_claim_and_hides_it_when_its_dependency_is_revoked(tmp_path):
    from dreaming_helpers import begin, claim, record_op, review
    engine, store, caller, owner_caller, policy, owner, human = environment(tmp_path)
    rid, gen, key, _ = begin(engine)
    carried = claim('op:P', text='The fixture record says coverage 7.')
    first = engine.freeze(rid, gen, [record_op('P', claim(key)),
                                     {'id': 'V', 'action': 'view_publish', 'view': 'research', 'claims': [carried], 'review': review(['op:P'])}])
    assert engine.publish(rid, gen, first['draft_revision'])['status'] == 'applied'
    engine.close(rid, gen)
    base = store.root / 'dreaming/views/demo/research'
    previous = json.loads((base / 'revisions' / (json.loads((base / 'current.json').read_text())['revision'] + '.json')).read_text())
    record_id = previous['dependencies'] and next(iter(previous['dependencies'].values()))['id']
    old = {**previous['claims'][0], 'refs': ['view-claim:' + previous['unit_bindings'][0]['claim_digest']]}
    rid2, gen2, key2, _ = begin(engine)
    fresh = claim(key2, text='A fresh fixture claim from the new run.')
    second = engine.freeze(rid2, gen2, [{'id': 'V2', 'action': 'view_publish', 'view': 'research', 'claims': [old, fresh],
                                         'review': review(old['refs'] + [key2])}])
    assert engine.publish(rid2, gen2, second['draft_revision'])['status'] == 'applied'
    current = engine.overview('research', scenario='research')
    assert len(current['items']) == 2
    carried_unit = next(u for u in current['items'] if u['index'] == 0)
    assert carried_unit['as_of'] == previous['as_of']
    store.delete(owner_caller, record_id, {'reason': 'Fixture revocation.', 'evidence': [{'uri': owner.as_uri()}]}, 'revoke')
    for historical in (None, current['revision']):
        result = engine.overview('research', scenario='research', historical=historical)
        assert [u['index'] for u in result['items']] == [1] and result['unavailable_units'][0]['index'] == 0
    # A claim that is not in the immediately previous revision cannot be carried.
    bad = engine.freeze(rid2, gen2, [{'id': 'V3', 'action': 'view_publish', 'view': 'research',
        'claims': [{**old, 'refs': ['view-claim:' + '0' * 64]}], 'review': review(['view-claim:' + '0' * 64])}])
    blocked = engine.publish(rid2, gen2, bad['draft_revision'])
    assert blocked['status'] == 'blocked' and blocked['unresolved'][0]['code'] == 'stale_view'


def test_reported_budgets_are_the_enforced_bounds_and_view_bytes_is_not_enforced(tmp_path):
    from dreaming_helpers import claim, view_op
    engine, store, caller, owner_caller, policy, owner, human = environment(tmp_path)
    updated = deepcopy(policy)
    updated['profiles']['fixture']['budgets'].update(view_bytes=1, view_chars=1)
    configure_policy(store, updated, expected_revision=_digest(policy))
    started = engine.start()
    assert set(started['budgets']) == {'source_bytes', 'events', 'operations'}
    key = engine.materials(started['run_id'])['sources']['owner']['events'][0]['key']
    frozen = engine.freeze(started['run_id'], 1, [view_op('V', claim(key))])
    assert engine.publish(started['run_id'], 1, frozen['draft_revision'])['status'] == 'applied'


def test_accepted_whole_source_gap_reopens_safely_when_the_file_returns(tmp_path):
    engine, store, _, root = codex_history(tmp_path, {'one': (['First fixture finding.'], ()), 'two': (['Second fixture finding.'], ())})
    first = engine.start(review_objective=OBJECTIVE)
    two = by_path(engine, first['run_id'])['two.jsonl']
    read_and_mark(engine, first['run_id'])
    engine.close(first['run_id'], 1, objective_outcome='reviewed')
    saved = (root / 'two.jsonl').read_bytes()
    (root / 'two.jsonl').unlink()
    second = engine.start(review_objective=OBJECTIVE)
    assert (two, 'source_unavailable') in {(g['source_id'], g['reason']) for g in second['objective_progress']['gaps']}
    read_and_mark(engine, second['run_id'])
    closed = engine.close(second['run_id'], 1, objective_outcome='reviewed',
                          accept_gaps=[{'source_id': two, 'reason': 'source_unavailable', 'note': 'Fixture file was removed.'}])
    assert closed['objective_completion'] == 'reviewed'
    (root / 'two.jsonl').write_bytes(saved + saved[saved.index(b'\n') + 1:])
    third = engine.start(review_objective=B)
    assert set(by_path(engine, third['run_id'])) == {'two.jsonl'}  # the returned file is pending again
    read_and_mark(engine, third['run_id'])
    assert engine.close(third['run_id'], 1, objective_outcome='reviewed')['objective_completion'] == 'reviewed'


# --- public operations path for the default objective and accepted gaps ---------

def test_public_dream_start_without_objective_binds_the_default_inventory(tmp_path):
    from shared_memory_mcp.operations import call
    engine, store, owner_caller, root = codex_history(tmp_path, {'one': (['History must stay unread.'], ())})
    owner = tmp_path / 'target' / 'owner.md'
    candidate = store.propose(owner_caller, {'scope': 'project', 'kind': 'observation', 'title': 'Public default candidate',
        'body': 'Synthetic.', 'sources': [{'uri': owner.as_uri()}]}, 'public-default')['record']['id']
    caller = {k: engine.caller[k] for k in ('cwd', 'harness', 'session_id', 'actor')}
    started = call(store, 'dream_start', {'caller': caller})
    item = started['item']
    assert item['review_objective']['id'] == 'default-maintenance'
    assert [(i['ref'], i['reason']) for i in item['inventory']['items']] == [('record:' + candidate, 'candidate')]
    assert item['objective_progress']['remaining_sources'] == 0 and by_path(engine, item['run_id']) == {}
    assert started['next'] == {'tool': 'dream_materials', 'args': {'caller': caller, 'run_id': item['run_id'],
                                                                     'event_key': 'record:' + candidate}}


def test_public_dream_close_accepts_a_permanent_gap_and_completes_the_objective(tmp_path):
    from shared_memory_mcp.operations import call
    engine, store, _, root = codex_history(tmp_path, {'gapped': (['Gapped fixture finding.'], (UNKNOWN,))})
    caller = {k: engine.caller[k] for k in ('cwd', 'harness', 'session_id', 'actor')}
    run_id = call(store, 'dream_start', {'caller': caller, 'review_objective': OBJECTIVE})['item']['run_id']
    gapped = by_path(engine, run_id)['gapped.jsonl']
    listing = call(store, 'dream_materials', {'caller': caller, 'run_id': run_id})
    assert {'source_id': gapped, 'reason': 'unknown_event_schema'} in listing['item']['gaps']
    draft = call(store, 'dream_draft', listing['next']['args'])  # served keys pre-filled as no-signal
    published = call(store, 'dream_publish', draft['next']['args'])
    assert published['next']['tool'] == 'dream_close'
    assert published['next']['optional']['accept_gaps'][0]['source_id'] == gapped
    closed = call(store, 'dream_close', {**published['next']['args'], 'objective_outcome': 'reviewed',
        'accept_gaps': [{'source_id': gapped, 'reason': 'unknown_event_schema', 'note': 'Future record type; no public text.'}]})
    assert closed['item']['objective_completion'] == 'reviewed'
    assert [(g['source_id'], g['reason']) for g in closed['item']['objective_progress']['accepted_gaps']] == [
        (gapped, 'unknown_event_schema')]
