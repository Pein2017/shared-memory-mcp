"""Frozen-event continuation through real readers and CLI/MCP consumers."""
import asyncio
from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
import sys

import pytest

from dreaming_helpers import environment, claim, record_op, freeze_publish
from shared_memory_mcp.core import MemoryError, _digest
from shared_memory_mcp.dreaming import add_disposition, configure_policy
from test_dream_transport import ENV, args_for, cli, payload


def long_run(tmp_path, *, catalog=False, history=False):
    engine, store, caller, consumer, policy, owner, human = environment(tmp_path)
    text = 'Bounded owner observation. 飞机🛫\n' * 210 + 'TAIL: joint preservation FAILED; no promotion.\n'
    if history:
        header = human.read_text().splitlines()[0]
        human.write_text(header + '\n' + json.dumps({'type': 'response_item', 'id': 'long-report',
            'payload': {'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': text}]}}) + '\n')
        sid = 'human'
    else:
        owner.write_text(text)
        sid = 'owner'
    selection = engine.source_read({'grant_id': sid})['selection'] if catalog else {'grant_id': sid}
    run = engine.start(sources=[selection])
    event = engine.materials(run['run_id'], sid)['sources'][sid]['events'][0]
    return engine, store, caller, consumer, policy, owner, run, sid, event, text


@pytest.mark.parametrize('catalog,history', [(False, False), (True, False), (False, True), (True, True)])
def test_all_parts_restore_tail_and_keep_original_evidence_and_coverage(tmp_path, catalog, history):
    engine, store, _, consumer, _, _, run, sid, event, text = long_run(tmp_path, catalog=catalog, history=history)
    assert event['excerpt_truncated'] and len(event['text']) == 4096
    path = store.root / 'dreaming/runs' / run['run_id'] / 'run.json'
    before = path.read_bytes()
    cursor, chunks = None, []
    while True:
        result = engine.materials(run['run_id'], sid, event_key=event['key'], cursor=cursor, max_chars=1537)
        assert result == engine.materials(run['run_id'], sid, event_key=event['key'], cursor=cursor, max_chars=1537)
        part = result['sources'][sid]['events'][0]
        assert {k:v for k,v in part.items() if k != 'text'} == {k:v for k,v in event.items() if k != 'text'}
        assert result['page']['offset'] == sum(map(len, chunks))
        assert result['page']['total_chars'] == len(text)
        assert result['page']['text_sha256'] == hashlib.sha256(text.encode()).hexdigest()
        assert result['sources'][sid]['coverage']['complete'] is False
        chunks.append(part['text'])
        cursor = result['page']['next_cursor']
        if cursor is None:
            break
    assert ''.join(chunks) == text and len(chunks) > 1
    assert path.read_bytes() == before
    c = claim(event['key'], level='report' if history else 'recorded', text=text.splitlines()[-1])
    frozen, published = freeze_publish(engine, run['run_id'], run['generation'], [record_op('R', c)])
    assert published['status'] == 'applied'
    read = store.read(consumer, [frozen['operations'][0]['reserved_id']])
    assert 'joint preservation FAILED' in read['items'][0]['body']


@pytest.mark.parametrize('change', ['source', 'grant', 'disposition', 'cursor', 'event'])
def test_continuation_rechecks_frozen_identity_and_current_access(tmp_path, change):
    engine, store, caller, _, policy, owner, run, sid, event, _ = long_run(tmp_path, catalog=True)
    first = engine.materials(run['run_id'], sid, event_key=event['key'], max_chars=1000)
    cursor = first['page']['next_cursor']
    key = event['key']
    if change == 'source':
        owner.write_text(owner.read_text().replace('FAILED', 'PASSED'))
    elif change == 'grant':
        updated = deepcopy(policy)
        updated['profiles']['fixture']['source_grants'] = [s for s in updated['profiles']['fixture']['source_grants'] if s['id'] != sid]
        configure_policy(store, updated, expected_revision=_digest(policy))
    elif change == 'disposition':
        add_disposition(store, caller, target='demo', topic='*', scope='research', source_keys=[key],
                        kind='no_reuse', reason='Synthetic source-use revocation')
    elif change == 'cursor':
        token = json.loads(cursor.removeprefix('material-v1:')); token['binding'] = '0' * 64
        cursor = 'material-v1:' + json.dumps(token)
    else:
        key = '0' * 64
    with pytest.raises(MemoryError):
        engine.materials(run['run_id'], sid, event_key=key, cursor=cursor, max_chars=1000)


