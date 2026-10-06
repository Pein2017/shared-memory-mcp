"""Admission plus genuine frozen-baseline legacy recovery at public boundaries."""
import asyncio
import json
from pathlib import Path
import subprocess
import sys
import types

import pytest

from shared_memory_mcp.core import MemoryError, MemoryStore

BASELINE = '7963ccaa59abf8a27a1f86f4e517da124019fd5b'
SOURCE = [{'uri': 'file:///fixture/owner.md'}]
REVIEW = {'reason': 'Checked original source', 'evidence': SOURCE}
RECORD = {'kind': 'handoff', 'scope': 'project', 'title': 'Legacy transport',
          'body': 'Historical handoff bytes.', 'sources': SOURCE}


@pytest.fixture(scope='module')
def legacy_class():
    """Load frozen pre-policy source only to create authentic historical fixtures."""
    name = '_shared_memory_pre_admission_fixture'
    package = types.ModuleType(name)
    package.__path__ = []
    sys.modules[name] = package
    for module in ('core', 'curation', 'recall'):
        filename = f'src/shared_memory_mcp/{module}.py'
        raw = subprocess.run(['git', 'show', f'{BASELINE}:{filename}'],
                             cwd=Path(__file__).parents[1], capture_output=True, text=True)
        assert raw.returncode == 0, raw.stderr
        loaded = types.ModuleType(f'{name}.{module}')
        loaded.__package__ = name
        sys.modules[loaded.__name__] = loaded
        exec(compile(raw.stdout, f'{BASELINE}:{filename}', 'exec'), loaded.__dict__)
    yield sys.modules[name + '.core'].MemoryStore
    for key in list(sys.modules):
        if key == name or key.startswith(name + '.'):
            del sys.modules[key]


@pytest.fixture
def env(tmp_path):
    project = tmp_path / 'project'
    project.mkdir()
    store = MemoryStore(tmp_path / 'memory')
    store.init()
    store.register('fixture', [project])
    ctx = {'cwd': str(project), 'harness': 'codex', 'session_id': 'fixture', 'actor': 'codex'}
    return store, ctx


def snapshot(store):
    return {str(p.relative_to(store.root)): p.read_bytes() for p in store.root.rglob('*')
            if p.is_file() and '.writer-gate.sqlite3' not in p.name}


def blocked(call, store, code='unsupported_kind'):
    before = snapshot(store)
    with pytest.raises(MemoryError) as error:
        call()
    assert error.value.code == code
    if code == 'unsupported_kind':
        assert 'local handoff documents' in str(error.value).lower()
    assert snapshot(store) == before


@pytest.mark.parametrize('operation', ['create', 'capture-candidate', 'capture-reviewed'])
def test_new_handoff_rejected_before_persistent_writes(env, operation):
    store, ctx = env
    call = (lambda: store.propose(ctx, RECORD, 'new')) if operation == 'create' else (
        lambda: store.capture(ctx, RECORD, 'new', review=REVIEW if operation.endswith('reviewed') else None))
    blocked(call, store)


def test_legacy_create_replay_and_unfinished_publication(env, legacy_class):
    store, ctx = env
    legacy = legacy_class(store.root)
    candidate = legacy.propose(ctx, RECORD, 'create')['record']
    before = snapshot(store)
    replay = store.propose(ctx, RECORD, 'create')
    assert replay['replayed'] and replay['record']['id'] == candidate['id']
    assert snapshot(store) == before
    blocked(lambda: store.propose(ctx, {**RECORD, 'body': 'changed'}, 'create'), store, 'idempotency_conflict')
    blocked(lambda: store.promote(ctx, candidate['id'], REVIEW, 'new-approve'), store)
    predecessor = legacy.propose(ctx, {**RECORD, 'title': 'Predecessor'}, 'old')['record']
    legacy.promote(ctx, predecessor['id'], REVIEW, 'old-approve')
    blocked(lambda: store.supersede(ctx, candidate['id'], [predecessor['id']], REVIEW, 'new-update'), store)


