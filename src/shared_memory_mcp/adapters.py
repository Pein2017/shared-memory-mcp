"""Recall-only translation of documented Claude and Codex SessionStart events.

Hook context is append-only in both hosts. Each boundary requests a current
bounded view; these adapters neither read transcripts nor capture memories.
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
                max_chars: int = 6000, dream_profile: str | None = None,
                dream_scenario: str = 'general') -> dict[str, Any]:
    """Translate only the actual native cwd/session; never use process cwd."""
    caller = _caller(harness, event)
    result = store.context(caller, limit=limit, max_chars=max_chars)
    if dream_profile:
        from .dream_transport import append_startup_collaboration
        result = append_startup_collaboration(store, caller, result, dream_profile,
                                               dream_scenario, max_chars=max_chars)
    if not isinstance(result, dict) or result.get("status") != "ok":
        info = result.get("diagnostic") if isinstance(result, dict) else None
        hint = info.get("onboarding") if isinstance(info, dict) else None
        if (isinstance(hint, str) and hint.startswith('Shared-memory onboarding diagnostic:')
                and len(hint) <= max_chars and '<shared-memory-context>' not in hint):
            return {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": hint}}
        status = result.get("status") if isinstance(result, dict) else None
        raise AdapterInputError("Core could not resolve context",
                                status if status in ("unmapped", "ambiguous", "invalid") else "invalid_context_output")
    text = result.get("text") if isinstance(result, dict) else None
    if not isinstance(text, str) or len(text) > max_chars:
        raise AdapterInputError("Core returned invalid or oversized context")
    if not text:
        return {}
    return {"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": text}}


def hook_main(store: Any, harness: str, *, stdin: TextIO | None = None,
              stdout: TextIO | None = None, stderr: TextIO | None = None,
              dream_profile: str | None = None, dream_scenario: str = 'general') -> int:
    """Emit host JSON; errors inject no memory and remain advisory to the host."""
    stdin = sys.stdin if stdin is None else stdin
    stdout = sys.stdout if stdout is None else stdout
    stderr = sys.stderr if stderr is None else stderr
    try:
        raw = stdin.read(1_048_577)
        if len(raw) > 1_048_576:
            raise AdapterInputError("Hook event exceeds input limit")
        try:
            event = json.loads(raw)
        except (json.JSONDecodeError, ValueError) as exc:
            raise AdapterInputError("Hook stdin must be a JSON event") from exc
        output = handle_hook(store, harness, event, dream_profile=dream_profile, dream_scenario=dream_scenario)
    except Exception as exc:
        # Do not echo raw native input, transcript paths, credentials, or records.
        code = getattr(exc, "code", "adapter_error")
        print(json.dumps({"shared_memory": "empty", "diagnostic": str(code)[:120],
                          "error_type": type(exc).__name__}), file=stderr)
        output = {}
    print(json.dumps(output, ensure_ascii=False), file=stdout)
    return 0