def test_cli_continues_one_bound_event(tmp_path):
    _, store, caller, _, _, _, run, sid, event, text = long_run(tmp_path)
    base = ('--run-id', run['run_id'], '--source-id', sid, '--event-key', event['key'], '--max-chars', '4096')
    cursor, parts = None, []
    while True:
        result = cli(store, caller, 'materials', *base, *(['--cursor', cursor] if cursor else []))
        parts.append(result['sources'][sid]['events'][0]['text'])
        cursor = result['page']['next_cursor']
        if cursor is None:
            break
    assert ''.join(parts) == text


@pytest.mark.parametrize('catalog', [False, True])
def test_reconstruction_io_is_reported_and_read_budget_bounds_response(tmp_path, monkeypatch, catalog):
    import shared_memory_mcp.dream_sources as sources
    import shared_memory_mcp.dream_catalog as catalog_module
    engine, _, _, _, _, _, run, sid, event, _ = long_run(tmp_path, catalog=catalog)
    original, consumed = sources._open_source, []
    class Measured:
        def __init__(self, stream):
            self.stream = stream
        def __getattr__(self, key):
            return getattr(self.stream, key)
        def read(self, *args):
            data = self.stream.read(*args); consumed.append(len(data)); return data
    @contextmanager
    def measured(spec):
        with original(spec) as stream:
            yield Measured(stream)
    monkeypatch.setattr(sources, '_open_source', measured)
    monkeypatch.setattr(catalog_module, '_open_source', measured)
    result = engine.materials(run['run_id'], sid, event_key=event['key'], max_chars=500)
    assert len(result['sources'][sid]['events'][0]['text']) == 500
    assert sum(consumed) == result['page']['read_bytes'] + result['page']['verification_bytes']


def test_disposition_changed_during_reconstruction_blocks_return(tmp_path, monkeypatch):
    import shared_memory_mcp.dreaming as dreaming
    engine, store, caller, _, _, _, run, sid, event, _ = long_run(tmp_path)
    original = dreaming.read_source
    def revoked(*args, **kwargs):
        result = original(*args, **kwargs)
        add_disposition(store, caller, target='demo', topic='*', scope='research', source_keys=[event['key']],
                        kind='no_reuse', reason='Synthetic concurrent revocation')
        return result
    monkeypatch.setattr(dreaming, 'read_source', revoked)
    with pytest.raises(MemoryError) as error:
        engine.materials(run['run_id'], sid, event_key=event['key'])
    assert error.value.code == 'dream_access_denied'


def test_history_append_does_not_change_the_frozen_event(tmp_path):
    engine, _, _, _, _, _, run, sid, event, text = long_run(tmp_path, history=True)
    spec = engine._run(run['run_id'])['profile_snapshot']['sources'][0]
    from pathlib import Path
    with Path(spec['path']).open('a') as stream:
        stream.write(json.dumps({'type': 'response_item', 'id': 'later', 'payload': {
            'type': 'message', 'role': 'assistant', 'content': [{'type': 'output_text', 'text': 'NEW UNSELECTED CONTENT'}]}}) + '\n')
    result = engine.materials(run['run_id'], sid, event_key=event['key'], max_chars=16000)
    assert result['sources'][sid]['events'][0]['text'] == text
    assert result['page']['next_cursor'] is None


