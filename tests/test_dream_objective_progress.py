from copy import deepcopy
import json

import pytest

from shared_memory_mcp.core import MAX_RECORD_BYTES, MemoryError, _json
from shared_memory_mcp.dream_incremental import (
    load_objective, objective_batch, objective_close, objective_inventory, objective_observe, save_objective,
)
from dreaming_helpers import environment


OBJECTIVE = {'id': 'historical-baseline', 'question': 'Review the applicable history.'}
BUDGETS = {'source_bytes': 1048576, 'events': 128}


def closed_run(progress, selections, catalog, *, pending=False):
    materials = {}
    for selection in selections:
        spec = catalog.resolve([selection])[0]
        page = progress['sources'][spec['id']]['pending_page']
        materials[spec['id']] = {'version': deepcopy(page['version']), 'events': [
            {'key': key} for key in page['event_keys']], 'coverage': deepcopy(page['coverage'])}
    processed = {key: 'pending-review' if pending else 'no-signal'
                 for m in materials.values() for key in [e['key'] for e in m['events']]}
    processed.update({'source:' + sid: 'no-signal' for sid, m in materials.items() if not m['events']})
    return {'id': 'batch-one', 'phase': 'closed', 'checkpoint': {'run_id': 'batch-one'},
            'materials': materials, 'processed': processed, 'memory_inputs': {},
            'review_objective': OBJECTIVE, 'technical_outcome': 'ok', 'unresolved': []}


def test_batch_delivery_does_not_advance_baseline(tmp_path):
    engine, *_ = environment(tmp_path)
    catalog = engine._catalog()
    progress = objective_inventory(catalog, OBJECTIVE)
    staged, selections = objective_batch(catalog, progress, BUDGETS)
    assert objective_observe(staged)['remaining_sources'] == 2
    assert all(s['reviewed_offset'] == 0 for s in staged['sources'].values())
    pending = objective_close(staged, closed_run(staged, selections, catalog, pending=True))
    assert objective_observe(pending)['remaining_sources'] == 2
    complete = objective_close(staged, closed_run(staged, selections, catalog))
    assert objective_observe(complete)['remaining_sources'] == 0
    assert objective_close(complete, closed_run(staged, selections, catalog)) == complete


def test_unclosed_run_and_wrong_range_cannot_advance(tmp_path):
    engine, *_ = environment(tmp_path)
    catalog = engine._catalog()
    progress, selections = objective_batch(catalog, objective_inventory(catalog, OBJECTIVE), BUDGETS)
    run = closed_run(progress, selections, catalog)
    run['phase'] = 'collecting'
    with pytest.raises(MemoryError):
        objective_close(progress, run)
    run['phase'] = 'closed'
    next(iter(run['materials'].values()))['version']['consumed'] += 1
    with pytest.raises(MemoryError):
        objective_close(progress, run)


def test_recursive_native_roots_more_than_one_batch_and_expansion(tmp_path):
    engine, store, caller, _, _, _, human = environment(tmp_path)
    root = tmp_path / 'native'
    (root / 'older').mkdir(parents=True)
    for i in range(18):
        (root / 'older' / f'{i:02}.jsonl').write_bytes(human.read_bytes())
    profile = deepcopy(engine._policy()[1])
    profile.update(read_access='inherited', history_roots=[{
        'path': str(root), 'format': 'codex', 'schema': 'codex-rollout-v1', 'native_version': 'fixture-v1'}])
    catalog = engine._catalog(profile)
    progress = objective_inventory(catalog, OBJECTIVE)
    assert len(progress['sources']) == 20
    staged, selections = objective_batch(catalog, progress, BUDGETS)
    assert len(selections) == 16
    closed = objective_close(staged, closed_run(staged, selections, catalog))
    assert objective_observe(closed)['remaining_sources'] == 4
    staged, selections = objective_batch(catalog, closed, BUDGETS)
    run = closed_run(staged, selections, catalog)
    run['id'] = 'batch-two'; run['checkpoint']['run_id'] = 'batch-two'
    closed = objective_close(staged, run)
    assert objective_observe(closed)['remaining_sources'] == 0
    correction = root / 'correction.jsonl'
    correction.write_bytes(human.read_bytes())
    expanded = objective_inventory(catalog, OBJECTIVE, previous=closed, selections=[{
        'absolute_path': str(correction), 'format': 'codex', 'schema': 'codex-rollout-v1',
        'native_version': 'fixture-v1'}])
    assert objective_observe(expanded)['remaining_sources'] == 1


