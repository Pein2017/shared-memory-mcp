"""Review-only owned legacy Dreaming cutover. No live service or user settings."""
import importlib.util
import json
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1]/'scripts/install-local.py'
spec = importlib.util.spec_from_file_location('shared_memory_install_cutover', SOURCE)
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


def fixture(tmp_path):
    root = tmp_path/'memory'
    root.mkdir()
    cli = str(tmp_path/'shared-memory')
    args = ['--root',str(root),'dream','gateway','--profile','fixture','--enable-publisher']
    owned = {'command':cli,'args':args}
    return root, cli, owned, {'fixture':{'actions':['view_publish']}}


@pytest.mark.parametrize('exposure', ['codemode', 'deferred', 'direct', 'hidden'])
def test_precise_config_removes_only_owned_second_registration(tmp_path, exposure):
    root, cli, owned, profiles = fixture(tmp_path)
    document = {'nativeMemoriesEnabled': True, 'mcpServers': {
        'shared-memory': {'command':cli,'args':['--root',str(root),'serve']},
        'shared-memory-dreaming':{**owned,'type':'stdio','exposure':exposure},
        'unrelated':{'url':'https://other.example.invalid'}}}
    preview = installer.plan_owned_legacy(document,'mcpServers',cli,root,profiles)
    assert preview['owned'] and preview['provider'] == 'shared-memory-dreaming'
    result = installer.cutover_owned_legacy_json(document,'mcpServers',cli,root,profiles)
    assert set(result['mcpServers']) == {'shared-memory','unrelated'}
    assert result['nativeMemoriesEnabled']
    assert document['mcpServers']['shared-memory-dreaming'] == {**owned,'type':'stdio','exposure':exposure}
    assert installer.cutover_owned_legacy_json(result,'mcpServers',cli,root,profiles) == result


@pytest.mark.parametrize('poison', [
    {'command':'/other/program'},
    {'args':['--root','/other/memory','dream','gateway','--profile','fixture','--enable-publisher']},
    {'args':['--root','/fixture','serve']},
    {'args':['--root','/fixture','dream','gateway','--profile','foreign','--enable-publisher']},
    {'env':{'SECRET':'do-not-remove-unrecognized-owner'}},
    {'exposure':'unknown'},
    {'exposure':None},
    {'exposure':[]},
])
def test_collision_and_unknown_profile_fail_before_cutover(tmp_path, poison):
    root, cli, owned, profiles = fixture(tmp_path)
    poison = {**poison}
    if 'args' in poison:
        poison['args'] = [str(root) if x=='/fixture' else x for x in poison['args']]
    original = {'mcpServers':{'shared-memory-dreaming':{**owned,**poison},
                              'foreign':{'command':'other'}}}
    before = json.dumps(original)
    with pytest.raises(ValueError):
        installer.cutover_owned_legacy_json(original,'mcpServers',cli,root,profiles)
    assert json.dumps(original) == before


def test_codex_and_claude_shapes_are_not_arbitrary_removals(tmp_path):
    root, cli, owned, profiles = fixture(tmp_path)
    codex={'mcp_servers':{'shared-memory-dreaming':{**owned,'startup_timeout_sec':15},
                          'foreign':{'command':'node'}}}
    assert installer.plan_owned_legacy(codex,'mcp_servers',cli,root,profiles)['owned']
    claude={'mcpServers':{'shared-memory-dreaming':{**owned,'type':'stdio'}}}
    assert installer.plan_owned_legacy(claude,'mcpServers',cli,root,profiles)['owned']
    assert not installer.plan_owned_legacy({'mcpServers':{}},'mcpServers',cli,root,profiles)['owned']
    codex['mcp_servers']['shared-memory-dreaming']['exposure'] = 'deferred'
    with pytest.raises(ValueError):
        installer.plan_owned_legacy(codex,'mcp_servers',cli,root,profiles)

