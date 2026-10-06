"""Read-only discovery and actual CLI/native hook onboarding consumers."""
import io
import json
import shlex
import subprocess
import sys

import pytest

from shared_memory_mcp.adapters import hook_main
from shared_memory_mcp.core import MemoryError, MemoryStore


def git(path, *args):
    result = subprocess.run(['git', '-C', str(path), *args], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def repo(path):
    path.mkdir(parents=True)
    git(path, 'init', '--quiet')
    git(path, '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.test',
        'commit', '--quiet', '--allow-empty', '-m', 'fixture')
    return path


def snapshot(store):
    return {str(p.relative_to(store.root)): p.read_bytes() for p in store.root.rglob('*')
            if p.is_file() and '.writer-gate.sqlite3' not in p.name}


@pytest.fixture
def env(tmp_path):
    parent = repo(tmp_path / 'parent')
    store = MemoryStore(tmp_path / 'memory')
    store.init()
    store.register('parent', [parent])
    return store, parent


def caller(path, **kwargs):
    return {'cwd': str(path), 'harness': 'codex', 'session_id': 'fixture', 'actor': 'codex', **kwargs}


def test_nested_discovery_cli_and_register_retry_are_independent(env, tmp_path):
    store, parent = env
    child = repo(parent / 'nested repo; $(false)')
    before = snapshot(store)
    cli = subprocess.run([sys.executable, '-m', 'shared_memory_mcp.cli', '--root', str(store.root),
                          'project', '--cwd', str(child)], capture_output=True, text=True)
    assert cli.returncode == 2, cli.stderr
    result = json.loads(cli.stdout)
    assert result['git_root'] == str(child)
    assert result['git_common_dir'] == git(child, 'rev-parse', '--path-format=absolute', '--git-common-dir')
    assert result['status'] == 'unmapped'
    hint = result['registration']
    assert shlex.split(hint['command']) == hint['argv']
    assert hint['argv'][-1] == str(child)
    assert snapshot(store) == before
    contextual = store.context(caller(child))
    assert contextual['items'] == [] and contextual['text'] == '' and contextual['scope'] is None
    assert contextual['diagnostic']['project']['registration'] == hint
    with pytest.raises(MemoryError) as error:
        store.search(caller(child), 'parent secret')
    assert hint['command'] in str(error.value)
    # Exercise the exact existing registration arguments through the real CLI.
    registered = subprocess.run([sys.executable, '-m', 'shared_memory_mcp.cli', *hint['argv'][1:]],
                                capture_output=True, text=True)
    assert registered.returncode == 0, registered.stderr
    assert store.resolve(caller(child))['project_id'] == result['suggested_project_id']
    assert store.resolve(caller(parent))['project_id'] == 'parent'
    assert store.search(caller(child), '')['items'] == []
    assert not (store.root / 'sharing.json').exists()


def test_linked_worktree_reuses_registered_common_identity(env, tmp_path):
    store, parent = env
    linked = tmp_path / 'linked'
    git(parent, 'worktree', 'add', '--quiet', '-b', 'fixture-linked', str(linked))
    before = snapshot(store)
    result = store.project(str(linked))
    assert result['status'] == 'ok' and result['project_id'] == 'parent'
    assert result['registration'] is None
    assert snapshot(store) == before


def test_linked_worktree_under_other_registered_root_uses_own_git_identity(env):
    store, parent = env
    independent = repo(parent / 'tool-repo')
    store.register('tools', [independent])
    linked = parent / '.worktrees' / 'tools'
    git(independent, 'worktree', 'add', '--quiet', '-b', 'linked-tools', str(linked))
    before = snapshot(store)
    actual = caller(linked, project_id='tools')
    assert store.context(actual)['status'] == 'ok'
    assert store.resolve(actual)['project_id'] == 'tools'
    project = store.project(str(linked), project_id='tools')
    assert project['status'] == 'ok' and project['project_id'] == 'tools'
    assert project['registration'] is None
    mismatch = store.context(caller(linked, project_id='parent'))
    assert mismatch['status'] == 'invalid' and mismatch['items'] == []
    assert mismatch['diagnostic']['code'] == 'scope_hint_mismatch'
    assert snapshot(store) == before


def test_name_collision_gets_separate_identity(env, tmp_path):
    store, parent = env
    other = repo(tmp_path / 'independent' / 'parent')
    result = store.project(str(other))
    assert result['suggested_project_id'] != 'parent'
    assert result['suggested_project_id'].startswith('parent-')
    argv = result['registration']['argv']
    store.register(argv[argv.index('--project-id') + 1], [argv[-1]])
    assert store.resolve(caller(other))['project_id'] != store.resolve(caller(parent))['project_id']


def test_restricted_subtree_is_never_broadened(tmp_path):
    project = repo(tmp_path / 'restricted')
    allowed, sibling = project / 'allowed', project / 'sibling'
    allowed.mkdir()
    sibling.mkdir()
    store = MemoryStore(tmp_path / 'memory')
    store.init()
    store.register('restricted', [allowed])
    before = snapshot(store)
    assert store.project(str(allowed))['project_id'] == 'restricted'
    for path in (sibling, project):
        result = store.project(str(path))
        assert result['status'] == 'unmapped'
        assert result['diagnostic']['code'] == 'restricted_scope'
        assert result['registration'] is None and result['suggested_project_id'] is None
    assert snapshot(store) == before


def test_scope_hint_mismatch_does_not_offer_registration(env):
    store, parent = env
    result = store.project(str(parent), project_id='wrong')
    assert result['status'] == 'invalid'
    assert result['diagnostic']['code'] == 'scope_hint_mismatch'
    assert result['registration'] is None


def test_corrupt_registry_discovery_fails_closed(env):
    store, parent = env
    (store.root / 'registry.json').write_text('{')
    with pytest.raises(MemoryError) as error:
        store.project(str(parent))
    assert error.value.code == 'corrupt_registry'


@pytest.mark.parametrize('harness', ['codex', 'claude'])
def test_native_hook_delivers_actionable_diagnostic_without_foreign_memory(env, harness):
    store, parent = env
    child = repo(parent / 'independent')
    event = {'cwd': str(child), 'session_id': 'fixture-session', 'hook_event_name': 'SessionStart',
             'source': 'startup', 'credential': 'DO-NOT-ECHO', 'transcript_path': '/private/raw'}
    before = snapshot(store)
    output, errors = io.StringIO(), io.StringIO()
    assert hook_main(store, harness, stdin=io.StringIO(json.dumps(event)), stdout=output, stderr=errors) == 0
    text = json.loads(output.getvalue())['hookSpecificOutput']['additionalContext']
    assert text.startswith('Shared-memory onboarding diagnostic:')
    assert store.project(str(child))['registration']['command'] in text
    assert '<shared-memory-context>' not in text
    assert 'DO-NOT-ECHO' not in text + errors.getvalue() and '/private/raw' not in text + errors.getvalue()
    assert len(text) <= 6000
    assert snapshot(store) == before
