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


def add_hook(document: dict, command: str, *, harness: str = "codex", event: str = "SessionStart") -> dict:
    """Own one command handler per event; the same command detects the event from stdin."""
    if event not in {"SessionStart", "SubagentStart"} or event == "SubagentStart" and harness != "claude":
        raise ValueError("Only Claude has an owned SubagentStart hook")
    legacy_matcher = "startup|resume|clear|compact"
    # SubagentStart matches every agent type: no matcher key.
    matcher = None if event == "SubagentStart" else legacy_matcher + ("|fork" if harness == "claude" else "")
    result = copy.deepcopy(document)
    groups = result.setdefault("hooks", {}).setdefault(event, [])
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
        if matcher is None:
            if "matcher" in group or handler.get("type") != "command":
                raise ValueError("Existing shared-memory hook has a conflicting contract")
            return result
        if group.get("matcher") not in {legacy_matcher, matcher} or handler.get("type") != "command":
            raise ValueError("Existing shared-memory hook has a conflicting contract")
        if group.get("matcher") != matcher:
            if len(group.get("hooks", [])) != 1:
                raise ValueError("Cannot change the matcher of a hook group shared with another owner")
            group["matcher"] = matcher
        return result
    groups.append({
        **({"matcher": matcher} if matcher is not None else {}),
        "hooks": [{"type": "command", "command": command, "timeout": 15}],
    })
    return result


LEGACY_NAME = "shared-memory-dreaming"


def plan_owned_legacy(document: dict, section: str, cli: str, root: Path, profiles: dict) -> dict:
    """Prove exact ownership before proposing removal of the old second provider.

    Unrecognized similarly named registrations are conflicts, not cleanup targets.
    This inspect-only contract has no subprocess or filesystem effects.
    """
    if section not in {"mcpServers", "mcp_servers"}:
        raise ValueError("Unsupported owned provider section")
    bindings = document.get(section, {})
    if not isinstance(bindings, dict):
        raise ValueError("Expected an MCP provider mapping")
    entry = bindings.get(LEGACY_NAME)
    if entry is None:
        return {"owned": False, "provider": LEGACY_NAME}
    if not isinstance(entry, dict):
        raise ValueError("Legacy Dreaming provider has an unrecognized descriptor")
    allowed = {"command", "args", "type", "startup_timeout_sec", "tool_timeout_sec", "enabled"}
    if section == "mcpServers":
        allowed.add("exposure")
        if "exposure" in entry and entry["exposure"] not in ("codemode", "deferred", "direct", "hidden"):
            raise ValueError("Legacy Pi MCP exposure is unrecognized")
    if set(entry) - allowed or entry.get("command") != cli:
        raise ValueError("Legacy Dreaming registration is not identifiably owned")
    if entry.get("type", "stdio") != "stdio" or entry.get("enabled", True) is not True:
        raise ValueError("Legacy Dreaming transport or enablement differs")
    args = entry.get("args")
    prefix = ["--root", str(root), "dream", "gateway", "--profile"]
    if (not isinstance(args, list) or len(args) not in (6, 7)
            or args[:len(prefix)] != prefix or
            args[5] not in profiles or
            (len(args) == 7 and args[6] != "--enable-publisher")):
        raise ValueError("Legacy Dreaming root/profile/arguments cannot be proven")
    if any(type(entry[k]) is not int or entry[k] < 0 for k in
           ("startup_timeout_sec", "tool_timeout_sec") if k in entry):
        raise ValueError("Legacy MCP timeouts are noncanonical")
    return {"owned": True, "provider": LEGACY_NAME, "profile": args[5],
            "publisher_selected": len(args) == 7}


def cutover_owned_legacy_json(document: dict, section: str, cli: str, root: Path,
                              profiles: dict) -> dict:
    """Plan/construct an exact one-provider JSON edit; preserve all other keys."""
    status = plan_owned_legacy(document, section, cli, root, profiles)
    result = copy.deepcopy(document)
    if status["owned"]:
        del result[section][LEGACY_NAME]
    return result


