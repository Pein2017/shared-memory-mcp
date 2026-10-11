"""Pi structural proof and release-independent Codex public projection."""
from copy import deepcopy
import hashlib

import pytest

from shared_memory_mcp.core import _digest
from shared_memory_mcp.dream_sources import read_source
from shared_memory_mcp.dream_catalog import SourceCatalog
from test_dream_sources import source, line, HEADER, codex_message
from test_dream_catalog import catalog
from test_dream_source_regressions import selected_engine
from dreaming_helpers import environment, claim, record_op, view_op, freeze_publish


def pi_event(identifier, parent, role='assistant'):
    return {'type': 'message', 'id': identifier, 'parentId': parent,
            'message': {'role': role, 'content': [{'type': 'text', 'text': 'PRIVATE_BRIDGE' if role == 'toolResult' else 'Synthetic branch report.'}]}}


def pi_values(mode):
    values = [{'type': 'session', 'id': 'fixture-pi', 'version': 3}]
    if mode == 'private':
        return values + [pi_event('A', None, 'user'), pi_event('T', 'A', 'toolResult'), pi_event('C', 'T')]
    if mode == 'custom':
        return values + [pi_event('A', None, 'user'), {'type': 'custom', 'id': 'T', 'parentId': 'A', 'data': 'PRIVATE_BRIDGE'}, pi_event('C', 'T')]
    if mode == 'missing':
        return values + [pi_event('C', 'absent')]
    if mode == 'cycle':
        return values + [pi_event('T', 'C', 'toolResult'), pi_event('C', 'T')]
    if mode == 'conflict':
        return values + [pi_event('T', None, 'toolResult'), pi_event('C', 'T'), pi_event('T', 'C', 'toolResult')]
    return values + [{'type': 'future-node', 'id': 'T', 'parentId': None}, pi_event('C', 'T')]


@pytest.mark.parametrize('mode', ['private', 'custom', 'missing', 'cycle', 'conflict', 'unknown'])
def test_pi_direct_and_catalog_prove_structure_without_private_text(tmp_path, mode):
    direct = read_source(source(tmp_path, 'pi', pi_values(mode), leaf_id='C'))
    c, profile, path = catalog(tmp_path, values=pi_values(mode))
    profile['source_grants'][0].update(format='pi', schema='pi-session-v3')
    c = SourceCatalog(c.store, 'fixture', profile)
    page = c.read({'grant_id': 'history', 'path': path.name, 'leaf_id': 'C'})
    reconstructed = read_source(c.resolve([page['selection']])[0])
    for result in [direct, page, reconstructed]:
        assert 'PRIVATE_BRIDGE' not in str(result)
        if mode in {'private', 'custom'}:
            assert [e['event_id'] for e in result['events']] == ['A', 'C']
            assert all(e.get('ancestry_verified') is True for e in result['events'])
            assert result['coverage']['complete']
        else:
            assert result['events'] == []
            assert not result['coverage']['complete']


def test_legacy_catalog_descriptor_rechecks_unsafe_suffix(tmp_path):
    c, profile, path = catalog(tmp_path, values=pi_values('missing'))
    profile['source_grants'][0].update(format='pi', schema='pi-session-v3')
    c = SourceCatalog(c.store, 'fixture', profile)
    page = c.read({'grant_id': 'history', 'path': path.name, 'leaf_id': 'C'})
    spec = c.resolve([page['selection']])[0]
    spec['_catalog_page'].pop('ancestry_revision', None)
    spec['_catalog_page']['admitted'] = [len(line(pi_values('missing')[0]))]
    assert read_source(spec)['events'] == []


def test_pi_missing_ancestor_cannot_publish_record_or_view(tmp_path):
    _, store, caller, consumer, policy, _, path = environment(tmp_path)
    values = pi_values('missing')
    path.write_bytes(b''.join(line(v) for v in values))
    spec = {'id': 'pi', 'path': str(path), 'format': 'pi', 'schema': 'pi-session-v3'}
    engine = selected_engine(store, caller, policy, spec)
    run = engine.start(sources=[{'grant_id': 'pi', 'leaf_id': 'C'}])
    wrong_key = _digest(['pi', 'fixture-pi', 'C', hashlib.sha256(line(values[-1])).hexdigest()])
    statement = claim(wrong_key, level='report')
    _, result = freeze_publish(engine, run['run_id'], run['generation'], [record_op('R', statement), view_op('V', statement)])
    assert result['status'] == 'blocked'
    assert store._load('demo') == []
    assert engine.overview('research', scenario='research')['status'] == 'navigation'


