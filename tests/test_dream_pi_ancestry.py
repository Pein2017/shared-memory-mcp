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
    assert first['events'] == []
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
