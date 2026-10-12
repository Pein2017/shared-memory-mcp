"""Recall-only translation of documented Claude and Codex SessionStart events.

Hook context is append-only in both hosts. Each boundary requests a current
bounded view; these adapters neither read transcripts nor capture memories.
A root `startup` may additionally start the detached, store-configured session
extraction after the hook output is written. Claude `SubagentStart` receives
only a bounded worker caller identity, never a startup packet.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, TextIO


class AdapterInputError(ValueError):
    def __init__(self, message: str, code: str = "adapter_input") -> None:
        super().__init__(message)
        self.code = code


def _caller(harness: str, event: Any) -> dict[str, str]:
    if harness not in ("claude", "codex") or not isinstance(event, dict):
        raise AdapterInputError("Expected a Claude or Codex hook event object")
    if event.get("hook_event_name") != "SessionStart":
        raise AdapterInputError("Expected SessionStart")
    sources = {"startup", "resume", "clear", "compact"}
    if harness == "claude":
        sources.add("fork")
    if event.get("source") not in sources:
        raise AdapterInputError("Unsupported SessionStart source")
    cwd, session_id = event.get("cwd"), event.get("session_id")
    if not isinstance(cwd, str) or not cwd or not Path(cwd).is_absolute() or "\x00" in cwd:
        raise AdapterInputError("Hook cwd must be an absolute path")
    if not isinstance(session_id, str) or not session_id.strip():
        raise AdapterInputError("Hook session_id is required")
    return {"cwd": cwd, "harness": harness, "session_id": session_id, "actor": harness}


def handle_hook(store: Any, harness: str, event: Any, *, limit: int = 8,
                max_chars: int = 6000, max_bytes: int = 8000, state: dict | None = None) -> dict[str, Any]:
    """Translate only the actual native cwd/session; never use process cwd.

    `state["resolved"]` is set only when core returned a valid packet for a registered project.
    """
    caller = _caller(harness, event)
    result = store.context(caller, limit=limit, max_chars=max_chars, max_bytes=max_bytes)
    if not isinstance(result, dict) or result.get("status") != "ok":
        info = result.get("diagnostic") if isinstance(result, dict) else None
        hint = info.get("onboarding") if isinstance(info, dict) else None
        if (isinstance(hint, str) and hint.startswith('Shared-memory onboarding diagnostic:')
                and len(hint) <= max_chars and '<shared-memory-context>' not in hint):
            diagnostic = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": hint}}
            if len(json.dumps(diagnostic, ensure_ascii=False).encode('utf-8')) <= max_bytes:
                return diagnostic
        status = result.get("status") if isinstance(result, dict) else None
        raise AdapterInputError("Core could not resolve context",
                                status if status in ("unmapped", "ambiguous", "invalid", "budget-limited") else "invalid_context_output")
    exposed = result.get('caller_context', {})
    if (result.get('packet_version') != 1 or any(exposed.get(k) != caller[k] for k in ('cwd', 'harness', 'session_id', 'actor'))
            or result.get('scope', {}).get('cwd') != caller['cwd'] or not exposed.get('project_id')
            or exposed.get('project_id') != result.get('scope', {}).get('project_id')):
        raise AdapterInputError('Core returned another caller or an unsupported packet', 'invalid_context_scope')
    text = result.get("text") if isinstance(result, dict) else None
    if not isinstance(text, str) or len(text) > max_chars:
        raise AdapterInputError("Core returned invalid or oversized context")
    if state is not None:
        state["resolved"] = True
    if not text:
        return {}
    output = {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}
    if len(json.dumps(output, ensure_ascii=False).encode('utf-8')) > max_bytes:
        raise AdapterInputError('Serialized native context exceeds its byte cap', 'context_budget')
    return output


SUBAGENT_BYTES = 1024


def handle_subagent(store: Any, event: Any, *, max_bytes: int = SUBAGENT_BYTES) -> dict[str, Any]:
    """Bounded worker identity for a Claude Agent-tool subagent; the parent session is lineage only."""
    if not isinstance(event, dict) or event.get("hook_event_name") != "SubagentStart":
        raise AdapterInputError("Expected SubagentStart")
    cwd, parent = event.get("cwd"), event.get("session_id")
    agent_id, agent_type = event.get("agent_id"), event.get("agent_type") or "subagent"
    if not isinstance(cwd, str) or not cwd or not Path(cwd).is_absolute() or "\x00" in cwd:
        raise AdapterInputError("Hook cwd must be an absolute path")
    for value in (parent, agent_id, agent_type):
        if not isinstance(value, str) or not value.strip() or len(value) > 128:
            raise AdapterInputError("SubagentStart requires session_id, agent_id and a short agent_type")
    caller = {"cwd": cwd, "harness": "claude", "session_id": agent_id, "actor": agent_type,
              "role": "worker", "parent_session_id": parent}
    try:
        # Registry read only: never wait on the writer gate inside the host's hook timeout.
        scope = store._resolve(caller)
    except Exception as exc:
        raise AdapterInputError("Core could not resolve the worker scope", getattr(exc, "code", "invalid_context")) from exc
    identity = {"harness": "claude", "session_id": agent_id, "parent_session_id": parent, "role": "worker",
                "actor": agent_type, "cwd": cwd, "project_id": scope["project_id"]}
    text = ("Shared-memory worker caller: " + json.dumps(identity, ensure_ascii=False) +
            "\nCall shared-memory `context` with this caller before relying on shared memory; "
            "write under it, never under the parent session.")
    output = {"hookSpecificOutput": {"hookEventName": "SubagentStart", "additionalContext": text}}
    if len(json.dumps(output, ensure_ascii=False).encode("utf-8")) > max_bytes:
        raise AdapterInputError("Serialized worker identity exceeds its byte cap", "context_budget")
    return output


def hook_main(store: Any, harness: str, *, stdin: TextIO | None = None,
              stdout: TextIO | None = None, stderr: TextIO | None = None, spawn: Any = None) -> int:
    """Emit host JSON; errors inject no memory and remain advisory to the host."""
    stdin = sys.stdin if stdin is None else stdin
    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr
    startup, state = False, {}
    try:
        raw = stdin.read(1_048_577)
        if len(raw) > 1_048_576:
            raise AdapterInputError("Hook event exceeds input limit")
        try:
            event = json.loads(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            raise AdapterInputError("Hook stdin must be a JSON event") from exc
        if harness == "claude" and isinstance(event, dict) and event.get("hook_event_name") == "SubagentStart":
            output = handle_subagent(store, event)
        else:
            output = handle_hook(store, harness, event, state=state)
            # Only a resolved registered-project startup may start extraction (never onboarding/unmapped output).
            startup = state.get("resolved", False) and event.get("source") == "startup"
    except Exception as exc:
        # Do not echo raw native input, transcript paths, credentials, or records.
        code = getattr(exc, "code", "adapter_error")
        print(json.dumps({"shared_memory": "empty", "diagnostic": str(code)[:120],
                          "error_type": type(exc).__name__}), file=stderr)
        output = {}
    print(json.dumps(output, ensure_ascii=False), file=stdout)
    stdout.flush()
    if startup and getattr(store, "root", None) is not None:
        # After the output: extraction runs detached and can never delay or alter recall.
        try:
            if spawn is None:
                from .extract import spawn
            started = spawn(store, trigger={k: event.get(k) for k in ("cwd", "session_id", "source", "transcript_path")} | {"harness": harness})
            if started.get("diagnostic"):
                print(json.dumps({"shared_memory_extraction": "disabled", "diagnostic": started["diagnostic"]}), file=stderr)
        except Exception as exc:
            print(json.dumps({"shared_memory_extraction": "not_started", "error_type": type(exc).__name__}), file=stderr)
    return 0