def test_active_append_is_deferred_and_memory_needs_explicit_revision(tmp_path):
    engine, _, _, _, _, _, human = environment(tmp_path)
    catalog = engine._catalog()
    ref = {'ref': 'record:synthetic', 'revision': 'revision-one'}
    progress = objective_inventory(catalog, OBJECTIVE, memory_refs=[ref])
    cutoff = next(s['cutoff'] for s in progress['sources'].values() if s['path'] == str(human))
    with human.open('ab') as stream:
        stream.write(b'{"type":"future"}\n')
    staged, selections = objective_batch(catalog, progress, BUDGETS)
    assert next(s['cutoff'] for s in staged['sources'].values() if s['path'] == str(human)) == cutoff
    run = closed_run(staged, selections, catalog)
    run['processed'][ref['ref']] = 'no-signal'
    closed = objective_close(staged, run)
    assert objective_observe(closed)['remaining_memory'] == 1
    run['id'] = 'memory-review'; run['checkpoint']['run_id'] = run['id']
    run['materials'] = {}; run['memory_inputs'] = {ref['ref']: {'revision': ref['revision']}}
    closed = objective_close(closed, run)
    assert objective_observe(closed)['remaining_memory'] == 0


def test_missing_and_unreviewable_empty_sources_remain_explicit(tmp_path):
    engine, _, _, _, _, owner, _ = environment(tmp_path)
    catalog = engine._catalog()
    owner.write_text('')
    progress = objective_inventory(catalog, OBJECTIVE)
    staged, selections = objective_batch(catalog, progress, BUDGETS)
    run = closed_run(staged, selections, catalog)
    run['processed'].pop('source:owner')
    closed = objective_close(staged, run)
    assert objective_observe(closed)['remaining_sources'] == 1
    owner.unlink()
    resumed, selections = objective_batch(catalog, closed, BUDGETS)
    assert objective_observe(resumed)['remaining_sources'] == 1
    assert objective_observe(resumed)['gaps']


def test_exact_page_cursor_survives_batches_and_pending_gap(tmp_path):
    engine, _, _, _, _, _, human = environment(tmp_path)
    original = human.read_bytes().splitlines(keepends=True)
    message = json.loads(original[1])
    with human.open('ab') as stream:
        for i in range(4):
            message['id'] = f'later-{i}'
            stream.write((json.dumps(message) + '\n').encode())
    catalog = engine._catalog()
    budgets = {**BUDGETS, 'events': 2}
    progress = objective_inventory(catalog, OBJECTIVE, selections=[{'grant_id': 'human'}])
    first_keys = set()
    for batch in range(3):
        staged, selected = objective_batch(catalog, progress, budgets)
        page = staged['sources']['human']['pending_page']
        assert page['version']['start'] == progress['sources']['human']['reviewed_offset']
        assert not first_keys.intersection(page['event_keys'])
        first_keys.update(page['event_keys'])
        run = closed_run(staged, selected, catalog)
        run['id'] = f'batch-{batch}'; run['checkpoint']['run_id'] = run['id']
        if batch == 0:
            invalid = deepcopy(run)
            invalid['materials']['human']['coverage']['gaps'].append({'reason': 'excerpt_truncated'})
            blocked = objective_close(staged, invalid)
            assert blocked['sources']['human']['reviewed_offset'] == 0
            assert objective_observe(blocked)['remaining_sources'] == 1
        progress = objective_close(staged, run)
    assert len(first_keys) == 5
    assert objective_observe(progress)['remaining_sources'] == 0


