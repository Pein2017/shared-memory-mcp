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

For direct current-user corrections, a reviewed `capture(..., live_correction=..., details.extensions.narrative.replaces=[...])` can publish a scoped successor to a specific source-only view unit immediately, with a truthful missing native locator if necessary. For an existing record, create a successor candidate, then `update` its exact-scope predecessor IDs after review. `capture(review=...)` already publishes. `curate(retired=true)` ends default relevance without declaring falsehood; `delete` is a reviewed logical withdrawal; no predecessor revival.

## One-call current-user correction

An authorized foreground Agent must inspect the **direct current user message**, not quoted, delegated or historical text. It may write the following only within the already granted project/scope. The overview unit reference must come from a fresh `overview_read` result, not a guessed index.

```json
{
  "context": {
    "cwd": "/path/to/registered-project",
    "harness": "codex",
    "session_id": "actual-session-id",
    "actor": "actual-agent"
  },
  "collection": "project",
  "record": {
    "kind": "decision",
    "title": "Review route pause",
    "body": "This route is paused; separate prior results retain their original conditions.",
    "scope": "project",
    "sources": [{"uri": "file:///path/to/research/owner.md"}]
  },
  "idempotency_key": "direct-correction:scoped-route:original-message:v1",
  "review": {
    "reason": "Checked the present, unquoted direct user correction and its actual project scope.",
    "evidence": [{"uri": "file:///path/to/research/owner.md"}]
  },
  "details": {
    "summary": "Route paused; unrelated dated results preserved.",
    "conditions": "Only the named route, not a separately preparing branch.",
    "statement_type": "user_decision",
    "extensions": {
      "narrative": {
        "id": "route.current",
        "role": "current",
        "replaces": ["view:research:REPLACE_WITH_EXACT_64_HEX_REVISION:0"]
      }
    }
  },
  "live_correction": {
    "kind": "direct-current-user",
    "excerpt": "Pause this route; retain the historical results.",
    "original_locator": null,
    "history_gap": "The native transcript event is not accessible for this present message.",
    "review_method": "Foreground Agent inspected the direct current user message."
  }
}
```

Use an exact real 64-hex revision and unit index. The source file's age does not grant authority, and `agent-reviewed` is **not** operator attestation or identity proof. Rejected or prohibited sources cannot be used as correction targets. If original native location is available, supply its true URI/locator instead of fabricating an event ID.

## Foreground current owner checks

When asked what is *currently* true or to make a consequential recommendation, call `context(query="...", task_mode="research"|"general", current_status=true)` with actual caller context. Inspect `owner_checks.status`, `gaps`, exact selected owner excerpts and source revision; open the source directly if needed. Routine background recall does not read every owner. Example CoordExp routes/source selectors are in `examples/coordexp-research-routing.json` and `examples/coordexp-research-grants.json`; they require an explicit operator-configured source policy, not automatic installation.

## Manual bounded Dreaming in the same MCP entry

Use `dream_catalog` and `source_read` to select granted sources; `run_start(review_objective={"id":"...", "question":"..."})` starts a bounded review only when authorized. Use `run_observe`, `run_materials`, `run_changes`, `coverage_mark`, `draft_submit`, `draft_read`, `draft_publish` and `run_close` in the current lane. Do not equate page delivery with semantic review, or no source changes with objective completion. Unresolved `issue_search` / `issue_resolve` proposals are advisory and never grant permission to run experiments. History episodes use `collection="history"` with provenance ranges and stay outside default context.

## Session handoff

Write the requested local handoff document with current state, owned files, next actions and any running-job recovery information. The receiving session reads it directly. Store a separate durable finding only if it adds reusable source-linked knowledge. A release/progress/assignment snapshot by itself is not such a finding and cannot be captured as `handoff`.
