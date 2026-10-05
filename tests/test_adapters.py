"""Native hook shape fixtures, not live host qualification."""
import io
import copy
import importlib.util
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

    def test_claude_fork_translation_is_fixture_only(self):
        store = Store()
        handle_hook(store, "claude", self.event(source="fork"))
        self.assertEqual(store.calls[0][0]["session_id"], "fixture-session")
        with self.assertRaises(AdapterInputError):
            handle_hook(Store(), "codex", self.event(source="fork"))

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
        from shared_memory_mcp.core import MemoryStore, WORKFLOW_REMINDER
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
            event = self.event(cwd=str(project))
            for harness in ("claude", "codex"):
                with self.subTest(harness=harness):
                    expected = store.context({**caller, "harness": harness, "actor": harness})
                    output = handle_hook(store, harness, event)
                    self.assertEqual(output["hookSpecificOutput"]["additionalContext"], expected["text"])
                    self.assertTrue(expected["text"].startswith(WORKFLOW_REMINDER + "\n<shared-memory-context>"))
                    self.assertEqual(expected["items"], [])
                    self.assertTrue(expected["records_not_loaded"])
                    self.assertNotIn("Native stores remain separate.", expected["text"])
                    self.assertEqual(store.read(caller, [proposed["record"]["id"]])["items"][0]["body"], "Native stores remain separate.")
                    self.assertLessEqual(len(expected["text"]), 6000)


class ClaudeNativeProbeAcceptanceTest(unittest.TestCase):
    def test_native_acceptance_rejects_wrong_identity_schema_model_and_exit(self):
        path = Path(__file__).with_name("native_startup_probe.py")
        spec = importlib.util.spec_from_file_location("native_probe_fixture", path)
        probe = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(probe)
        caller = {"cwd": "/actual/project", "session_id": "native-session", "harness": "claude", "actor": "claude"}
        request = {"sentinel_present": True, "record_id_present": True, "workflow_reminder_present": True, "model": probe.CLAUDE_MODEL,
                   "memory_tools": ["mcp__shared-memory__" + name for name in probe.TOOLS],
                   "memory_schema_tools": ["mcp__shared-memory__" + name for name in probe.TOOLS],
                   "effort_fields_present": False, "caller_contexts": [caller]}
        receipt = {"cwd": caller["cwd"], "session_id": caller["session_id"], "hook_event_name": "SessionStart",
                   "source": "startup", "exit_code": 0, "text_chars": 1500,
                   "sentinel_present": True, "record_id_present": True}
        result = {"exit_code": 1, "deadline_hit": False, "stdout": "", "stderr": ""}
        with tempfile.TemporaryDirectory() as scratch:
            receipt_path = Path(scratch) / "receipt.jsonl"
            receipt_path.write_text(json.dumps(receipt) + "\n")
            def status(actual_request=request, actual_result=result):
                return probe.summarize(copy.deepcopy(actual_result), [actual_request], receipt_path,
                                       "claude", caller["cwd"])["status"]
            self.assertEqual(status(), "pass")
            for changed in ({"workflow_reminder_present": False}, {"model": "other"}, {"memory_schema_tools": []}, {"effort_fields_present": True},
                            {"caller_contexts": [{**caller, "session_id": "invented"}]},
                            {"caller_contexts": [{**caller, "actor": "fixture"}]}):
                with self.subTest(changed=changed):
                    self.assertEqual(status({**request, **changed}), "limit")
            self.assertEqual(status(actual_result={**result, "exit_code": 0}), "limit")
            receipt_path.write_text(json.dumps({**receipt, "cwd": "/other/project"}) + "\n")
            self.assertEqual(status(), "limit")

    def test_native_reminder_observable_requires_the_same_startup_text(self):
        from urllib.error import HTTPError
        from urllib.request import Request, urlopen
        path = Path(__file__).with_name("native_startup_probe.py")
        spec = importlib.util.spec_from_file_location("native_probe_reminder_fixture", path)
        probe = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(probe)
        wrapper = '<shared-memory-context>SENTINEL RECORD_ID</shared-memory-context>'
        provider = probe.Provider('SENTINEL', 'RECORD_ID')
        try:
            for body, expected in (
                ({"messages": [{"content": probe.WORKFLOW_REMINDER + '\n' + wrapper}]}, True),
                ({"tools": [{"description": probe.WORKFLOW_REMINDER}], "messages": [{"content": wrapper}]}, False),
                ({"input": [{"type": "additional_tools", "tools": [{"description": probe.WORKFLOW_REMINDER + '\n' + wrapper}]}]}, False),
                ({"messages": [{"content": probe.WORKFLOW_REMINDER}, {"content": wrapper}]}, False),
                ({"messages": [{"content": probe.WORKFLOW_REMINDER + '\n<shared-memory-context>other</shared-memory-context>'},
                               {"content": wrapper}]}, False),
            ):
                with self.subTest(expected=expected, body=body):
                    request = Request(provider.url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
                    with self.assertRaises(HTTPError) as error:
                        urlopen(request, timeout=2)
                    self.assertEqual(error.exception.code, 400)
                    error.exception.close()
                    self.assertEqual(provider.requests[-1]['workflow_reminder_present'], expected)
        finally:
            provider.close()


if __name__ == "__main__":
    unittest.main()
