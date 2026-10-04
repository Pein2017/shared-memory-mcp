import importlib.util
import json
import sys
from pathlib import Path

import pytest

path = Path(__file__).resolve().parents[1] / "scripts" / "install-local.py"
spec = importlib.util.spec_from_file_location("install_local", path)
installer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(installer)


def test_install_preserves_other_owners_and_is_idempotent():
    original = {"theme": "dark", "hooks": {"PreToolUse": [{"hooks": [{"command": "other"}]}]},
                "mcpServers": {"other": {"command": "other"}}, "extensions": ["other.ts"]}
    first = installer.add_hook(original, "/own/cli hook")
    first = installer.add_server(first, "/own/cli", ["serve"])
    first = installer.add_extension(first, "/own/extension.ts")
    second = installer.add_hook(first, "/own/cli hook")
    second = installer.add_server(second, "/own/cli", ["serve"])
    second = installer.add_extension(second, "/own/extension.ts")
    assert first == second
    assert first["theme"] == original["theme"]
    assert first["hooks"]["PreToolUse"] == original["hooks"]["PreToolUse"]
    assert first["mcpServers"]["other"] == original["mcpServers"]["other"]
    assert original["extensions"] == ["other.ts"]
    assert first["extensions"] == ["other.ts", "/own/extension.ts"]
    assert len(first["hooks"]["SessionStart"]) == 1


def test_config_collisions_fail_without_changing_input():
    document = {"mcpServers": {"shared-memory": {"command": "someone-else"}}}
    with pytest.raises(ValueError):
        installer.add_server(document, "/own/cli", ["serve"])
    assert document == {"mcpServers": {"shared-memory": {"command": "someone-else"}}}
    duplicate = {"hooks": {"SessionStart": [{"hooks": [{"command": "own"}, {"command": "own"}]}]}}
    with pytest.raises(ValueError):
        installer.add_hook(duplicate, "own")


def test_only_owned_native_hook_can_be_selected_for_trust():
    owned = {"command": "own", "sourcePath": "/fixture/hooks.json", "eventName": "sessionStart",
             "currentHash": "sha256:test", "key": "owned"}
    other = {**owned, "command": "other", "key": "other"}
    response = {"data": [{"hooks": [other, owned]}]}
    assert installer.select_owned_hook(response, Path("/fixture/hooks.json"), "own")["key"] == "owned"
    with pytest.raises(ValueError):
        installer.select_owned_hook(response, Path("/other/hooks.json"), "own")
    with pytest.raises(ValueError):
        installer.select_owned_hook({"data": [{"hooks": [owned, owned]}]}, Path("/fixture/hooks.json"), "own")


def test_atomic_configuration_write_and_repeated_write(tmp_path):
    path = tmp_path / "settings.json"
    installer.atomic_text(path, '{"unrelated": true}\n')
    before = path.stat().st_mtime_ns
    installer.atomic_text(path, '{"unrelated": true}\n')
    assert path.stat().st_mtime_ns == before
    assert path.read_text() == '{"unrelated": true}\n'
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("entry", [
    {"type": "stdio", "command": "other", "args": ["serve"]},
    {"type": "http", "command": "/own/cli", "args": ["serve"]},
    {"type": "stdio", "command": "/own/cli", "args": ["serve"], "env": {"TOKEN": "other"}},
    {"type": "stdio", "command": "/own/cli", "args": ["serve"], "exposure": "direct"},
    None,
])
def test_claude_server_collision_rejects_nonidentical_descriptor(entry):
    document = {"account": {"preserve": True}, "mcpServers": {"shared-memory": entry}}
    before = json.dumps(document)
    with pytest.raises(ValueError):
        installer.claude_server_present(document, "/own/cli", ["serve"])
    assert json.dumps(document) == before


def test_claude_server_identity_is_exact():
    expected = {"type": "stdio", "command": "/own/cli", "args": ["serve"]}
    assert installer.claude_server_present({"mcpServers": {"shared-memory": expected}}, "/own/cli", ["serve"])
    assert not installer.claude_server_present({"account": True}, "/own/cli", ["serve"])


