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

## Progressive task-driven reading

Use as many relevant batches as the authorized task needs. A response budget or `limit` controls one delivery, not the total records, sessions, sources, pages or rounds the Agent may read. Bounded scope means the task question, source grants and frozen selections; do not invent a cumulative count quota or interpret the first batch as the entire evidence base. Existing backend protections can still reject a read: expose that gap, without calling it an empty result or completed review.

Start with task-bound context to locate useful claims and owners, then use discriminating search and full detail for the open question. Expand along original source routes, corrections, conditions and conflicting evidence that could change the answer. A preview or compact account is insufficient when omitted qualifications matter. First-page ranking does not establish that later evidence is irrelevant.

| Delivery | Needed continuation |
| --- | --- |
| `context` selected claims and `continuation` | Follow the returned read hint or original owner route. The hint is not a cursor over every omission; use targeted search/read to discover additional needed records. Repeating the same context request does not paginate. |
| `search` cards | Pass returned `next_offset` as `offset` and `corpus_revision` as `expected_revision`, retaining the same query, collection, mode and visibility. Inspect full records when previews omit needed evidence. |
| `read` / `overview_read` detail | Pass an item's `detail_page` as `page`, then each returned `next_page`. Reassemble the complete `detail_page.text` JSON before interpreting the claim. Read needed `read.omitted_ids` separately in smaller batches; retain the original request's selectors/projection flags and the returned revision. |
| `dream_catalog`, `source_list`, `memory_audit` | Pass returned `next_cursor` as `cursor` under the same selection and any cursor-bound budgets. Reassemble `memory_audit` JSON slices by their exact offsets/revision; retained visibility is not semantic review. |
| `source_read` public source pages | Continue the same original grant/path/branch selection with returned `next_cursor`. Preserve each returned frozen `selection` and version for review provenance; a page handle is not the next cursor. Use supported event/body continuation when needed details remain partial. |

Keep track of what is still needed: missing conditions, later user corrections, conflicting observations and original-source checks. This is task-local reasoning, not a new persistent queue. If a revision changes, restart that affected selection and reconcile the consumed evidence; do not splice different revisions or invent offsets, parser state or authority. Permission denial, unresolved ancestry or exhausted supported continuation remains an explicit dependent gap.

Stop when the requested judgment is supported with its decisive qualifiers, or explain what concrete blocker leaves it unresolved. For an explicitly requested complete review, traverse the authorized selection and account for exclusions/gaps; an ordinary task does not need to drain unrelated history merely because a cursor exists. Reading or delivering a page never counts as reviewing its meaning. Report scoped coverage rather than declaring whole-history success.

## Manual bounded Dreaming in the same MCP entry

Use `dream_catalog` and `source_read` to select granted sources; `run_start(review_objective={"id":"...", "question":"..."})` starts a bounded review only when authorized. Use `run_observe`, `run_materials`, `run_changes`, `coverage_mark`, `draft_submit`, `draft_read`, `draft_publish` and `run_close` in the current lane. Do not equate page delivery with semantic review, or no source changes with objective completion. Unresolved `issue_search` / `issue_resolve` proposals are advisory and never grant permission to run experiments. History episodes use `collection="history"` with provenance ranges and stay outside default context.

Bind the review question, selected source versions/cutoff and relevant scope before synthesis. Inspect existing work through `run_observe`/`run_changes`, and relevant records through bounded `memory_audit`, including candidates and inactive items where needed. Search related advisory issues; review their actual gaps even when source bytes are unchanged. Compare granted original owners against memory for missing accepted findings, stale current claims, duplicate accounts, apparent conflicts and scope mistakes. Do not turn a bounded selection into a claim of whole-history coverage.

Choose a disposition from evidence rather than aiming for a number of new records:

| Reviewed situation | Disposition |
| --- | --- |
| Unchanged candidate with sufficient original-source evidence | `record_approve` using its exact audited content digest and sources; preserve original payload, provenance and qualifier. |
| Review changes a candidate's proposition | Create separately reviewed knowledge; justify withdrawal of the old candidate or leave it pending with the precise gap. Dreaming supersession requires active predecessors, so do not relabel this as unchanged approval or supersede a candidate. |
| Compatible active duplicates with the same qualifier | `record_supersede` with every predecessor and a source-linked successor retaining decision-changing conditions and limitations. |
| Different populations, checkpoints, versions or conditions | Retain separate conditional observations; establish actual replacement before superseding. Unresolved conflict stays explicit. |
| Established rejection or no-use | Granted `record_withdraw` with its source-checked reason; retain logical history. |
| Merely obsolete relevance, with no retirement action | Report the retirement need. Do not substitute withdrawal or call ordinary `curate` to bypass the DreamRun action policy. |
| Missing evidence, permission, ancestry or a user-owned decision | Defer the affected claim with its blocker and revisit condition in existing candidate content or run disposition; do not publish it through a view. |

Apply the [progressive reading guidance](#progressive-task-driven-reading) to the selected review sources: use supported exact event/body/page continuation before classifying needed material as oversized or unreadable, with no cumulative count quota. Keep source revisions and branch selection fixed; delivered pages are not semantic review. If access is forbidden, sensitive-content filtering rejects material, ancestry is unresolved or supported continuation is exhausted, retain that dependent gap and finish independently supported work. A moved source path is not proof that a prohibition can be bypassed.

When the reviewed account changes, refresh affected compact views/navigation as needed. Keep as-of status, original-source routes, necessary conditions and counterevidence attached; detailed records carry the longer account. A compact view is not a place to promote unresolved candidate claims. Fit is determined by the actual serialized consumer budget, not a universal character count; retain whole qualified units or explicit read routes.

After publication, verify applicable ordinary target `context` plus discriminating `search/read` with real caller identity and default active eligibility, rather than relying on audit visibility. Never borrow a target session identity; report a consumer gap when that boundary cannot be exercised. Resolve an advisory issue only after checking its requested correction or conclusion at the authoritative owner, with evidence; publishing a memory alone does not resolve it. Close the bounded Run after reconciling effects and dispositions, reporting what was added/approved/replaced/deferred, remaining gaps, coverage and consumer usefulness separately from technical success. Stop there; no speculative repeated repair or automatic next batch.

## Session handoff

Write the requested local handoff document with current state, owned files, next actions and any running-job recovery information. The receiving session reads it directly. Store a separate durable finding only if it adds reusable source-linked knowledge. A release/progress/assignment snapshot by itself is not such a finding and cannot be captured as `handoff`.