def test_objective_binding_and_revision_cannot_be_reused(tmp_path):
    engine, *_ = environment(tmp_path)
    catalog = engine._catalog()
    progress = objective_inventory(catalog, OBJECTIVE, binding={'target': 'demo'},
                                   memory_refs=[{'ref': 'record:one', 'revision': 'v1'}])
    with pytest.raises(MemoryError):
        objective_inventory(catalog, OBJECTIVE, previous=progress, binding={'target': 'other'})
    with pytest.raises(MemoryError):
        objective_inventory(catalog, OBJECTIVE, previous=progress, binding={'target': 'demo'},
                            memory_refs=[{'ref': 'record:one', 'revision': 'v2'}])


def test_production_sized_metadata_is_sharded_and_roundtrips(tmp_path):
    engine, store, *_ = environment(tmp_path)
    progress = objective_inventory(engine._catalog(), OBJECTIVE)
    template = progress['sources']['human']
    progress['sources'] = {f'fixture-{i:04}': {**deepcopy(template),
        'path': f'/synthetic/history/2026/10/session-{i:04}.jsonl'} for i in range(8500)}
    progress['memory'] = {f'record:fixture-{i}': {'revision': f'v{i}', 'status': 'pending'}
                          for i in range(18)}
    assert len(_json(progress).encode()) > MAX_RECORD_BYTES
    with store._gate():
        descriptor = save_objective(store, progress)
        assert save_objective(store, progress) == descriptor
    assert len(_json(descriptor).encode()) < 256
    assert load_objective(store, descriptor) == progress
    files = list((store.root / 'dreaming/checkpoints/objectives').glob('*.json'))
    assert len(files) > 2
    assert all(path.stat().st_size <= MAX_RECORD_BYTES for path in files)
    assert len(objective_observe(progress)['ready_memory']) == 16


@pytest.mark.parametrize('damage', ['missing', 'changed', 'malformed'])
def test_objective_missing_or_corrupted_shard_fails_closed(tmp_path, damage):
    engine, store, *_ = environment(tmp_path)
    progress = objective_inventory(engine._catalog(), OBJECTIVE)
    with store._gate():
        descriptor = save_objective(store, progress)
    folder = store.root / 'dreaming/checkpoints/objectives'
    manifest = json.loads((folder / (descriptor['manifest'] + '.json')).read_text())
    shard = folder / (manifest['shards'][0]['digest'] + '.json')
    if damage == 'missing':
        shard.unlink()
    elif damage == 'malformed':
        shard.write_text('{broken')
    else:
        document = json.loads(shard.read_text())
        document['entries'][0][1]['reviewed_offset'] += 1
        shard.write_text(json.dumps(document))
    with pytest.raises(MemoryError):
        load_objective(store, descriptor)
    if damage == 'missing':
        with store._gate():
            assert save_objective(store, progress) == descriptor
        assert load_objective(store, descriptor) == progress
    else:
        with store._gate(), pytest.raises(MemoryError):
            save_objective(store, progress)


def test_objective_shards_split_by_bytes_and_keep_backend_guards(tmp_path):
    engine, store, *_ = environment(tmp_path)
    progress = objective_inventory(engine._catalog(), OBJECTIVE)
    progress['memory'] = {'record:large-one': {'revision': 'v1', 'status': 'pending', 'metadata': 'x' * 600000},
                          'record:large-two': {'revision': 'v1', 'status': 'pending', 'metadata': 'y' * 600000}}
    with store._gate():
        descriptor = save_objective(store, progress)
    assert load_objective(store, descriptor) == progress
    progress['memory']['record:large-one']['metadata'] = 'x' * MAX_RECORD_BYTES
    with store._gate(), pytest.raises(MemoryError):
        save_objective(store, progress)
    progress['memory'] = {f'record:{i}': {'revision': 'v1', 'status': 'pending'} for i in range(10001)}
    with store._gate(), pytest.raises(MemoryError):
        save_objective(store, progress)
