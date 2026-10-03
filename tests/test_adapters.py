"""Native hook shape fixtures, not live host qualification."""
import io
import json
from pathlib import Path
import tempfile
import unittest

from shared_memory_mcp.adapters import AdapterInputError, handle_hook, hook_main


class Store:
    def __init__(self, text="<shared-memory-context>bounded memory</shared-memory-context>"):
        self.text = text
        self.calls = []

    def context(self, context, **kwargs):
        self.calls.append((context, kwargs))
        return {"status": "ok", "text": self.text, "scope": {}, "items": [], "omitted": 0, "truncated": False}


class HookAdaptersTest(unittest.TestCase):
    def event(self, **changes):
        event = {"session_id": "fixture-session", "transcript_path": "/do/not/read.jsonl",
                 "cwd": "/actual/host/project", "hook_event_name": "SessionStart",
                 "source": "startup", "permission_mode": "default"}
        event.update(changes)
        return event

    def test_native_event_shapes_use_supplied_cwd(self):
        for harness in ("claude", "codex"):
            for source in ("startup", "resume", "clear", "compact"):
                with self.subTest(harness=harness, source=source):
                    store = Store()
                    output = handle_hook(store, harness, self.event(source=source))
                    self.assertEqual(output, {"hookSpecificOutput": {"hookEventName": "SessionStart",
                                                                     "additionalContext": store.text}})
                    self.assertEqual(store.calls[0][0], {"cwd": "/actual/host/project", "harness": harness,
                                                        "session_id": "fixture-session", "actor": harness})

    def test_invalid_context_never_calls_core(self):
        for changes in ({"cwd": "relative"}, {"cwd": ""}, {"cwd": None},
                        {"session_id": ""}, {"hook_event_name": "PreToolUse"},
                        {"source": "invented"}):
            with self.subTest(changes=changes):
                store = Store()
                with self.assertRaises(AdapterInputError):
                    handle_hook(store, "codex", self.event(**changes))
                self.assertEqual(store.calls, [])

    def test_empty_core_context_injects_nothing(self):
        self.assertEqual(handle_hook(Store(""), "claude", self.event()), {})

    def test_core_budget_is_passed_and_overflow_fails_closed(self):
        store = Store("x" * 81)
        with self.assertRaises(AdapterInputError):
            handle_hook(store, "codex", self.event(), max_chars=80)
        self.assertEqual(store.calls[0][1], {"limit": 8, "max_chars": 80})

    def test_unmapped_core_context_is_empty_with_diagnostics(self):
        class UnmappedStore:
            def context(self, *_args, **_kwargs):
                return {"status": "unmapped", "text": "", "scope": None, "items": [],
                        "omitted": 0, "truncated": False, "diagnostic": "No project"}
        output, errors = io.StringIO(), io.StringIO()
        self.assertEqual(hook_main(UnmappedStore(), "codex", stdin=io.StringIO(json.dumps(self.event())),
                                   stdout=output, stderr=errors), 0)
        self.assertEqual(json.loads(output.getvalue()), {})
        self.assertEqual(json.loads(errors.getvalue())["diagnostic"], "unmapped")

    def test_cli_malformed_event_is_empty_json_with_stderr_diagnostic(self):
        output, errors = io.StringIO(), io.StringIO()
        code = hook_main(Store(), "codex",
                         stdin=io.StringIO("[]"), stdout=output, stderr=errors)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue()), {})
        self.assertIn("adapter_input", errors.getvalue())

    def test_cli_transport_is_json_and_does_not_mix_diagnostics(self):
        store = Store()
        output, errors = io.StringIO(), io.StringIO()
        code = hook_main(store, "claude", stdin=io.StringIO(json.dumps(self.event())),
                         stdout=output, stderr=errors)
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["hookSpecificOutput"]["additionalContext"], store.text)
        self.assertEqual(errors.getvalue(), "")

    def test_hooks_deliver_the_exact_shared_core_bounded_snapshot(self):
        from shared_memory_mcp.core import MemoryStore
        with tempfile.TemporaryDirectory(prefix="shared-memory-hook-") as scratch:
            project = Path(scratch) / "actual-project"
            project.mkdir()
            store = MemoryStore(Path(scratch) / "memory")
            store.init()
            store.register("test-project", [str(project)])
            caller = {"cwd": str(project), "harness": "claude", "session_id": "fixture-session", "actor": "claude"}
            proposed = store.propose(caller, {"kind": "invariant", "title": "Fixture",
                "body": "Native stores remain separate.", "scope": "project",
                "sources": [{"uri": "file:///fixture/owner.md"}]}, "fixture-propose")
            store.promote(caller, proposed["record"]["id"],
                          {"reason": "Isolated fixture review", "evidence": [{"uri": "file:///fixture/owner.md"}]},
                          "fixture-review")
            expected = store.context(caller)
            event = self.event(cwd=str(project))
            output = handle_hook(store, "claude", event)
            self.assertEqual(output["hookSpecificOutput"]["additionalContext"], expected["text"])
            self.assertEqual(len(expected["items"]), 1)
            self.assertLessEqual(len(expected["text"]), 6000)


if __name__ == "__main__":
    unittest.main()