def test_direct_pi_parts_reuse_frozen_structure_and_reject_changed_epoch(tmp_path, monkeypatch):
    import shared_memory_mcp.dream_sources as sources
    from test_dream_source_regressions import selected_engine
    engine, store, caller, _, policy, _, path = environment(tmp_path)
    text = 'Synthetic selected Pi report. 飞机\n' * 210
    entries = [{'type': 'session', 'id': 'fixture-pi', 'version': 3},
               {'type': 'message', 'id': 'A', 'parentId': None,
                'message': {'role': 'assistant', 'content': [{'type': 'text', 'text': text}]}}]
    path.write_text(''.join(json.dumps(e) + '\n' for e in entries))
    engine = selected_engine(store, caller, policy,
                             {'id': 'pi', 'path': str(path), 'format': 'pi', 'schema': 'pi-session-v3'})
    run = engine.start(sources=[{'grant_id': 'pi', 'leaf_id': 'A'}])
    event = engine.materials(run['run_id'], 'pi')['sources']['pi']['events'][0]
    def no_rescan(*args, **kwargs):
        pytest.fail('Frozen Pi structure was scanned again for a text part')
    monkeypatch.setattr(sources, '_scan_pi_structure', no_rescan)
    cursor, parts = None, []
    while True:
        result = engine.materials(run['run_id'], 'pi', event_key=event['key'], cursor=cursor, max_chars=1000)
        parts.append(result['sources']['pi']['events'][0]['text'])
        cursor = result['page']['next_cursor']
        if cursor is None:
            break
    assert ''.join(parts) == text
    with path.open('a') as stream:
        stream.write(json.dumps({'type': 'session_info', 'id': 'B', 'parentId': 'A', 'name': 'Synthetic append'}) + '\n')
    with pytest.raises(MemoryError) as error:
        engine.materials(run['run_id'], 'pi', event_key=event['key'], max_chars=1000)
    assert error.value.code == 'source_changed'


@pytest.mark.parametrize('catalog', [False, True])
def test_pi_body_reports_cache_eviction_rebuild_io(tmp_path, monkeypatch, catalog):
    import shared_memory_mcp.dream_sources as sources
    import shared_memory_mcp.dream_catalog as catalog_module
    from test_dream_source_regressions import selected_engine
    from test_dream_pi_ancestry import pi_values
    engine, store, caller, _, policy, _, path = environment(tmp_path)
    path.write_text(''.join(json.dumps(e) + '\n' for e in pi_values('private')))
    engine = selected_engine(store, caller, policy,
                             {'id': 'pi', 'path': str(path), 'format': 'pi', 'schema': 'pi-session-v3'})
    selection = {'grant_id': 'pi', 'leaf_id': 'C'}
    if catalog:
        selection = engine.source_read(selection)['selection']
    run = engine.start(sources=[selection])
    event = engine.materials(run['run_id'], 'pi')['sources']['pi']['events'][-1]
    with engine._catalog()._db() as db:
        db.execute('DELETE FROM structures')
    original, consumed = sources._open_source, []
    class Measured:
        def __init__(self, stream):
            self.stream = stream
        def __getattr__(self, key):
            return getattr(self.stream, key)
        def read(self, *args):
            data = self.stream.read(*args); consumed.append(len(data)); return data
        def readline(self, *args):
            data = self.stream.readline(*args); consumed.append(len(data)); return data
    @contextmanager
    def measured(spec):
        with original(spec) as stream:
            yield Measured(stream)
    monkeypatch.setattr(sources, '_open_source', measured)
    monkeypatch.setattr(catalog_module, '_open_source', measured)
    result = engine.materials(run['run_id'], 'pi', event_key=event['key'])
    assert sum(consumed) == result['page']['read_bytes'] + result['page']['verification_bytes']
    consumed.clear()
    repeated = engine.materials(run['run_id'], 'pi', event_key=event['key'])
    assert sum(consumed) == repeated['page']['read_bytes'] + repeated['page']['verification_bytes']
    assert result['page']['verification_bytes'] - repeated['page']['verification_bytes'] == path.stat().st_size


@pytest.mark.parametrize('mode', ['fixed', 'general', 'gateway'])
def test_stdio_continues_without_expanding_source_grants(tmp_path, mode):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    _, store, caller, _, _, _, run, sid, event, text = long_run(tmp_path, catalog=True)
    if mode == 'gateway':
        args = ['-m', 'shared_memory_mcp.cli', '--root', str(store.root), 'dream', 'gateway', '--profile', 'fixture']
    else:
        args = args_for(store, caller, 'serve', *(['--run-id', run['run_id'], '--generation', str(run['generation'])] if mode == 'fixed' else []))

    async def read_all():
        async with stdio_client(StdioServerParameters(command=sys.executable, args=args, env=ENV)) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                name = 'source_read' if mode == 'fixed' else 'run_materials'
                arguments = {'source_id': sid, 'event_key': event['key'], 'max_chars': 2000}
                if mode != 'fixed':
                    arguments['run_id'] = run['run_id']
                if mode == 'gateway':
                    arguments['context'] = caller
                assert (await session.call_tool(name, {**arguments, 'source_id': '/etc/passwd'})).isError
                parts = []
                while True:
                    result = payload(await session.call_tool(name, arguments))
                    parts.append(result['sources'][sid]['events'][0]['text'])
                    cursor = result['page']['next_cursor']
                    if cursor is None:
                        break
                    arguments['cursor'] = cursor
                return ''.join(parts)
    assert asyncio.run(read_all()) == text


