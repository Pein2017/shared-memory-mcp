"""Actual subprocess CLI and official MCP stdio clients, with no model/provider calls."""
import asyncio
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from dreaming_helpers import environment, begin, claim, review, record_op, view_op, freeze_publish
from shared_memory_mcp.adapters import handle_hook
from shared_memory_mcp.dreaming import add_disposition

SOURCE = str(Path(__file__).parents[1] / 'src')
ENV = {**os.environ, 'PYTHONPATH': SOURCE, 'PYTHONDONTWRITEBYTECODE': '1'}


def args_for(store, caller, action, *extra):
    args = ['-m', 'shared_memory_mcp.cli', '--root', str(store.root), 'dream', action,
            '--profile', 'fixture', '--cwd', caller['cwd'], '--harness', caller['harness'],
            '--session-id', caller['session_id'], '--actor', caller['actor']]
    return args + list(extra)


def cli(store, caller, action, *extra, data=None, expected=0):
    run = subprocess.run([sys.executable, *args_for(store, caller, action, *extra)],
                         input=json.dumps(data) if data is not None else None,
                         capture_output=True, text=True, env=ENV, timeout=30)
    assert run.returncode == expected, (run.stdout, run.stderr)
    return json.loads(run.stdout)


def payload(response):
    assert not response.isError, response
    return response.structuredContent or json.loads(response.content[0].text)


@pytest.mark.parametrize('harness', ['codex', 'pi', 'claude'])
def test_bound_stdio_denies_raw_paths_bindings_and_crud_then_publishes(tmp_path, harness):
    pytest.importorskip('mcp')
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    _, store, caller, _, _, owner, human = environment(tmp_path)
    caller = {**caller, 'harness': harness}
    source_before = {p: (p.read_bytes(), p.stat().st_mtime_ns) for p in (owner, human)}
    start = cli(store, caller, 'start')
    rid, generation = start['run_id'], str(start['generation'])
    binding = ['--run-id', rid, '--generation', generation]
    async def sequence():
        advisory = StdioServerParameters(command=sys.executable, args=args_for(store, caller, 'serve', *binding), env=ENV)
        async with stdio_client(advisory) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                tools = (await session.list_tools()).tools
                names = {t.name for t in tools}
                assert names == {'run_observe', 'source_read', 'memory_read', 'draft_read', 'overview_read',
                                 'draft_submit', 'coverage_mark', 'issue_suggest'}
                assert all(t.annotations.readOnlyHint == (t.name in {'run_observe','source_read','memory_read','draft_read','overview_read'}) for t in tools)
                before_policy = (store.root / 'dreaming/policy.json').read_bytes()
                negatives = [('create', {}), ('capture', {}), ('curate', {}), ('update', {}), ('delete', {}),
                             ('run_shell', {'command': 'unavailable'}), ('configure', {}), ('takeover', {}),
                             ('draft_publish', {'revision': '0' * 64}),
                             ('source_read', {'source_id': '/etc/passwd'}),
                             ('source_read', {'source_id': 'owner', 'cwd': str(tmp_path)}),
                             ('run_observe', {'profile': 'other', 'enable_publisher': True})]
                for name, arguments in negatives:
                    result = await session.call_tool(name, arguments)
                    assert result.isError, (name, result)
                assert store._load('demo') == []
                assert (store.root / 'dreaming/policy.json').read_bytes() == before_policy
                material = payload(await session.call_tool('source_read', {'source_id': 'owner'}))
                key = material['sources']['owner']['events'][0]['key']
                frozen = payload(await session.call_tool('draft_submit', {'operations': [record_op('A', claim(key)), view_op('V', claim('op:A'))]}))
                assert payload(await session.call_tool('draft_read', {'revision': frozen['draft_revision']}))['operations']
        publisher = StdioServerParameters(command=sys.executable, args=args_for(store, caller, 'serve', *binding, '--enable-publisher'), env=ENV)
        async with stdio_client(publisher) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                tools = (await session.list_tools()).tools
                assert 'draft_publish' in {t.name for t in tools}
                result = payload(await session.call_tool('draft_publish', {'revision': frozen['draft_revision']}))
                assert result['status'] == 'applied'
                assert payload(await session.call_tool('overview_read', {'view': 'research', 'scenario': 'research'}))['status'] == 'valid'
                memory = payload(await session.call_tool('memory_read', {'query': 'fixture'}))
                assert len(memory['items']) == 1
        return frozen
    frozen = asyncio.run(sequence())
    assert len(store._load('demo')) == 1
    for path, (raw, mtime) in source_before.items():
        assert path.read_bytes() == raw and path.stat().st_mtime_ns == mtime
    next_caller = {**caller, 'session_id': caller['session_id'] + '-continued'}
    takeover = cli(store, next_caller, 'takeover', *binding)
    assert takeover['generation'] == 2
    result = cli(store, next_caller, 'publish', '--run-id', rid, '--generation', '2', '--revision', frozen['draft_revision'])
    assert result['status'] == 'applied' and len(store._load('demo')) == 1
    assert store._load('demo')[0]['provenance']['session_id'] == caller['session_id']