@pytest.mark.parametrize('release', ['0.156.1', '0.159.2', 'future-fixture-release'])
def test_codex_release_is_provenance_not_projection_gate(tmp_path, release):
    header = deepcopy(HEADER); header['payload']['cli_version'] = release
    values = [header, {'type': 'world_state', 'payload': {'full': True, 'state': {'private': 'PRIVATE_STATE'}}},
              {'type': 'token_usage_record', 'payload': {**{k: {} for k in ('usage', 'turn_token_usage', 'thread_token_usage')},
               **{k: 'synthetic' for k in ('thread_id', 'turn_id', 'session_id', 'root_turn_id', 'response_id')}}}, codex_message()]
    spec = source(tmp_path, 'codex', values, native_version='different-current-release')
    direct = read_source(spec)
    c, profile, path = catalog(tmp_path, values=values)
    profile['source_grants'][0].pop('native_version')
    c = SourceCatalog(c.store, 'fixture', profile)
    page = c.read({'grant_id': 'history', 'path': path.name})
    reconstructed = read_source(c.resolve([page['selection']])[0])
    for result in [direct, page, reconstructed]:
        assert result['coverage']['complete']
        assert [e['event_id'] for e in result['events']] == ['u1']
        assert result['events'][0]['native_version'] == release
        assert 'PRIVATE_STATE' not in str(result)


def test_unknown_codex_wire_event_remains_gap(tmp_path):
    result = read_source(source(tmp_path, 'codex', [HEADER, {'type': 'future-unknown', 'text': 'PRIVATE_UNKNOWN'}]))
    assert result['events'] == []
    assert result['coverage']['gaps'][0]['reason'] == 'unknown_event_schema'


def test_unknown_codex_response_item_remains_gap(tmp_path):
    result = read_source(source(tmp_path, 'codex', [HEADER, {'type': 'response_item', 'payload': {'type': 'future-item', 'text': 'PRIVATE_UNKNOWN'}}]))
    assert result['events'] == []
    assert result['coverage']['gaps'][0]['reason'] == 'unknown_event_schema'


def test_pi_bounded_continuation_carries_only_structural_proof(tmp_path):
    values = pi_values('private')
    spec = source(tmp_path, 'pi', values, leaf_id='C')
    first = read_source(spec, max_events=1)
    second = read_source(spec, cursor=first['cursor'])
    assert [e['event_id'] for e in first['events']] == ['A']
    assert [e['event_id'] for e in second['events']] == ['C']
    assert second['events'][0]['ancestry_verified'] is True
    assert 'PRIVATE_BRIDGE' not in str(second['cursor'])
    c, profile, path = catalog(tmp_path, values=values)
    profile['source_grants'][0].update(format='pi', schema='pi-session-v3')
    c = SourceCatalog(c.store, 'fixture', profile)
    selection = {'grant_id': 'history', 'path': path.name, 'leaf_id': 'C'}
    first = c.read(selection, max_events=1)
    second = c.read(selection, cursor=first['next_cursor'])
    assert [e['event_id'] for e in second['events']] == ['C']
    assert read_source(c.resolve([second['selection']])[0])['events'] == second['events']


def test_pi_later_page_conflict_cannot_reuse_prior_bridge(tmp_path):
    values = pi_values('private')[:3] + [pi_event('T', None, 'toolResult'), pi_event('C', 'T')]
    spec = source(tmp_path, 'pi', values, leaf_id='C')
    first = read_source(spec, max_events=1)
    second = read_source(spec, cursor=first['cursor'])
    assert second['events'] == []
    assert any(g['reason'] == 'conflicting_event_identity' for g in second['coverage']['gaps'])


@pytest.mark.parametrize('bridge', ['system', 'toolResult'])
def test_pi_recognized_private_roles_keep_only_edges(tmp_path, bridge):
    values = [{'type': 'session', 'id': 'fixture-pi', 'version': 3}, pi_event('T', None, bridge), pi_event('C', 'T')]
    result = read_source(source(tmp_path, 'pi', values, leaf_id='C'))
    assert [e['event_id'] for e in result['events']] == ['C']
    assert result['events'][0]['ancestry_verified'] is True