def test_installer_preview_plans_owned_cutover_without_mutating_fixture(tmp_path, monkeypatch, capsys):
    home, pi, project = (tmp_path/p for p in ('codex-home', 'pi-agent', 'task-project'))
    for directory in (home, pi, project):
        directory.mkdir()
    root = tmp_path/'memory'
    (root/'dreaming').mkdir(parents=True)
    (root/'registry.json').write_text('{"version":1,"projects":[]}')
    (root/'dreaming/policy.json').write_text(json.dumps({'profiles': {'fixture': {}}}))
    cli = tmp_path/'shared-memory'
    cli.write_text('#!/bin/sh\nexit 0\n')
    cli.chmod(0o700)
    legacy_args = ['--root', str(root), 'dream', 'gateway', '--profile', 'fixture', '--enable-publisher']
    (home/'config.toml').write_text('[mcp_servers.shared-memory-dreaming]\ncommand = ' + json.dumps(str(cli)) +
        '\nargs = ' + json.dumps(legacy_args) + '\n[mcp_servers.unrelated]\ncommand = "other"\n')
    (pi/'mcp.json').write_text(json.dumps({'mcpServers': {
        'shared-memory-dreaming': {'command':str(cli),'args':legacy_args,'type':'stdio','exposure':'deferred'},
        'unrelated': {'command':'other'}}}))
    before = [(path, path.read_bytes()) for path in (home/'config.toml', pi/'mcp.json')]
    monkeypatch.setattr('sys.argv', ['install-local.py', '--root', str(root), '--cli', str(cli),
        '--codex-home', str(home), '--pi-dir', str(pi), '--cwd', str(project)])
    assert installer.main() == 0
    preview = json.loads(capsys.readouterr().out)
    assert preview['status'] == 'plan'
    assert preview['owned_legacy']['codex']['owned'] is True
    assert preview['owned_legacy']['pi']['owned'] is True
    assert all(path.read_bytes() == content for path, content in before)
    assert not (root/'.state').exists()

def apply_fixture(tmp_path, monkeypatch):
    import subprocess
    root, home, pi, claude, project = (tmp_path / p for p in
        ('memory', 'codex-home', 'pi', 'claude', 'project'))
    for directory in (root, home, pi, claude, project):
        directory.mkdir()
    (root/'registry.json').write_text('{"version":1,"projects":[]}')
    (root/'dreaming').mkdir()
    (root/'dreaming/policy.json').write_text(json.dumps({'profiles': {'fixture': {}}}))
    cli = tmp_path/'shared-memory'
    cli.write_text('#!/bin/sh\nexit 0\n')
    cli.chmod(0o700)
    old_args = ['--root', str(root), 'dream', 'gateway', '--profile', 'fixture', '--enable-publisher']
    common_args = ['--root', str(root), 'serve']
    (home/'config.toml').write_text(
        '[mcp_servers.shared-memory-dreaming]\ncommand = ' + json.dumps(str(cli)) +
        '\nargs = ' + json.dumps(old_args) +
        '\n[mcp_servers.shared-memory]\ncommand = ' + json.dumps(str(cli)) +
        '\nargs = ' + json.dumps(common_args) +
        '\n[mcp_servers.unrelated]\ncommand = "other"\n')
    (pi/'mcp.json').write_text(json.dumps({'nativeMemoriesEnabled':True, 'mcpServers':{
        'shared-memory-dreaming':{'command':str(cli),'args':old_args,'type':'stdio','exposure':'deferred'},
        'unrelated':{'command':'other'}}}))
    (claude/'.claude.json').write_text(json.dumps({'nativeMemoriesEnabled':True,'mcpServers':{
        'shared-memory-dreaming':{'command':str(cli),'args':old_args,'type':'stdio'},
        'shared-memory':{'command':str(cli),'args':common_args,'type':'stdio'},
        'unrelated':{'command':'other'}}}))
    (claude/'settings.json').write_text(json.dumps({'nativeMemoriesEnabled':True}))
    monkeypatch.setattr(installer, 'trust_codex_hook', lambda *args: {'enabled':True,'trustStatus':'trusted'})
    calls = []
    def controlled_process(argv, **kwargs):
        calls.append(argv)
        assert argv[-1] == 'shared-memory-dreaming'
        if argv[0] == 'codex':
            path = home/'config.toml'
            text = path.read_text()
            block = ('[mcp_servers.shared-memory-dreaming]\ncommand = ' + json.dumps(str(cli)) +
                     '\nargs = ' + json.dumps(old_args) + '\n')
            assert block in text
            path.write_text(text.replace(block,''))
        elif argv[0] == 'claude':
            path = claude/'.claude.json'
            value = json.loads(path.read_text())
            del value['mcpServers']['shared-memory-dreaming']
            path.write_text(json.dumps(value))
        else:
            raise AssertionError('Unexpected external subprocess')
        return subprocess.CompletedProcess(argv, 0)
    monkeypatch.setattr(installer.subprocess, 'run', controlled_process)
    monkeypatch.setattr('sys.argv', ['install-local.py', '--root',str(root),'--cli',str(cli),
        '--codex-home',str(home),'--pi-dir',str(pi),'--claude-dir',str(claude),
        '--cwd',str(project),'--apply'])
    return root, home, pi, claude, calls


