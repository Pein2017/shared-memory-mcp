import importlib.util
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