@pytest.mark.parametrize('harness', ['codex', 'pi'])
@pytest.mark.parametrize('catalog', [False, True])
def test_large_native_event_body_pages_keep_identity_and_current_fences(tmp_path, harness, catalog, monkeypatch):
    from pathlib import Path
    from shared_memory_mcp.dream_sources import FORMATS
    from test_dream_sources import HEADER, codex_message, line
    engine, store, caller, _, policy, _, native = environment(tmp_path)
    text = 'Synthetic public body. 飞机🛫\n' * 2200 + 'TAIL: unchanged limits.'
    event = codex_message(text, role='assistant') if harness == 'codex' else {
        'type': 'message', 'id': 'saved', 'parentId': None,
        'message': {'role': 'assistant', 'content': [{'type': 'text', 'text': text}]}}
    native.write_bytes(line(HEADER if harness == 'codex' else {'type': 'session', 'id': 'fixture-pi', 'version': 3}) + line(event))
    assert len(line(event)) > 65536
    updated = deepcopy(policy)
    updated['profiles']['fixture']['budgets']['source_bytes'] = 2 * 1024 * 1024
    grant = updated['profiles']['fixture']['source_grants'][1]
    grant.update(format=harness, schema=FORMATS[harness], attestations={})
    configure_policy(store, updated, expected_revision=_digest(policy))
    selection = engine.source_read({'grant_id': 'human'})['selection'] if catalog else {'grant_id': 'human'}
    run = engine.start(sources=[selection])
    frozen = engine.materials(run['run_id'], 'human')['sources']['human']['events'][0]
    saved = Path(store.root / 'dreaming/runs' / run['run_id'] / 'run.json').read_bytes()
    if harness == 'pi':
        import shared_memory_mcp.dream_sources as readers
        def no_rescan(*args, **kwargs):
            raise AssertionError('Body chunk rescanned full Pi structural ancestry')
        monkeypatch.setattr(readers, '_scan_pi_structure', no_rescan)
    cursor, chunks = None, []
    while True:
        result = engine.materials(run['run_id'], 'human', event_key=frozen['key'], cursor=cursor, max_chars=16000)
        part = result['sources']['human']['events'][0]
        assert {k: v for k, v in part.items() if k != 'text'} == {k: v for k, v in frozen.items() if k != 'text'}
        assert result['sources']['human']['coverage']['complete'] is False
        chunks.append(part['text'])
        cursor = result['page']['next_cursor']
        if cursor is None:
            break
    assert ''.join(chunks) == text
    assert len(chunks) > 1
    assert Path(store.root / 'dreaming/runs' / run['run_id'] / 'run.json').read_bytes() == saved
    first = engine.materials(run['run_id'], 'human', event_key=frozen['key'], max_chars=1000)
    # The continuation is fenced even when event and file lengths are unchanged.
    native.write_bytes(native.read_bytes().replace(b'unchanged limits', b'untrusted limits'))
    with pytest.raises(MemoryError) as error:
        engine.materials(run['run_id'], 'human', event_key=frozen['key'], cursor=first['page']['next_cursor'])
    assert error.value.code == 'source_changed'
    revoked = deepcopy(updated)
    revoked['profiles']['fixture']['source_grants'] = revoked['profiles']['fixture']['source_grants'][:1]
    configure_policy(store, revoked, expected_revision=_digest(updated))
    with pytest.raises(MemoryError) as error:
        engine.materials(run['run_id'], 'human', event_key=frozen['key'], cursor=first['page']['next_cursor'])
    assert error.value.code == 'dream_access_denied'
