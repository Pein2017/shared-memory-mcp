# Onboarding and capture examples

Use the actual session identity and configured CLI/store. Examples use placeholder paths and event names; do not execute the placeholders verbatim.

## Unregistered task repository

```sh
shared-memory --root /path/to/store project --cwd /path/to/task-repository
```

Inspect the returned Git root, common identity and registration hint. If this is the first-party repository the authorized task is working on, run the returned existing `register` invocation, then discover again and use its resolved project ID with the same actual cwd/session. A linked worktree can resolve to an existing project without a new binding. A conflict/restricted binding needs reconciliation rather than a guessed parent scope. Scope read operations never register implicitly; registration does not create sharing permissions.

## Source-reviewed reusable finding

The gateway's `capture` accepts the following argument shape. Obtain `context` from the session; the example is not a replacement caller identity.

```json
{
  "context": {
    "cwd": "/path/to/task-repository",
    "harness": "codex",
    "session_id": "actual-session-id",
    "actor": "codex",
    "project_id": "resolved-project-id"
  },
  "record": {
    "kind": "bug/root-cause",
    "title": "Checkpointed vision blocks reject text packing kwargs",
    "body": "On the checked implementation, text packing options reached the vision block and caused an unexpected-keyword failure. Filter those options at the text/vision boundary; this does not establish model-quality improvement.",
    "scope": "project",
    "sources": [{"uri": "file:///path/to/task-repository/research/result.md", "locator": "failure and repair evidence"}]
  },
  "details": {
    "summary": "Text-specific packing kwargs must not reach checkpointed vision blocks.",
    "conditions": "Applies to the source revision and execution path checked in the linked owner.",
    "domain": "engineering",
    "statement_type": "engineering_lesson"
  },
  "review": {
    "reason": "Read the original failure, source boundary and retained consumer check; reviewed only for the stated applicability.",
    "evidence": [{"uri": "file:///path/to/task-repository/research/result.md", "locator": "failure and repair evidence"}]
  },
  "idempotency_key": "source-event:owner-result:checked-revision:packing-boundary:v1"
}
```

Search for duplicates first when needed. The key identifies the original source event, not each tool attempt; replay the identical full payload/key after uncertainty. Different wording/review/metadata under the same key conflicts. Omit `review` if source checking or interpretation is incomplete; the capture remains a candidate. A published hypothesis still needs its actual evidence boundary.

For correction, create the successor candidate without review, read/review its evidence, then `update` that candidate's ID with exact-scope predecessor IDs. `capture(review=...)` already publishes and is not a candidate for a subsequent update. Use `curate(retired=true)` when relevance ends without declaring the original result false; use `delete` for reviewed withdrawal.

## Session handoff

Write the requested local handoff document with current state, owned files, next actions and any running-job recovery information. The receiving session reads it directly. Store a separate durable finding only if it adds reusable source-linked knowledge. A release/progress/assignment snapshot by itself is not such a finding and cannot be captured as `handoff`.
