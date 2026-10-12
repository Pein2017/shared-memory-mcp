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


def test_cli_takeover_and_publish_keep_the_original_effect_executor(tmp_path):
    _, store, caller, *_ = environment(tmp_path)
    start = cli(store, caller, 'start')
    rid, generation = start['run_id'], str(start['generation'])
    key = cli(store, caller, 'materials', '--run-id', rid, '--source-id', 'owner')['sources']['owner']['events'][0]['key']
    frozen = cli(store, caller, 'freeze', '--run-id', rid, '--generation', generation,
                 data=[record_op('A', claim(key)), view_op('V', claim('op:A'))])
    next_caller = {**caller, 'session_id': caller['session_id'] + '-continued'}
    assert cli(store, next_caller, 'takeover', '--run-id', rid, '--generation', generation)['generation'] == 2
    result = cli(store, next_caller, 'publish', '--run-id', rid, '--generation', '2', '--revision', frozen['draft_revision'])
    assert result['status'] == 'applied' and len(store._load('demo')) == 1
    assert store._load('demo')[0]['provenance']['session_id'] == next_caller['session_id']


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
    rendered = text(handle_hook(store, harness, event))
    assert 'SYNTHETIC_SCOPED_PREFERENCE' in rendered and len(rendered) <= 6000
    wrong = {**event, 'cwd': caller['cwd']}
    assert 'SYNTHETIC_' not in text(handle_hook(store, harness, wrong))
    add_disposition(store, caller, target='demo', topic='*', scope='collaboration', source_keys=[key], kind='no_reuse', reason='Synthetic revocation')
    assert 'SYNTHETIC_' not in text(handle_hook(store, harness, event))


def test_cli_partial_is_nonzero_and_default_manifest_stays_separate(tmp_path):
    engine, store, caller, *_ = environment(tmp_path)
    run = cli(store, caller, 'start'); rid, gen = run['run_id'], str(run['generation'])
    key = cli(store, caller, 'materials', '--run-id', rid, '--source-id', 'owner')['sources']['owner']['events'][0]['key']
    risky = claim(key); risky['risks'] = ['execution-authority']
    frozen = cli(store, caller, 'freeze', '--run-id', rid, '--generation', gen, data=[record_op('A', claim(key)), record_op('B', risky)])
    result = cli(store, caller, 'publish', '--run-id', rid, '--generation', gen, '--revision', frozen['draft_revision'], expected=3)
    assert result['status'] == 'partial' and len(store._load('demo')) == 1
    from shared_memory_mcp.server import make_server
    advertised = asyncio.run(make_server(store).list_tools())
    names = {t.name for t in advertised}
    from shared_memory_mcp.operations import PUBLIC
    assert tuple(t.name for t in advertised) == PUBLIC
    assert len(names) == len(advertised)