def test_completed_legacy_approve_update_replay_and_retirement_withdrawal(env, legacy_class):
    store, ctx = env
    legacy = legacy_class(store.root)
    old = legacy.propose(ctx, {**RECORD, 'title': 'Old'}, 'old')['record']
    legacy.promote(ctx, old['id'], REVIEW, 'approved')
    successor = legacy.propose(ctx, RECORD, 'new')['record']
    legacy.supersede(ctx, successor['id'], [old['id']], REVIEW, 'updated')
    before = snapshot(store)
    assert store.promote(ctx, old['id'], REVIEW, 'approved')['replayed']
    assert store.supersede(ctx, successor['id'], [old['id']], REVIEW, 'updated')['replayed']
    assert snapshot(store) == before
    blocked(lambda: store.promote(ctx, old['id'], {**REVIEW, 'reason': 'changed'}, 'approved'), store, 'idempotency_conflict')
    blocked(lambda: store.supersede(ctx, successor['id'], [old['id']], {**REVIEW, 'reason': 'changed'}, 'updated'), store, 'idempotency_conflict')
    canonical = {p: data for p, data in before.items() if p.startswith('records/')}
    store.curate(ctx, successor['id'], REVIEW, 'retire', retired=True)
    assert store.search(ctx, '')['items'] == []
    assert store.read(ctx, [successor['id']], True)['items'][0]['effective_status'] == 'retired'
    store.delete(ctx, successor['id'], REVIEW, 'withdraw')
    assert store.read(ctx, [successor['id']], True)['items'][0]['effective_status'] == 'withdrawn'
    assert all(snapshot(store)[p] == data for p, data in canonical.items())


@pytest.mark.parametrize('reviewed', [False, True])
@pytest.mark.parametrize('binding', [False, True])
def test_completed_legacy_capture_exact_replay(env, legacy_class, reviewed, binding):
    store, ctx = env
    legacy = legacy_class(store.root)
    review = REVIEW if reviewed else None
    result = legacy.capture(ctx, RECORD, 'completed', review=review, details={'domain': 'engineering'})
    if not binding:
        for path in (store.root / 'capture').rglob('*.json'):
            path.unlink()  # Authentic pre-request-binding completed fixture.
    before = snapshot(store)
    replay = store.capture(ctx, RECORD, 'completed', review=review, details={'domain': 'engineering'})
    assert replay['replayed'] and replay['id'] == result['id']
    assert snapshot(store) == before
    for changed in ({'review': REVIEW if not reviewed else {**REVIEW, 'reason': 'changed'}},
                    {'details': {'domain': 'research'}}):
        arguments = {'review': review, 'details': {'domain': 'engineering'}, **changed}
        blocked(lambda: store.capture(ctx, RECORD, 'completed', **arguments), store, 'idempotency_conflict')


@pytest.mark.parametrize('boundary', ['request', 'candidate', 'curation'])
def test_unfinished_legacy_reviewed_capture_blocks_without_writes(env, legacy_class, boundary):
    store, ctx = env
    legacy = legacy_class(store.root)
    publish = legacy._publish
    def interrupted(path, data):
        publish(path, data)
        if ((boundary == 'request' and 'capture' in path.parts) or
                (boundary == 'candidate' and path.suffix == '.md') or
                (boundary == 'curation' and 'curation' in path.parts)):
            raise RuntimeError('frozen interruption')
    legacy._publish = interrupted
    with pytest.raises(RuntimeError):
        legacy.capture(ctx, RECORD, 'unfinished', review=REVIEW)
    blocked(lambda: store.capture(ctx, RECORD, 'unfinished', review=REVIEW), store)
    blocked(lambda: store.capture(ctx, RECORD, 'unfinished', review={**REVIEW, 'reason': 'changed'}), store, 'idempotency_conflict')