@pytest.mark.parametrize('harness', ['codex', 'claude'])
def test_opt_in_hook_consumes_only_actual_project_and_respects_revocation(tmp_path, harness):
    engine, store, caller, owner_caller, _, _, _ = environment(tmp_path)
    rid, gen, _, key = begin(engine)
    c = claim(key, level='explicit', text='SYNTHETIC_SCOPED_PREFERENCE')
    op = {'id': 'P', 'action': 'collaboration_create', 'claim': c, 'review': review([key]), 'visibility': 'active'}
    vc = deepcopy(c); vc['refs'] = ['op:P']
    _, result = freeze_publish(engine, rid, gen, [op, view_op('CV', vc, kind='collaboration')])
    assert result['status'] == 'applied'
    event = {'hook_event_name': 'SessionStart', 'source': 'startup', 'cwd': owner_caller['cwd'], 'session_id': 'synthetic-consumer'}
    def text(output):
        return output['hookSpecificOutput']['additionalContext']
    assert 'SYNTHETIC_' not in text(handle_hook(store, harness, event))
    rendered = text(handle_hook(store, harness, event, dream_profile='fixture', dream_scenario='research'))
    assert 'SYNTHETIC_SCOPED_PREFERENCE' in rendered and len(rendered) <= 6000
    wrong = {**event, 'cwd': caller['cwd']}
    assert 'SYNTHETIC_' not in text(handle_hook(store, harness, wrong, dream_profile='fixture', dream_scenario='research'))
    add_disposition(store, caller, target='demo', topic='*', scope='collaboration', source_keys=[key], kind='no_reuse', reason='Synthetic revocation')
    assert 'SYNTHETIC_' not in text(handle_hook(store, harness, event, dream_profile='fixture', dream_scenario='research'))


def test_cli_partial_is_nonzero_and_default_manifest_stays_separate(tmp_path):
    engine, store, caller, *_ = environment(tmp_path)
    run = cli(store, caller, 'start'); rid, gen = run['run_id'], str(run['generation'])
    key = cli(store, caller, 'materials', '--run-id', rid, '--source-id', 'owner')['sources']['owner']['events'][0]['key']
    risky = claim(key); risky['risks'] = ['execution-authority']
    frozen = cli(store, caller, 'freeze', '--run-id', rid, '--generation', gen, data=[record_op('A', claim(key)), record_op('B', risky)])
    result = cli(store, caller, 'publish', '--run-id', rid, '--generation', gen, '--revision', frozen['draft_revision'], expected=3)
    assert result['status'] == 'partial' and len(store._load('demo')) == 1
    from shared_memory_mcp.server import make_server
    assert {t.name for t in asyncio.run(make_server(store).list_tools())} == {'context','search','read','create','approve','update','delete','capture','curate'}
