"""Caller-per-call gateway qualification using the installed official MCP SDK."""
import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from dreaming_helpers import environment, claim, record_op, view_op
from shared_memory_mcp.core import MemoryError, _digest
from shared_memory_mcp.dreaming import configure_policy

ENV = {**os.environ, 'PYTHONPATH': str(Path(__file__).parents[1] / 'src'), 'PYTHONDONTWRITEBYTECODE': '1'}


def gateway_args(store, *extra):
    return ['-m', 'shared_memory_mcp.cli', '--root', str(store.root), 'dream', 'gateway', '--profile', 'fixture', *extra]


def value(result):
    assert not result.isError, result
    return result.structuredContent or json.loads(result.content[0].text)


def test_gateway_factory_startup_without_caller(tmp_path):
    from shared_memory_mcp.dream_gateway import make_dream_gateway
    _, store, *_ = environment(tmp_path)
    make_dream_gateway(store, 'fixture')
    with pytest.raises(MemoryError):
        make_dream_gateway(store, 'missing')


def test_gateway_cli_surface(tmp_path):
    _, store, *_ = environment(tmp_path)
    result = subprocess.run([sys.executable, *gateway_args(store), '--help'], env=ENV, capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert '--enable-publisher' in result.stdout
    assert '--session-id' not in result.stdout and '--cwd' not in result.stdout


def test_gateway_stdio_identity_isolation_and_publication(tmp_path):
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from shared_memory_mcp.server import make_server
    _, store, a, owner_caller, policy, owner, human = environment(tmp_path)
    b = {**a, 'session_id': 'fixture-executor-B', 'harness': 'pi', 'actor': 'fixture-B'}
    outsider = tmp_path / 'outsider'; outsider.mkdir(); store.register('outsider', [outsider])
    before = {p: p.read_bytes() for p in (owner, human)}
    async def sequence():
        advisory = StdioServerParameters(command=sys.executable, args=gateway_args(store), env=ENV)
        async with stdio_client(advisory) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                tools = (await session.list_tools()).tools
                assert len(tools) == 14 and 'draft_publish' not in {t.name for t in tools}
                assert all('context' in t.inputSchema['required'] for t in tools)
                # Both overlapping and sequential calls must preserve each caller.
                catalogs = await asyncio.gather(*(session.call_tool('dream_catalog', {'context': c}) for c in (a, b)))
                assert all(not r.isError for r in catalogs)
                runs = [value(await session.call_tool('run_start', {'context': a})),
                        value(await session.call_tool('run_start', {'context': b, 'sources': [{'grant_id': 'owner'}]}))]
                for run, caller in zip(runs, (a, b)):
                    observed = value(await session.call_tool('run_observe', {'context': caller, 'run_id': run['run_id']}))
                    assert observed['attempts'][-1]['caller']['session_id'] == caller['session_id']
                    assert observed['attempts'][-1]['identity_assurance'] == 'caller-declared; native-session-unverified'
                rid = runs[0]['run_id']
                overlap = await asyncio.gather(
                    session.call_tool('run_materials', {'context': a, 'run_id': rid}),
                    session.call_tool('run_materials', {'context': b, 'run_id': rid}))
                assert not overlap[0].isError and overlap[1].isError
                assert not (await session.call_tool('run_materials', {'context': a, 'run_id': rid})).isError
                negatives = [
                    ('dream_catalog', {}),
                    ('dream_catalog', {'context': {**a, 'profile': 'other'}}),
                    ('dream_catalog', {'context': {**a, 'publisher': True}}),
                    ('dream_catalog', {'context': a, 'profile': 'other'}),
                    ('dream_catalog', {'context': a, 'enable_publisher': True}),
                    ('dream_catalog', {'context': {**a, 'cwd': str(outsider)}}),
                    ('dream_catalog', {'context': {**a, 'cwd': str(tmp_path / 'unregistered')}}),
                    ('dream_catalog', {'context': {**a, 'session_id': ''}}),
                    ('dream_catalog', {'context': {**a, 'project_id': 'demo'}}),
                    ('run_start', {'context': a, 'target_project': 'runner'}),
                    ('source_list', {'context': a, 'grant_id': 'missing'}),
                    ('source_list', {'context': a, 'grant_id': 'owner', 'relative_dir': '../escape'}),
                    ('source_read', {'context': a, 'selection': {'grant_id': 'owner', 'path': '/etc/passwd'}}),
                    ('draft_publish', {'context': a, 'run_id': rid, 'generation': 1, 'revision': '0' * 64}),
                    ('draft_submit', {'context': b, 'run_id': rid, 'generation': 1, 'operations': []}),
                ]
                for name, arguments in negatives:
                    assert (await session.call_tool(name, arguments)).isError, (name, arguments)
                takeover = value(await session.call_tool('run_takeover', {'context': b, 'run_id': rid, 'generation': 1}))
                assert takeover['generation'] == 2
                assert (await session.call_tool('draft_submit', {'context': a, 'run_id': rid, 'generation': 1, 'operations': []})).isError
                assert (await session.call_tool('draft_submit', {'context': a, 'run_id': rid, 'generation': 2, 'operations': []})).isError
                observed = value(await session.call_tool('run_observe', {'context': b, 'run_id': rid}))
                assert observed['attempts'][-1]['caller']['session_id'] == b['session_id']
                assert observed['attempts'][-1]['identity_assurance'] == 'caller-declared; native-session-unverified'
                material = value(await session.call_tool('run_materials', {'context': b, 'run_id': rid, 'source_id': 'owner'}))
                key = material['sources']['owner']['events'][0]['key']
                draft = value(await session.call_tool('draft_submit', {'context': b, 'run_id': rid, 'generation': 2,
                    'operations': [record_op('A', claim(key)), view_op('V', claim('op:A'))]}))
        publisher = StdioServerParameters(command=sys.executable, args=gateway_args(store, '--enable-publisher'), env=ENV)
        async with stdio_client(publisher) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                assert len((await session.list_tools()).tools) == 15
                result = value(await session.call_tool('draft_publish', {'context': b, 'run_id': rid, 'generation': 2, 'revision': draft['draft_revision']}))
                assert result['status'] == 'applied'
                view = value(await session.call_tool('overview_read', {'context': b, 'view': 'research', 'scenario': 'research'}))
                assert view['status'] == 'valid' and 'coverage 7' in view['text']
                record_id = draft['operations'][0]['reserved_id']
                # Exercise the ordinary final consumer, not only Dreaming receipts.
                ordinary = make_server(store)
                read = await ordinary.call_tool('read', {'context': owner_caller, 'ids': [record_id]})
                contents = read[0] if isinstance(read, tuple) else read
                ordinary_payload = json.loads(contents.content[0].text)
                assert ordinary_payload['items'][0]['id'] == record_id
                assert 'coverage 7' in ordinary_payload['items'][0]['body']
                # A live process must re-evaluate source and executor grants on each call.
                revoked = deepcopy(policy)
                revoked['profiles']['fixture']['source_grants'] = [revoked['profiles']['fixture']['source_grants'][1]]
                configure_policy(store, revoked, expected_revision=_digest(policy))
                assert (await session.call_tool('source_read', {'context': b, 'selection': {'grant_id': 'owner'}})).isError
                hidden = value(await session.call_tool('overview_read', {'context': b, 'view': 'research', 'scenario': 'research'}))
                assert hidden['status'] == 'invalidated' and not hidden['text']
                denied = deepcopy(revoked)
                denied['profiles']['fixture']['executor_projects'] = ['demo']
                configure_policy(store, denied, expected_revision=_digest(revoked))
                assert (await session.call_tool('dream_catalog', {'context': b})).isError
                return record_id
    record_id = asyncio.run(sequence())
    record = next(item for item in store._load('demo') if item['id'] == record_id)
    assert record['provenance']['session_id'] == b['session_id']
    assert record['provenance']['harness'] == b['harness']
    assert all(p.read_bytes() == raw for p, raw in before.items())