def test_legacy_unbound_candidate_capture_is_blocked(env, legacy_class):
    store, ctx = env
    legacy_class(store.root).propose(ctx, RECORD, 'capture:unbound')
    blocked(lambda: store.capture(ctx, RECORD, 'unbound', review=REVIEW), store)


def test_cli_call_rejection_and_completed_replay(env, legacy_class):
    store, ctx = env
    legacy = legacy_class(store.root)
    result = legacy.capture(ctx, RECORD, 'legacy', review=REVIEW)
    before = snapshot(store)
    def call(key):
        return subprocess.run([sys.executable, '-m', 'shared_memory_mcp.cli', '--root', str(store.root),
                               'call', '--tool', 'capture'],
                              input=json.dumps({'context': ctx, 'record': RECORD, 'idempotency_key': key, 'review': REVIEW}),
                              capture_output=True, text=True)
    replay = call('legacy')
    assert replay.returncode == 0, replay.stderr
    assert json.loads(replay.stdout)['id'] == result['id']
    rejected = call('new')
    assert rejected.returncode == 2
    assert json.loads(rejected.stdout)['diagnostic']['code'] == 'unsupported_kind'
    assert snapshot(store) == before


def test_fresh_stdio_admits_completed_legacy_payload_but_rejects_new_writes(env, legacy_class):
    pytest.importorskip('mcp')
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    store, ctx = env
    legacy = legacy_class(store.root)
    completed = legacy.capture(ctx, RECORD, 'published', review=REVIEW)
    candidate = legacy.capture(ctx, RECORD, 'candidate')
    proposed = legacy.propose(ctx, RECORD, 'created')['record']
    old = legacy.propose(ctx, {**RECORD, 'title': 'Old'}, 'old')['record']
    legacy.promote(ctx, old['id'], REVIEW, 'approved')
    successor = legacy.propose(ctx, {**RECORD, 'title': 'Successor'}, 'successor')['record']
    legacy.supersede(ctx, successor['id'], [old['id']], REVIEW, 'updated')
    before = snapshot(store)
    async def verify():
        params = StdioServerParameters(command=sys.executable,
            args=['-m', 'shared_memory_mcp.server', '--root', str(store.root)])
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                tools = (await session.list_tools()).tools
                assert len(tools) == 9
                record_schema = next(t for t in tools if t.name == 'create').inputSchema['$defs']['Record']
                assert 'deprecated' in record_schema['description']
                assert 'handoff' in record_schema['properties']['kind']['enum']
                async def call(tool, **args):
                    result = await session.call_tool(tool, {'context': ctx, **args})
                    assert not result.isError, result
                    return result.structuredContent or json.loads(result.content[0].text)
                assert (await call('create', record=RECORD, idempotency_key='created'))['record']['id'] == proposed['id']
                assert (await call('approve', id=old['id'], review=REVIEW, idempotency_key='approved'))['replayed']
                assert (await call('update', id=successor['id'], old_ids=[old['id']], review=REVIEW, idempotency_key='updated'))['replayed']
                assert (await call('capture', record=RECORD, review=REVIEW, idempotency_key='published'))['id'] == completed['id']
                assert (await call('capture', record=RECORD, idempotency_key='candidate'))['id'] == candidate['id']
                for tool, args in (
                    ('capture', {'record': RECORD, 'review': REVIEW, 'idempotency_key': 'new'}),
                    ('create', {'record': RECORD, 'idempotency_key': 'new-create'}),
                    ('approve', {'id': proposed['id'], 'review': REVIEW, 'idempotency_key': 'new-publish'}),
                    ('capture', {'record': RECORD, 'review': {**REVIEW, 'reason': 'changed'}, 'idempotency_key': 'published'}),
                ):
                    rejected = await session.call_tool(tool, {'context': ctx, **args})
                    assert rejected.isError, rejected
                assert snapshot(store) == before
    asyncio.run(verify())