def test_disposable_apply_cuts_only_owned_legacy_and_keeps_native_settings(tmp_path, monkeypatch):
    root, home, pi, claude, calls = apply_fixture(tmp_path, monkeypatch)
    assert installer.main() == 0
    assert calls == [
        ['codex', 'mcp', 'remove', 'shared-memory-dreaming'],
        ['claude', 'mcp', 'remove', '--scope', 'user', 'shared-memory-dreaming']]
    import tomllib
    conf = tomllib.loads((home/'config.toml').read_text())['mcp_servers']
    assert set(conf) == {'shared-memory', 'unrelated'}
    for file in (pi/'mcp.json', claude/'.claude.json'):
        document = json.loads(file.read_text())
        assert set(document['mcpServers']) == {'shared-memory', 'unrelated'}
        assert document['nativeMemoriesEnabled'] is True
    assert json.loads((claude/'settings.json').read_text())['nativeMemoriesEnabled'] is True
    assert list((root/'.state/config-backups').glob('*/manifest.json'))


@pytest.mark.parametrize('harness', ['codex', 'pi'])
def test_disabled_common_provider_rejects_cutover_before_writes(tmp_path, monkeypatch, harness):
    root, home, pi, claude, calls = apply_fixture(tmp_path, monkeypatch)
    if harness == 'codex':
        path = home/'config.toml'
        path.write_text(path.read_text().replace('[mcp_servers.unrelated]',
            'enabled = false\n[mcp_servers.unrelated]'))
    else:
        path = pi/'mcp.json'
        document = json.loads(path.read_text())
        document['mcpServers']['shared-memory'] = {
            'command':str(tmp_path/'shared-memory'), 'args':['--root',str(root),'serve'],
            'enabled':False, 'exposure':'direct'}
        path.write_text(json.dumps(document))
    paths = [home/'config.toml', pi/'mcp.json', claude/'.claude.json', claude/'settings.json']
    before = {path:path.read_bytes() for path in paths}
    with pytest.raises(ValueError, match='active'):
        installer.main()
    assert not calls and not (root/'.state').exists()
    assert all(path.read_bytes() == payload for path, payload in before.items())


@pytest.mark.parametrize('change', ['disabled', 'command'])
def test_changed_common_provider_stops_before_native_legacy_removal(tmp_path, monkeypatch, change):
    root, home, pi, claude, calls = apply_fixture(tmp_path, monkeypatch)
    def change_during_hook_discovery(*args):
        path = home/'config.toml'
        text = path.read_text()
        if change == 'disabled':
            text = text.replace('[mcp_servers.unrelated]', 'enabled = false\n[mcp_servers.unrelated]')
        else:
            marker = '[mcp_servers.shared-memory]\ncommand = ' + json.dumps(str(tmp_path/'shared-memory'))
            text = text.replace(marker, '[mcp_servers.shared-memory]\ncommand = "other"')
        path.write_text(text)
        return {'enabled':True,'trustStatus':'trusted'}
    monkeypatch.setattr(installer, 'trust_codex_hook', change_during_hook_discovery)
    with pytest.raises(ValueError, match='active'):
        installer.main()
    assert not calls
    import tomllib
    assert 'shared-memory-dreaming' in tomllib.loads((home/'config.toml').read_text())['mcp_servers']


def test_changed_claude_common_provider_keeps_its_legacy_registration(tmp_path, monkeypatch):
    root, home, pi, claude, calls = apply_fixture(tmp_path, monkeypatch)
    native_remove = installer.subprocess.run
    def change_after_codex_removal(argv, **kwargs):
        result = native_remove(argv, **kwargs)
        path = claude/'.claude.json'
        document = json.loads(path.read_text())
        del document['mcpServers']['shared-memory']
        path.write_text(json.dumps(document))
        return result
    monkeypatch.setattr(installer.subprocess, 'run', change_after_codex_removal)
    with pytest.raises(ValueError, match='active'):
        installer.main()
    assert calls == [['codex', 'mcp', 'remove', 'shared-memory-dreaming']]
    assert 'shared-memory-dreaming' in json.loads((claude/'.claude.json').read_text())['mcpServers']