def test_pi_missing_parent_field_does_not_forge_a_root(tmp_path):
    values = pi_values('private')
    values[1].pop('parentId')
    result = read_source(source(tmp_path, 'pi', values, leaf_id='C'))
    assert result['events'] == []


@pytest.mark.parametrize('kind,payload', [('world_state', {'full': 'yes', 'state': {}}),
                                         ('world_state', {'full': True, 'state': []}),
                                         ('token_usage_record', {'usage': {}, 'thread_id': 'synthetic'}),
                                         ('token_usage_record', None)])
def test_unknown_nonpublic_codex_shapes_remain_gaps(tmp_path, kind, payload):
    result = read_source(source(tmp_path, 'codex', [HEADER, {'type': kind, 'payload': payload}]))
    assert result['events'] == []
    assert result['coverage']['gaps'][0]['reason'] == 'unknown_event_schema'


def test_saved_resume_branch_uses_last_persisted_entry_not_last_message(tmp_path):
    values = [pi_values('private')[0], pi_event('A', None), pi_event('B', 'A'),
              pi_event('C', 'A'), {'type': 'label', 'id': 'L', 'parentId': 'B', 'targetId': 'B', 'label': 'saved'}]
    spec = source(tmp_path, 'pi', values)
    saved = read_source(spec)
    assert [e['event_id'] for e in saved['events']] == ['A', 'B']
    assert all(e['branch'] == 'L' and e['branch_selection'] == 'saved-resume' for e in saved['events'])
    assert saved['coverage']['complete']
    explicit = read_source({**spec, 'leaf_id': 'C'})
    assert [e['event_id'] for e in explicit['events']] == ['A', 'C']
    assert all(e['branch_selection'] == 'explicit' for e in explicit['events'])


def test_pi_full_ancestry_admits_early_page_and_reuses_structure(tmp_path, monkeypatch):
    values = pi_values('private')
    spec = source(tmp_path, 'pi', values, leaf_id='C')
    direct = read_source(spec, max_events=1)
    assert [e['event_id'] for e in direct['events']] == ['A']
    c, profile, path = catalog(tmp_path, values=values)
    profile['source_grants'][0].update(format='pi', schema='pi-session-v3')
    c = SourceCatalog(c.store, 'fixture', profile)
    selection = {'grant_id': 'history', 'path': path.name, 'leaf_id': 'C'}
    first = c.read(selection, max_events=1)
    assert [e['event_id'] for e in first['events']] == ['A']
    import shared_memory_mcp.dream_sources as readers
    def no_rescan(*args, **kwargs):
        raise AssertionError('Full structural scan repeated for a frozen page')
    monkeypatch.setattr(readers, '_scan_pi_structure', no_rescan)
    c = SourceCatalog(c.store, 'fixture', profile)
    second = c.read(selection, cursor=first['next_cursor'])
    assert [e['event_id'] for e in second['events']] == ['C']
    assert read_source(c.resolve([first['selection']])[0])['events'] == first['events']
    assert read_source(c.resolve([second['selection']])[0])['events'] == second['events']
    assert second['coverage']['structure_bytes'] == 0


@pytest.mark.parametrize('harness', ['codex', 'pi'])
def test_large_native_event_all_three_decoders_preserve_identity(tmp_path, harness):
    text = 'public-fixture ' * 10000 + 'TAIL'
    event = codex_message(text) if harness == 'codex' else pi_event('A', None)
    if harness == 'pi':
        event['message']['content'] = text
    values = [HEADER if harness == 'codex' else pi_values('private')[0], event]
    spec = source(tmp_path, harness, values)
    direct = read_source(spec)
    c, profile, path = catalog(tmp_path, values=values)
    profile['source_grants'][0].update(format=harness, schema=spec['schema'])
    c = SourceCatalog(c.store, 'fixture', profile)
    page = c.read({'grant_id': 'history', 'path': path.name})
    rebuilt = read_source(c.resolve([page['selection']])[0])
    for result in [direct, page, rebuilt]:
        assert len(result['events']) == 1
        assert result['events'][0]['text'] == text
        assert result['coverage']['complete']
    assert page['events'] == rebuilt['events']
    for field in ['key', 'raw_digest', 'locator', 'byte_start', 'event_id']:
        assert direct['events'][0][field] == page['events'][0][field]


