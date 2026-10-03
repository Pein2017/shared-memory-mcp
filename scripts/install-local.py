#!/usr/bin/env python3
"""Install owned local adapters; default to a reviewable plan."""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import selectors
import shlex
import subprocess
import time
import tomllib
import uuid

NAME = "shared-memory"


def load_json(path: Path) -> dict:
    value = json.loads(path.read_text()) if path.exists() else {}
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text() == text:
        return
    temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        with temporary.open("x", encoding="utf-8") as stream:
            os.chmod(temporary, 0o600)
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def add_hook(document: dict, command: str) -> dict:
    result = copy.deepcopy(document)
    groups = result.setdefault("hooks", {}).setdefault("SessionStart", [])
    owned = [
        (group, handler)
        for group in groups
        for handler in group.get("hooks", [])
        if handler.get("command") == command
    ]
    if owned:
        if len(owned) != 1:
            raise ValueError("Duplicate shared-memory hook; reconcile before installation")
        group, handler = owned[0]
        if group.get("matcher") != "startup|resume|clear|compact" or handler.get("type") != "command":
            raise ValueError("Existing shared-memory hook has a conflicting contract")
        return result
    groups.append({
        "matcher": "startup|resume|clear|compact",
        "hooks": [{"type": "command", "command": command, "timeout": 15}],
    })
    return result


def add_server(document: dict, command: str, arguments: list[str]) -> dict:
    result = copy.deepcopy(document)
    servers = result.setdefault("mcpServers", {})
    existing = servers.get(NAME)
    if existing is not None:
        if existing.get("command") != command or existing.get("args", []) != arguments:
            raise ValueError("Existing shared-memory MCP entry belongs to another configuration")
    else:
        servers[NAME] = {"command": command, "args": arguments, "exposure": "direct"}
    return result


def add_extension(document: dict, extension: str) -> dict:
    result = copy.deepcopy(document)
    entries = result.setdefault("extensions", [])
    if not isinstance(entries, list):
        raise ValueError("Pi extensions must be a list")
    if entries.count(extension) > 1:
        raise ValueError("Duplicate shared-memory Pi extension")
    if extension not in entries:
        entries.append(extension)
    return result


class CodexRPC:
    """Bounded requests to an owned native server, without a model turn."""

    def __init__(self, home: Path, stderr):
        environment = dict(os.environ, CODEX_HOME=str(home))
        self.process = subprocess.Popen(
            ["codex", "app-server", "--listen", "stdio://"],
            env=environment, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr,
        )
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.process.stdout, selectors.EVENT_READ)
        self.pending = b""
        self.sequence = 0

    def request(self, method: str, params: dict) -> dict:
        self.sequence += 1
        identifier = self.sequence
        self.process.stdin.write((json.dumps({"id": identifier, "method": method, "params": params}) + "\n").encode())
        self.process.stdin.flush()
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline:
            while b"\n" in self.pending:
                line, self.pending = self.pending.split(b"\n", 1)
                if not line:
                    continue
                message = json.loads(line)
                if message.get("id") == identifier:
                    if "error" in message:
                        raise RuntimeError(f"{method}: {message['error']}")
                    return message["result"]
            if not self.selector.select(max(0, deadline - time.monotonic())):
                break
            chunk = os.read(self.process.stdout.fileno(), 65536)
            if not chunk:
                break
            self.pending += chunk
        raise TimeoutError(f"Native Codex request timed out: {method}")

    def close(self) -> None:
        self.process.stdin.close()
        self.process.terminate()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        self.selector.close()


def select_owned_hook(response: dict, path: Path, command: str) -> dict:
    hooks = [
        hook for row in response.get("data", []) for hook in row.get("hooks", [])
        if hook.get("sourcePath") == str(path)
        and hook.get("command") == command and hook.get("eventName") == "sessionStart"
    ]
    if len(hooks) != 1 or not hooks[0].get("currentHash"):
        raise ValueError("Native Codex did not discover exactly one owned SessionStart hook")
    return hooks[0]