def install_fixture(tmp_path, monkeypatch, claude=True):
    root, home, pi, project = [tmp_path / name for name in ("store", "codex", "pi", "project")]
    for directory in (root, home, pi, project):
        directory.mkdir()
    (root / "registry.json").write_text("{}")
    cli = tmp_path / "shared-memory"
    cli.write_text("#!/bin/sh\nexit 0\n")
    cli.chmod(0o700)
    arguments = ["--root", str(root), "serve"]
    (home / "config.toml").write_text('model = "preserved"\n[mcp_servers.shared-memory]\ncommand = '
        + json.dumps(str(cli)) + '\nargs = ' + json.dumps(arguments) + '\n')
    (pi / "mcp.json").write_text('{"mcpServers":{"other":{"command":"other"}}}')
    (pi / "settings.json").write_text('{"extensions":["other.ts"],"model":"preserved"}')
    claude_dir = tmp_path / "claude"
    if claude:
        claude_dir.mkdir()
        (claude_dir / "settings.json").write_text(json.dumps({"model": "preserved", "autoMemoryEnabled": True,
            "hooks": {"SessionStart": [{"matcher": "startup", "hooks": [{"type": "command", "command": "other"}]}]}}))
        (claude_dir / ".claude.json").write_text(json.dumps({"account": {"preserve": True},
            "mcpServers": {"other": {"type": "http", "url": "https://example.invalid"}}}))
    calls = []
    def native_register(command, **kwargs):
        assert command[:5] == ["claude", "mcp", "add-json", "--scope", "user"]
        assert command[5] == "shared-memory"
        assert kwargs["env"]["CLAUDE_CONFIG_DIR"] == str(claude_dir)
        descriptor = json.loads(command[6])
        assert descriptor == {"type": "stdio", "command": str(cli), "args": arguments}
        document = json.loads((claude_dir / ".claude.json").read_text())
        document["mcpServers"]["shared-memory"] = descriptor
        (claude_dir / ".claude.json").write_text(json.dumps(document))
        calls.append(command)
    monkeypatch.setattr(installer.subprocess, "run", native_register)
    monkeypatch.setattr(installer, "trust_codex_hook", lambda *args: {"trustStatus": "trusted", "enabled": True})
    argv = ["install-local", "--root", str(root), "--cli", str(cli), "--codex-home", str(home),
            "--pi-dir", str(pi), "--cwd", str(project)]
    if claude:
        argv += ["--claude-dir", str(claude_dir)]
    monkeypatch.setattr(sys, "argv", argv)
    return root, home, pi, claude_dir, argv, calls


def test_optional_claude_install_preserves_and_backs_up_native_configuration(tmp_path, monkeypatch, capsys):
    root, home, pi, claude_dir, argv, calls = install_fixture(tmp_path, monkeypatch)
    originals = {path: path.read_bytes() for path in (claude_dir / "settings.json", claude_dir / ".claude.json")}
    assert installer.main() == 0
    plan = json.loads(capsys.readouterr().out)
    assert plan["claude_dir"] == str(claude_dir)
    assert plan["claude_mcp"]["registration"] == "add"
    assert not calls
    assert all(path.read_bytes() == payload for path, payload in originals.items())
    argv.append("--apply")
    assert installer.main() == 0
    first = json.loads(capsys.readouterr().out)
    manifest = json.loads((Path(first["backup"]) / "manifest.json").read_text())
    for path, payload in originals.items():
        row = next(row for row in manifest if row["path"] == str(path))
        assert Path(row["backup"]).read_bytes() == payload
        assert Path(row["backup"]).stat().st_mode & 0o777 == 0o600
    settings = json.loads((claude_dir / "settings.json").read_text())
    assert settings["model"] == "preserved" and settings["autoMemoryEnabled"] is True
    assert settings["hooks"]["SessionStart"][0]["hooks"][0]["command"] == "other"
    assert settings["hooks"]["SessionStart"][1]["matcher"] == "startup|resume|clear|compact"
    assert "--harness claude" in settings["hooks"]["SessionStart"][1]["hooks"][0]["command"]
    account = json.loads((claude_dir / ".claude.json").read_text())
    assert account["account"] == {"preserve": True} and "other" in account["mcpServers"]
    assert not (claude_dir / "skills").exists()
    first_bytes = {path: path.read_bytes() for path in originals}
    assert installer.main() == 0
    second = json.loads(capsys.readouterr().out)
    assert second["claude_mcp"]["registration"] == "identical"
    assert len(calls) == 1
    assert all(path.read_bytes() == payload for path, payload in first_bytes.items())


def test_omitted_claude_keeps_original_codex_pi_install(tmp_path, monkeypatch, capsys):
    root, home, pi, claude_dir, argv, calls = install_fixture(tmp_path, monkeypatch, claude=False)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_dir))
    argv.append("--apply")
    assert installer.main() == 0
    installed = json.loads(capsys.readouterr().out)
    assert "claude_dir" not in installed and not claude_dir.exists() and not calls
    assert len(installed["config_files"]) == 4
    assert json.loads((pi / "mcp.json").read_text())["mcpServers"]["shared-memory"]["exposure"] == "direct"
    assert json.loads((pi / "settings.json").read_text())["extensions"][0] == "other.ts"
    assert (home / "skills" / "shared-memory").is_symlink()


def test_claude_collision_fails_before_any_write(tmp_path, monkeypatch):
    root, home, pi, claude_dir, argv, calls = install_fixture(tmp_path, monkeypatch)
    (claude_dir / ".claude.json").write_text('{"mcpServers":{"shared-memory":{"type":"http","url":"other"}}}')
    before = {path: path.read_bytes() for path in (home / "config.toml", pi / "mcp.json", pi / "settings.json",
                                                claude_dir / "settings.json", claude_dir / ".claude.json")}
    argv.append("--apply")
    with pytest.raises(ValueError):
        installer.main()
    assert not calls and not (root / ".state").exists()
    assert all(path.read_bytes() == payload for path, payload in before.items())