@pytest.mark.parametrize('reader', ['snapshot', 'catalog'])
def test_large_event_budget_boundary_keeps_exact_start_until_widened(tmp_path, reader):
    values = [HEADER, codex_message('public-fixture ' * 10000)]
    if reader == 'snapshot':
        spec = source(tmp_path, 'codex', values)
        first = read_source(spec, max_bytes=65537)
        retry = read_source(spec, max_bytes=65537, cursor=first['cursor'])
        enlarged = read_source(spec, cursor=retry['cursor'])
        offset = first['cursor']['offset']
    else:
        c, _, path = catalog(tmp_path, values=values)
        selection = {'grant_id': 'history', 'path': path.name}
        first = c.read(selection, max_bytes=65537)
        retry = c.read(selection, max_bytes=65537, cursor=first['next_cursor'])
        enlarged = c.read(selection, cursor=retry['next_cursor'])
        offset = first['version']['consumed']
    assert first['events'] == retry['events'] == []
    assert not first['coverage']['complete']
    gap = next(g for g in retry['coverage']['gaps'] if g['reason'] == 'event_exceeds_remaining_budget')
    assert gap['next_offset'] == offset == len(line(HEADER))
    assert gap['required_bytes_at_least'] == 65538
    assert gap['supported_event_bytes'] == 8 * 1024 * 1024
    assert [e['event_id'] for e in enlarged['events']] == ['u1']
    assert enlarged['coverage']['complete']


@pytest.mark.parametrize('change', ['rewrite', 'revoke'])
def test_pi_cached_graph_rejects_changes_outside_consumed_page(tmp_path, change):
    import os
    from shared_memory_mcp.core import MemoryError
    c, profile, path = catalog(tmp_path, values=pi_values('private'))
    profile['source_grants'][0].update(format='pi', schema='pi-session-v3')
    c = SourceCatalog(c.store, 'fixture', profile)
    selection = {'grant_id': 'history', 'path': path.name, 'leaf_id': 'C'}
    first = c.read(selection, max_events=1)
    spec = c.resolve([first['selection']])[0]
    if change == 'rewrite':
        before = path.stat()
        path.write_bytes(path.read_bytes().replace(b'"parentId": "T"', b'"parentId": "A"'))
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    else:
        profile['source_grants'][0]['attestations'] = {'0' * 64: {'subject': 'Pein', 'basis': 'Changed grant'}}
        c = SourceCatalog(c.store, 'fixture', profile)
        assert not c.authorized(spec)
    with pytest.raises(MemoryError):
        c.read(selection, cursor=first['next_cursor'])
    with pytest.raises(MemoryError):
        c.resolve([first['selection']])


@pytest.mark.parametrize('harness', ['codex', 'pi'])
def test_large_sensitive_tail_is_filtered_before_any_page_admission(tmp_path, harness):
    text = 'public-fixture ' * 10000 + ' sk-' + 'x' * 24
    event = codex_message(text) if harness == 'codex' else pi_event('A', None)
    if harness == 'pi':
        event['message']['content'] = text
    values = [HEADER if harness == 'codex' else pi_values('private')[0], event]
    spec = source(tmp_path, harness, values)
    c, profile, path = catalog(tmp_path, values=values)
    profile['source_grants'][0].update(format=harness, schema=spec['schema'])
    c = SourceCatalog(c.store, 'fixture', profile)
    page = c.read({'grant_id': 'history', 'path': path.name})
    for result in [read_source(spec), page, read_source(c.resolve([page['selection']])[0])]:
        assert result['events'] == []
        assert not result['coverage']['complete']
        assert any(g['reason'] == 'sensitive_content_excluded' for g in result['coverage']['gaps'])


def test_native_event_parse_ceiling_is_separate_from_public_page_budget(tmp_path, monkeypatch):
    import shared_memory_mcp.dream_sources as readers
    values = [HEADER, codex_message('public-fixture ' * 10000)]
    spec = source(tmp_path, 'codex', values)
    c, _, path = catalog(tmp_path, values=values)
    # A small ceiling exercises the same rejection without allocating an 8MiB fixture.
    monkeypatch.setattr(readers, 'MAX_NATIVE_EVENT', 65536)
    for result in [read_source(spec), c.read({'grant_id': 'history', 'path': path.name})]:
        assert result['events'] == []
        assert any(g['reason'] == 'oversized_event' for g in result['coverage']['gaps'])
        assert not result['coverage']['complete']