def require_active_common(entry: dict, command: str, arguments: list[str]) -> None:
    if (not isinstance(entry, dict) or entry.get("command") != command
            or entry.get("args", []) != arguments
            or entry.get("type", "stdio") != "stdio"
            or entry.get("enabled", True) is not True):
        raise ValueError("Expected the exact active shared-memory MCP entry before cutover")


def add_server(document: dict, command: str, arguments: list[str]) -> dict:
    result = copy.deepcopy(document)
    servers = result.setdefault("mcpServers", {})
    existing = servers.get(NAME)
    if existing is not None:
        if existing.get("command") != command or existing.get("args", []) != arguments:
            raise ValueError("Existing shared-memory MCP entry belongs to another configuration")
        require_active_common(existing, command, arguments)
    else:
        servers[NAME] = {"command": command, "args": arguments, "exposure": "direct"}
    return result


def claude_server_present(document: dict, command: str, arguments: list[str]) -> bool:
    servers = document.get("mcpServers", {})
    if not isinstance(servers, dict):
        raise ValueError("Claude mcpServers must be an object")
    if NAME not in servers:
        return False
    expected = {"type": "stdio", "command": command, "args": arguments}
    if servers[NAME] != expected:
        raise ValueError("Claude shared-memory MCP entry belongs to another configuration")
    return True


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
    parser.add_argument("--claude-dir", type=Path, help="Explicit opt-in Claude configuration directory")
    parser.add_argument("--cwd", required=True, type=Path, help="Registered project for native hook discovery")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    if not all((args.codex_home, args.pi_dir)):
        parser.error("Supply Codex and Pi configuration roots explicitly or through their named environment variables")
    source = Path(__file__).resolve().parents[1]
    root, cli, home, pi, cwd = (p.resolve() for p in (
        args.root, args.cli, args.codex_home, args.pi_dir, args.cwd,
    ))
    claude = args.claude_dir.resolve() if args.claude_dir else None
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
        for harness in (("codex", "claude") if claude else ("codex",))
    }
    arguments = ["--root", str(root), "serve"]
    paths = [home / "config.toml", home / "hooks.json", pi / "mcp.json", pi / "settings.json"]
    if claude:
        paths += [claude / "settings.json", claude / ".claude.json"]
    before = {str(path): path.read_bytes() if path.exists() else None for path in paths}
    codex_config = tomllib.loads((home / "config.toml").read_text()) if (home / "config.toml").exists() else {}
    existing = codex_config.get("mcp_servers", {}).get(NAME)
    if existing and (existing.get("command") != str(cli) or existing.get("args", []) != arguments):
        parser.error("Codex shared-memory MCP entry has another owner")
    if existing is not None:
        require_active_common(existing, str(cli), arguments)
    policy = load_json(root / "dreaming" / "policy.json")
    profiles = policy.get("profiles", {})
    if not isinstance(profiles, dict):
        parser.error("Legacy Dreaming policy profiles cannot be inspected")
    pi_config = load_json(pi / "mcp.json")
    owned_legacy = {
        "codex": plan_owned_legacy(codex_config, "mcp_servers", str(cli), root, profiles),
        "pi": plan_owned_legacy(pi_config, "mcpServers", str(cli), root, profiles),
    }
    updates = {
        home / "hooks.json": add_hook(load_json(home / "hooks.json"), commands["codex"]),
        pi / "mcp.json": cutover_owned_legacy_json(
            add_server(pi_config, str(cli), arguments), "mcpServers", str(cli), root, profiles),
        pi / "settings.json": add_extension(load_json(pi / "settings.json"), str(wrapper)),
    }
    if claude:
        claude_native_config = load_json(claude / ".claude.json")
        owned_legacy["claude"] = plan_owned_legacy(
            claude_native_config, "mcpServers", str(cli), root, profiles)
        claude_registered = claude_server_present(claude_native_config, str(cli), arguments)
        updates[claude / "settings.json"] = add_hook(
            add_hook(load_json(claude / "settings.json"), commands["claude"], harness="claude"),
            commands["claude"], harness="claude", event="SubagentStart")
    plan = {"status": "plan", "store": str(root), "source": str(source),
            "config_files": [str(p) for p in paths], "skill": str(skill_link),
            "pi_extension": str(wrapper), "mcp_name": NAME,
            "owned_legacy": owned_legacy,
            "cutover_boundary": "Only exact old shared-memory-dreaming registrations; native memories and all unrelated entries are retained."}
    if claude:
        plan.update(claude_dir=str(claude), claude_hook={"command": commands["claude"],
            "matcher": "startup|resume|clear|compact|fork"},
            claude_subagent_hook={"command": commands["claude"], "event": "SubagentStart",
                                  "output": "bounded worker caller identity only"},
            claude_mcp={"scope": "user", "registration": "identical" if claude_registered else "add"})
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
    for path in paths:
        if (path.read_bytes() if path.exists() else None) != before[str(path)]:
            raise ValueError(f"Configuration changed during preflight: {path}")
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
    if claude:
        native_path = claude / ".claude.json"
        if (native_path.read_bytes() if native_path.exists() else None) != before[str(native_path)]:
            raise ValueError(f"Configuration changed during preflight: {native_path}")
        if not claude_registered:
            descriptor = {"type": "stdio", "command": str(cli), "args": arguments}
            subprocess.run(["claude", "mcp", "add-json", "--scope", "user", NAME, json.dumps(descriptor)],
                           env=dict(os.environ, CLAUDE_CONFIG_DIR=str(claude)), check=True,
                           capture_output=True, timeout=20)
        if not claude_server_present(load_json(native_path), str(cli), arguments):
            raise ValueError("Native Claude did not persist the owned MCP entry")
    # Remove an older second registration only after the common entry and hooks
    # are installed and exact ownership is checked again. No guessed cleanup.
    if owned_legacy["codex"]["owned"]:
        current = tomllib.loads((home / "config.toml").read_text())
        require_active_common(current.get("mcp_servers", {}).get(NAME), str(cli), arguments)
        if plan_owned_legacy(current, "mcp_servers", str(cli), root, profiles) != owned_legacy["codex"]:
            raise ValueError("Codex legacy registration changed before owned cutover")
        subprocess.run(["codex", "mcp", "remove", LEGACY_NAME],
                       env=dict(os.environ, CODEX_HOME=str(home)), check=True,
                       capture_output=True, timeout=20)
        if LEGACY_NAME in tomllib.loads((home / "config.toml").read_text()).get("mcp_servers", {}):
            raise ValueError("Codex legacy registration was not removed")
    if claude and owned_legacy["claude"]["owned"]:
        current = load_json(native_path)
        if not claude_server_present(current, str(cli), arguments):
            raise ValueError("Expected the exact active Claude shared-memory MCP entry before cutover")
        if plan_owned_legacy(current, "mcpServers", str(cli), root, profiles) != owned_legacy["claude"]:
            raise ValueError("Claude legacy registration changed before owned cutover")
        subprocess.run(["claude", "mcp", "remove", "--scope", "user", LEGACY_NAME],
                       env=dict(os.environ, CLAUDE_CONFIG_DIR=str(claude)), check=True,
                       capture_output=True, timeout=20)
        if LEGACY_NAME in load_json(native_path).get("mcpServers", {}):
            raise ValueError("Claude legacy registration was not removed")
    atomic_text(root / ".gitignore", "/.venv/\n/.state/\n/.writer-gate.sqlite3*\n") if not (root / ".gitignore").exists() else None
    print(json.dumps({**plan, "status": "installed", "backup": str(backup),
                      "codex_hook": trust}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