def trust_codex_hook(home: Path, cwd: Path, command: str, log: Path) -> dict:
    with log.open("w") as stream:
        os.chmod(log, 0o600)
        rpc = CodexRPC(home, stream)
        try:
            rpc.request("initialize", {
                "clientInfo": {"name": "shared-memory-installer", "version": "0.1.0"},
                "capabilities": {"experimentalApi": True},
            })
            hook = select_owned_hook(rpc.request("hooks/list", {"cwds": [str(cwd)]}), home / "hooks.json", command)
            if hook.get("trustStatus") != "trusted" or not hook.get("enabled"):
                rpc.request("config/batchWrite", {
                    "edits": [{
                        "keyPath": "hooks.state",
                        "value": {hook["key"]: {"trusted_hash": hook["currentHash"], "enabled": True}},
                        "mergeStrategy": "upsert",
                    }],
                    "filePath": None, "expectedVersion": None, "reloadUserConfig": True,
                })
            hook = select_owned_hook(rpc.request("hooks/list", {"cwds": [str(cwd)]}), home / "hooks.json", command)
            if hook.get("trustStatus") != "trusted" or not hook.get("enabled"):
                raise ValueError("Owned Codex hook did not become enabled and trusted")
            return {"key": hook["key"], "trustStatus": hook["trustStatus"], "enabled": hook["enabled"]}
        finally:
            rpc.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--cli", required=True, type=Path)
    parser.add_argument("--codex-home", type=Path, default=os.environ.get("CODEX_HOME"))
    parser.add_argument("--pi-dir", type=Path, default=os.environ.get("PI_CODING_AGENT_DIR"))
    parser.add_argument("--cwd", required=True, type=Path, help="Registered project for native hook discovery")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not all((args.codex_home, args.pi_dir)):
        parser.error("Supply Codex and Pi configuration roots explicitly or through their named environment variables")
    source = Path(__file__).resolve().parents[1]
    root, cli, home, pi, cwd = (p.resolve() for p in (
        args.root, args.cli, args.codex_home, args.pi_dir, args.cwd,
    ))
    if not cli.is_file() or not os.access(cli, os.X_OK):
        parser.error("--cli must be an installed executable")
    if not (root / "registry.json").is_file():
        parser.error("Initialize and register the central store before installing adapters")
    skill_source = source / "skills" / NAME
    skill_link = home / "skills" / NAME
    if not (skill_source / "SKILL.md").is_file():
        parser.error("Bundled shared-memory skill is missing")
    if skill_link.exists() or skill_link.is_symlink():
        if not skill_link.is_symlink() or skill_link.resolve() != skill_source:
            parser.error(f"Skill destination already has another owner: {skill_link}")
    wrapper = root / ".state" / "adapters" / "shared-memory.ts"
    commands = {
        harness: shlex.join([str(cli), "--root", str(root), "hook", "--harness", harness])
        for harness in ("codex",)
    }
    arguments = ["--root", str(root), "serve"]
    paths = [home / "config.toml", home / "hooks.json", pi / "mcp.json", pi / "settings.json"]
    before = {str(path): path.read_bytes() if path.exists() else None for path in paths}
    codex_config = tomllib.loads((home / "config.toml").read_text()) if (home / "config.toml").exists() else {}
    existing = codex_config.get("mcp_servers", {}).get(NAME)
    if existing and (existing.get("command") != str(cli) or existing.get("args", []) != arguments):
        parser.error("Codex shared-memory MCP entry has another owner")
    updates = {
        home / "hooks.json": add_hook(load_json(home / "hooks.json"), commands["codex"]),
        pi / "mcp.json": add_server(load_json(pi / "mcp.json"), str(cli), arguments),
        pi / "settings.json": add_extension(load_json(pi / "settings.json"), str(wrapper)),
    }
    plan = {"status": "plan", "store": str(root), "source": str(source),
            "config_files": [str(p) for p in paths], "skill": str(skill_link),
            "pi_extension": str(wrapper), "mcp_name": NAME}
    if not args.apply:
        print(json.dumps(plan, ensure_ascii=False, indent=2))
        return 0
    backup = root / ".state" / "config-backups" / (time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()) + "-" + uuid.uuid4().hex[:8])
    backup.mkdir(parents=True, mode=0o700)
    manifest = []
    for index, path in enumerate(paths):
        payload = before[str(path)]
        stored = backup / f"{index}-{path.name}"
        if payload is not None:
            stored.write_bytes(payload)
            os.chmod(stored, 0o600)
        manifest.append({"path": str(path), "existed": payload is not None, "backup": str(stored) if payload is not None else None})
    atomic_text(backup / "manifest.json", json.dumps(manifest, indent=2) + "\n")
    for path, data in updates.items():
        if (path.read_bytes() if path.exists() else None) != before[str(path)]:
            raise ValueError(f"Configuration changed during preflight: {path}")
        atomic_text(path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    factory = str(source / "adapters" / "pi" / "shared-memory.ts")
    wrapper_text = "import { createSharedMemoryExtension } from " + json.dumps(factory) + ";\n"
    wrapper_text += "export default createSharedMemoryExtension(" + json.dumps({"root": str(root), "cli": str(cli)}) + ");\n"
    atomic_text(wrapper, wrapper_text)
    skill_link.parent.mkdir(parents=True, exist_ok=True)
    if not skill_link.is_symlink():
        skill_link.symlink_to(skill_source, target_is_directory=True)
    if not existing:
        subprocess.run(["codex", "mcp", "add", NAME, "--", str(cli), *arguments],
                       env=dict(os.environ, CODEX_HOME=str(home)), check=True, capture_output=True, timeout=20)
    trust = trust_codex_hook(home, cwd, commands["codex"], backup / "codex-discovery.log")
    atomic_text(root / ".gitignore", "/.venv/\n/.state/\n/.writer-gate.sqlite3*\n") if not (root / ".gitignore").exists() else None
    print(json.dumps({**plan, "status": "installed", "backup": str(backup),
                      "codex_hook": trust}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