def test_pi_cache_io_does_not_change_page_identity_or_retain_transcript(tmp_path):
    import json
    c, profile, path = catalog(tmp_path, values=pi_values('private'))
    profile['source_grants'][0].update(format='pi', schema='pi-session-v3')
    c = SourceCatalog(c.store, 'fixture', profile)
    selection = {'grant_id': 'history', 'path': path.name}
    first = c.read(selection)
    cached = c.read(selection)
    assert first['selection'] == cached['selection']
    assert first['coverage']['structure_bytes'] == path.stat().st_size
    assert cached['coverage']['structure_bytes'] == 0
    with c._db() as db:
        retained = ''.join(row[0] for row in db.execute('SELECT body FROM structures'))
        retained += ''.join(row[0] for row in db.execute('SELECT body FROM handles'))
    assert 'PRIVATE_BRIDGE' not in retained and 'Synthetic branch report.' not in retained
    rebuilt = read_source(c.resolve([first['selection']])[0])
    assert rebuilt['events'] == first['events']
    assert rebuilt['coverage']['structure_bytes'] == 0


@pytest.mark.parametrize('reader', ['snapshot', 'catalog'])
def test_rejected_event_continuation_keeps_following_physical_line(tmp_path, reader, monkeypatch):
    import shared_memory_mcp.dream_sources as readers
    monkeypatch.setattr(readers, 'MAX_NATIVE_EVENT', 65536)
    following = codex_message('Following original event.', identifier='following')
    values = [HEADER, codex_message('public-fixture ' * 20000), following]
    if reader == 'snapshot':
        spec = source(tmp_path, 'codex', values)
        read = lambda cursor: read_source(spec, cursor=cursor, max_bytes=65537)
    else:
        c, _, path = catalog(tmp_path, values=values)
        read = lambda cursor: c.read({'grant_id': 'history', 'path': path.name}, cursor=cursor, max_bytes=65537)
    cursor, admitted = None, []
    for _ in range(12):
        page = read(cursor)
        admitted.extend(page['events'])
        cursor = page['cursor'] if reader == 'snapshot' else page['next_cursor']
        if page['version']['consumed'] == page['version']['cutoff']:
            break
    assert [e['event_id'] for e in admitted] == ['following']
    assert admitted[0]['locator'] == 'line:3'
    assert admitted[0]['byte_start'] == len(line(HEADER)) + len(line(values[1]))


@pytest.mark.parametrize('reader', ['snapshot', 'catalog'])
def test_pi_total_structure_limit_rejects_before_payload_io(tmp_path, reader, monkeypatch):
    import shared_memory_mcp.dream_sources as readers
    from shared_memory_mcp.core import MemoryError
    monkeypatch.setattr(readers, 'MAX_PI_STRUCTURE_BYTES', 65536)
    values = [pi_values('private')[0], pi_event('saved', None)]
    if reader == 'snapshot':
        spec = source(tmp_path, 'pi', values)
        from pathlib import Path
        path = Path(spec['path'])
        read = lambda: read_source(spec)
    else:
        c, profile, path = catalog(tmp_path, values=values)
        profile['source_grants'][0].update(format='pi', schema='pi-session-v3')
        c = SourceCatalog(c.store, 'fixture', profile)
        read = lambda: c.read({'grant_id': 'history', 'path': path.name})
    assert read()['events'][0]['branch_selection'] == 'saved-resume'
    path.write_bytes(line(values[0]) + line({**values[1], 'message': {'role': 'assistant', 'content': 'x' * 65536}}))
    def no_payload_io(*args, **kwargs):
        raise AssertionError('Structural payload read before total-size rejection')
    monkeypatch.setattr(readers, '_native_line', no_payload_io)
    with pytest.raises(MemoryError) as error:
        read()
    assert error.value.code == 'source_limit'
    assert 'Pi structural scan requires' in str(error.value)
    assert 'fixed limit is 65536 bytes' in str(error.value)


@pytest.mark.parametrize('catalog_page', [False, True])
def test_large_pi_graph_through_catalog_run_and_material_body(tmp_path, monkeypatch, catalog_page):
    import json
    from shared_memory_mcp.core import MAX_RECORD_BYTES
    from shared_memory_mcp.dreaming import configure_policy
    engine, store, _, _, policy, _, path = environment(tmp_path)
    values = [pi_values('private')[0]]
    for index in range(4000):
        values.append({'type': 'custom', 'id': f'bridge-{index:05d}-' + 'n' * 100,
                       'parentId': values[-1]['id'] if index else None, 'data': 'PRIVATE_PAYLOAD'})
    text = 'Synthetic public final body. ' * 400 + 'TAIL'
    final = pi_event('saved', values[-1]['id'])
    final['message']['content'] = text
    values.append(final)
    path.write_bytes(b''.join(line(v) for v in values))
    updated = deepcopy(policy)
    updated['profiles']['fixture']['source_grants'][1].update(format='pi', schema='pi-session-v3', attestations={})
    updated['profiles']['fixture']['budgets']['source_bytes'] = 8 * 1024 * 1024
    configure_policy(store, updated, expected_revision=_digest(policy))
    cursor, page = None, None
    while True:
        page = engine.source_read({'grant_id': 'human'}, cursor=cursor)
        if page['events']:
            break
        cursor = page['next_cursor']
        assert cursor is not None
    assert [e['event_id'] for e in page['events']] == ['saved']
    run = engine.start(sources=[page['selection'] if catalog_page else {'grant_id': 'human'}])
    raw = (store.root / 'dreaming/runs' / run['run_id'] / 'run.json').read_bytes()
    assert len(raw) < MAX_RECORD_BYTES
    assert b'PRIVATE_PAYLOAD' not in raw and b'"parents"' not in raw
    frozen = engine.materials(run['run_id'], 'human')['sources']['human']['events'][0]
    import shared_memory_mcp.dream_sources as readers
    def no_rescan(*args, **kwargs):
        raise AssertionError('Full graph scanned again for material page')
    monkeypatch.setattr(readers, '_scan_pi_structure', no_rescan)
    body = engine.materials(run['run_id'], 'human', event_key=frozen['key'], max_chars=16000)
    assert body['sources']['human']['events'][0]['text'] == text
    assert body['sources']['human']['events'][0]['key'] == frozen['key']
    assert engine.source_read({'grant_id': 'human'}, cursor=cursor)['events'] == page['events']


@pytest.mark.parametrize('mode', ['evicted', 'corrupt'])
def test_pi_graph_reference_rebuild_and_exact_digest_fence(tmp_path, mode):
    import json
    from shared_memory_mcp.core import MemoryError
    c, profile, path = catalog(tmp_path, values=pi_values('private'))
    profile['source_grants'][0].update(format='pi', schema='pi-session-v3')
    c = SourceCatalog(c.store, 'fixture', profile)
    page = c.read({'grant_id': 'history', 'path': path.name})
    spec = c.resolve([page['selection']])[0]
    reference = spec['_catalog_page']['state_before']['pi_metadata']
    assert set(reference) == {'cache_key', 'sha256', 'epoch', 'cutoff', 'projection_revision', 'raw_sha256'}
    with c._db() as db:
        if mode == 'evicted':
            db.execute('DELETE FROM structures')
        else:
            token, raw = db.execute('SELECT token, body FROM structures').fetchone()
            metadata = json.loads(raw)
            metadata['parents']['T']['parent'] = None
            metadata['sha256'] = _digest({k: v for k, v in metadata.items() if k != 'sha256'})
            db.execute('UPDATE structures SET body=? WHERE token=?', (json.dumps(metadata), token))
    if mode == 'corrupt':
        with pytest.raises(MemoryError) as error:
            read_source(spec)
        assert error.value.code == 'source_changed'
        assert 'frozen graph digest' in str(error.value)
    else:
        rebuilt = read_source(spec)
        assert rebuilt['events'] == page['events']
        assert rebuilt['coverage']['structure_bytes'] == path.stat().st_size
        second = read_source(spec)
        assert second['events'] == page['events']
        assert second['coverage']['structure_bytes'] == 0


def test_pi_graph_capacity_is_separate_from_public_page_limit(tmp_path, monkeypatch):
    import shared_memory_mcp.dream_sources as readers
    from shared_memory_mcp.core import MemoryError
    monkeypatch.setattr(readers, 'MAX_PI_GRAPH_NODES', 2)
    values = pi_values('private')
    spec = source(tmp_path, 'pi', values)
    with pytest.raises(MemoryError) as error:
        read_source(spec, max_events=1024)
    assert error.value.code == 'source_limit'
    assert 'fixed limit of 2 identities' in str(error.value)
    with pytest.raises(MemoryError):
        read_source(spec, max_events=1025)


def test_public_source_selection_cannot_inject_graph_cache_owner(tmp_path):
    from shared_memory_mcp.core import MemoryError
    c, profile, path = catalog(tmp_path, values=pi_values('private'))
    profile['source_grants'][0].update(format='pi', schema='pi-session-v3')
    c = SourceCatalog(c.store, 'fixture', profile)
    selection = {'grant_id': 'history', 'path': path.name,
                 '_structure_cache': {'path': '/untrusted.sqlite3', 'owner': 'untrusted'}}
    with pytest.raises(MemoryError) as error:
        c.read(selection)
    assert error.value.code == 'invalid_input'
    with pytest.raises(MemoryError):
        c.resolve([selection])


def test_pi_completed_page_replay_rebuilds_evicted_cache(tmp_path):
    c, profile, path = catalog(tmp_path, values=pi_values('private'))
    profile['source_grants'][0].update(format='pi', schema='pi-session-v3')
    c = SourceCatalog(c.store, 'fixture', profile)
    selection = {'grant_id': 'history', 'path': path.name}
    first = c.read(selection, max_events=1)
    second = c.read(selection, cursor=first['next_cursor'])
    with c._db() as db:
        db.execute('DELETE FROM structures')
    replay = c.read(selection, cursor=first['next_cursor'])
    assert replay['events'] == second['events']
    assert replay['selection'] == second['selection']
    assert replay['next_cursor'] == second['next_cursor']
    assert replay['coverage']['structure_bytes'] == path.stat().st_size
    assert c.read(selection, cursor=first['next_cursor'])['coverage']['structure_bytes'] == 0


def native_private_edge_values():
    return [pi_values('private')[0], pi_event('A', None, 'user'),
        {'type': 'custom_message', 'id': 'M', 'parentId': 'A', 'customType': 'fixture',
         'content': 'PRIVATE_CUSTOM', 'display': False},
        {'type': 'usage', 'id': 'U', 'parentId': 'M', 'kind': 'arbitrary-native-kind',
         'provider': 'fixture', 'model': 'fixture', 'usage': {'private': 'PRIVATE_USAGE'}},
        {'type': 'compaction', 'id': 'K', 'parentId': 'U', 'summary': 'PRIVATE_COMPACTION',
         'firstKeptEntryId': 'A', 'tokensBefore': 7},
        {'type': 'context_edit', 'id': 'E', 'parentId': 'K', 'targetId': 'A',
         'replacement': {'content': 'PRIVATE_REPLACEMENT'}}, pi_event('C', 'E'),
        {'type': 'branch_summary', 'id': 'B', 'parentId': 'A', 'fromId': 'C', 'summary': 'PRIVATE_BRANCH'},
        pi_event('D', 'B')]


@pytest.mark.parametrize('attested', [False, True])
def test_native_private_edges_preserve_original_saved_and_explicit_branches(tmp_path, attested):
    from test_dream_sources import attest
    values = native_private_edge_values()
    attestations = attest(values[1]) if attested else {}
    attestations.update(attest(values[2]))  # Extension-injected content never becomes a human event.
    spec = source(tmp_path, 'pi', values, attestations=attestations)
    explicit = read_source({**spec, 'leaf_id': 'C'})
    assert [e['event_id'] for e in explicit['events']] == ['A', 'C']
    saved = read_source(spec)
    c, profile, path = catalog(tmp_path, values=values)
    profile['source_grants'][0].update(format='pi', schema='pi-session-v3', attestations=attestations)
    c = SourceCatalog(c.store, 'fixture', profile)
    page = c.read({'grant_id': 'history', 'path': path.name})
    for result in [saved, page, read_source(c.resolve([page['selection']])[0])]:
        assert [e['event_id'] for e in result['events']] == ['A', 'D']
        assert not result['coverage']['complete']
        assert any(g['reason'] == 'compaction_originals_not_proven' for g in result['coverage']['gaps'])
        assert not any(g['reason'] == 'unknown_event_schema' for g in result['coverage']['gaps'])
        assert 'PRIVATE_' not in str(result)
        assert result['events'][0]['human'] == ('attested-Pein' if attested else 'unknown')
        assert result['events'][1]['human'] == 'unknown'
        assert all(e['ancestry_verified'] for e in result['events'])


@pytest.mark.parametrize('failure', ['unknown', 'missing', 'cycle', 'conflict'])
def test_native_private_edge_recognition_keeps_unsafe_ancestry_closed(tmp_path, failure):
    values = native_private_edge_values()
    if failure == 'unknown':
        values[2]['type'] = 'future-node'
    elif failure == 'missing':
        values[2].pop('parentId')
    elif failure == 'cycle':
        values[2]['parentId'] = 'C'
    else:
        values.append({**values[2], 'parentId': 'C'})
    spec = source(tmp_path, 'pi', values, leaf_id='C')
    c, profile, path = catalog(tmp_path, values=values)
    profile['source_grants'][0].update(format='pi', schema='pi-session-v3')
    c = SourceCatalog(c.store, 'fixture', profile)
    page = c.read({'grant_id': 'history', 'path': path.name, 'leaf_id': 'C'})
    for result in [read_source(spec), page, read_source(c.resolve([page['selection']])[0])]:
        assert result['events'] == []
        assert not result['coverage']['complete']
        assert 'PRIVATE_' not in str(result)


def test_native_private_edges_reach_run_material_consumer(tmp_path):
    from shared_memory_mcp.dreaming import configure_policy
    engine, store, _, _, policy, _, path = environment(tmp_path)
    values = native_private_edge_values()
    path.write_bytes(b''.join(line(v) for v in values))
    updated = deepcopy(policy)
    updated['profiles']['fixture']['source_grants'][1].update(format='pi', schema='pi-session-v3', attestations={})
    configure_policy(store, updated, expected_revision=_digest(policy))
    page = engine.source_read({'grant_id': 'human'})
    assert [e['event_id'] for e in page['events']] == ['A', 'D']
    run = engine.start(sources=[page['selection']])
    frozen = engine.materials(run['run_id'], 'human')['sources']['human']
    assert [e['event_id'] for e in frozen['events']] == ['A', 'D']
    assert not frozen['coverage']['complete']
    event = frozen['events'][1]
    body = engine.materials(run['run_id'], 'human', event_key=event['key'], max_chars=16000)
    assert body['sources']['human']['events'][0]['text'] == values[-1]['message']['content'][0]['text']
    assert body['sources']['human']['events'][0]['human'] == 'unknown'
    assert 'PRIVATE_' not in str(body)
    assert body['sources']['human']['coverage']['complete'] is False


def test_old_pi_graph_reference_becomes_explicit_gap_without_repinning(tmp_path):
    import json
    from shared_memory_mcp.core import MemoryError
    from shared_memory_mcp.dream_incremental import collect
    c, profile, path = catalog(tmp_path, values=native_private_edge_values())
    profile['source_grants'][0].update(format='pi', schema='pi-session-v3')
    c = SourceCatalog(c.store, 'fixture', profile)
    page = c.read({'grant_id': 'history', 'path': path.name})
    spec = c.resolve([page['selection']])[0]
    legacy = deepcopy(spec)
    legacy['_catalog_page']['state_before']['pi_metadata'].pop('projection_revision')
    receipt = json.dumps(legacy, sort_keys=True)
    version = deepcopy(legacy['_catalog_page']['version'])
    before_bytes = path.read_bytes()
    with c._db() as db:
        handles_before = list(db.execute('SELECT token, body FROM handles ORDER BY token'))
        structures_before = list(db.execute('SELECT token, body FROM structures ORDER BY token'))
    with pytest.raises(MemoryError) as error:
        read_source(legacy)
    assert error.value.code == 'unsupported_structure_revision'
    materials, _, _ = collect({'sources': [legacy], 'budgets': {'source_bytes': 1048576, 'events': 32}})
    assert materials[legacy['id']]['events'] == []
    assert materials[legacy['id']]['coverage']['gaps'][0]['reason'] == 'unsupported_structure_revision'
    assert json.dumps(legacy, sort_keys=True) == receipt
    assert legacy['_catalog_page']['version'] == version
    assert path.read_bytes() == before_bytes
    with c._db() as db:
        assert list(db.execute('SELECT token, body FROM handles ORDER BY token')) == handles_before
        assert list(db.execute('SELECT token, body FROM structures ORDER BY token')) == structures_before
