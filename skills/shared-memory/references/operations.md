# Onboarding and capture examples

Use the actual session identity and configured CLI/store. Examples use placeholder paths and event names; do not execute the placeholders verbatim.

## Unregistered task repository

```sh
shared-memory --root /path/to/store project --cwd /path/to/task-repository
```

Inspect the returned Git root, common identity and registration hint. If this is the first-party repository the authorized task is working on, run the returned existing `register` invocation, then discover again and use its resolved project ID with the same actual cwd/session. A linked worktree can resolve to an existing project without a new binding. A conflict/restricted binding needs reconciliation rather than a guessed parent scope. Scope read operations never register implicitly; registration does not create sharing permissions.

## v0.3 argument and response conventions

- Identity: every tool takes `caller` = `{cwd, harness, session_id, actor}` plus optional `project_id`, `task_id`, `role` (`lead`/`worker`), `model`, `parent_session_id`. Lineage fields are provenance only. Task scope needs an externally issued `task_id`; task records default to a 14-day expiry and are shared by callers in the same worktree and task.
- Continuation: paginated tools (`search`, `read`, `source_list`, `source_read`, `dream_materials`, `overview`, `issue_list`) return `next_cursor`; pass it unchanged as `cursor` with the same other arguments. A tampered or foreign cursor fails `invalid_cursor`; a changed corpus or source fails `stale_cursor` — restart without a cursor.
- Fences: writes that depend on a prior read take one `expected_revision`: a record's `revision` from `read` (for `annotate`), the run `revision` from `dream_status`/`dream_draft` (for `dream_draft`, `dream_publish`, `dream_close`, `dream_takeover`, `issue_open`), or an issue's `revision` from `issue_list` (for `issue_close`). A stale fence fails without effect and reports `current_revision`.
- Budgets: `limit` (items) and `max_bytes` (serialized size); `max_events` exists only on `source_read`. Reads wait up to 5 s for a held writer gate, then fail `writer_busy`: retry.
- Notices: writes are not rejected for secret-like text; `secret_pattern` names the pattern class, `volatile_source` flags `/tmp`-style sources and `live_locator_missing` asks for a transcript-file locator on live corrections. Stored bytes are unchanged.
- Status and assurance: `search(statuses=[...], scopes=[...])` lists effective status (`candidate`, `stale`, `active`, `superseded`, `expired`, `withdrawn`, `withdrawal`, `retired`) within the caller's own scope and needs no Dreaming profile. `assurance` (`self-reviewed`, `cross-session-reviewed`, `dreaming-reviewed`, `model-extracted`, `candidate`) labels review provenance and only breaks ranking ties.
- Idempotency: `idempotency_key` is optional on `capture`, `approve`, `supersede`, `withdraw`, `annotate` and `issue_close`. When omitted the server derives `derived:<sha256(session_id + canonical payload)>` and returns it; an identical retry replays, and reusing a returned key with changed content fails `idempotency_conflict`.
- Envelope: success has `status:"ok"`, `scope`, `revision`, `item` or `items`, `next_cursor`, `omitted` (named counts), `truncated`, `notices`, `budget{limit_bytes, used_bytes}`; Dreaming tools add `next{tool, args}`. The `context` startup packet keeps its documented `packet_version: 1` shape. Errors are `{status:"error", diagnostic:{code, message, example?}}`; a wrong field name or missing argument includes a minimal correct `example`. Retired 0.2 names return `unknown_tool` naming the replacement.

## Source-reviewed reusable finding

`capture` accepts the following argument shape. Obtain `caller` from the session; the example is not a replacement caller identity.

```json
{
  "caller": {
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

For direct current-user corrections, a reviewed `capture(..., live_correction=..., details.extensions.narrative.replaces=[...])` can publish a scoped successor to a specific source-only view unit immediately, with a truthful missing native locator if necessary. For an existing record, capture a successor candidate, then `supersede` its exact-scope predecessor `old_ids` after review. `capture(review=...)` already publishes. `annotate(retired=true)` ends default relevance without declaring falsehood; `withdraw` is a reviewed logical withdrawal; no predecessor revival.

## One-call current-user correction

An authorized foreground Agent must inspect the **direct current user message**, not quoted, delegated or historical text. It may write the following only within the already granted project/scope. The overview unit reference must come from a fresh `overview` result, not a guessed index.

```json
{
  "caller": {
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
| `search` cards | Pass returned `next_cursor` as `cursor`, retaining the same query, collection, mode and visibility. Inspect full records when previews omit needed evidence. |
| `read` / `overview` detail | Pass an oversized item's `cursor`, then each returned `next_cursor`. Reassemble the complete `detail_page.text` JSON before interpreting the claim. Read needed `read.omitted_ids` separately in smaller batches; retain the original request's selectors/projection flags. |
| `source_list`, status `search` | Pass returned `next_cursor` as `cursor` under the same selection. Reassemble status-search JSON slices in order; retained visibility is not semantic review. |
| `source_read` public source pages | Continue the same original grant/path/branch selection with returned `next_cursor`. Preserve each returned frozen `selection` and version for review provenance; a page handle is not the next cursor. Use supported event/body continuation when needed details remain partial. |

Keep track of what is still needed: missing conditions, later user corrections, conflicting observations and original-source checks. This is task-local reasoning, not a new persistent queue. If a revision changes, restart that affected selection and reconcile the consumed evidence; do not splice different revisions or invent offsets, parser state or authority. Permission denial, unresolved ancestry or exhausted supported continuation remains an explicit dependent gap.

Stop when the requested judgment is supported with its decisive qualifiers, or explain what concrete blocker leaves it unresolved. For an explicitly requested complete review, traverse the authorized selection and account for exclusions/gaps; an ordinary task does not need to drain unrelated history merely because a cursor exists. Reading or delivering a page never counts as reviewing its meaning. Report scoped coverage rather than declaring whole-history success.

## Evidence-preserving distillation

Apply this to foreground capture and manually requested Dreaming. It guides existing record content and dispositions; it adds no schema, action or status.

- **Signal:** Keep a finding only if it could improve a future Agent's concrete decision. Routine progress and unchanged baselines may yield no new memory. A no-new-knowledge conclusion does not need a record or new status. Unresolved review still needs a disposition even when source bytes are unchanged.
- **Outcome:** Use `success`, `partial`, `fail` or `uncertain` as reviewer prose only when useful, in existing body/conditions or the reason of an already warranted disposition. Separate technical execution, scientific result, authorization and scope. Prefer evidence and checked original user corrections over an assistant's self-report; a user's move to another task or a passing test does not establish scientific success. For a useful failure, retain its trigger/conditions, failed approach, cause only if established, repair/check and future failure shield or revisit condition. Do not force every record into a template. Keep `dream_close.objective_outcome` at its supported `reviewed`/`disposed` values and coverage statuses at `processed`, `excluded`, `no-signal` or `pending-review`.
- **Corrections:** Compare the original source, authorship assurance, scope and conditions. A verified original correction overrides a derivative summary only for that proposition; preserve unrelated dated results. A `role=user` or caller marker does not prove authorship. Never promote historical, quoted or delegated text through `live_correction(kind="direct-current-user")`. Keep unresolved authorship or conflict pending.
- **Compatible deduplication:** Merge only compatible claims. Retain decision-changing qualifiers, claim-linked original source routes, counterevidence and exact distinctive user phrasing, errors or API identifiers that aid retrieval. Use supported record details such as `aliases` and `topics`; `details.search_terms` is not a supported record field. Check that original query terms still find the successor or qualified view. Different conditions coexist, and duplicate summaries are not independent support. An unavailable or deleted derivative source does not make a claim false: retain independently supported parts and keep unsupported parts explicit and pending rather than placing them in a published view.
- **Acceptance gaps:** Keep uncertain or unsupported acceptance claims pending with the exact evidence gap and a concrete revisit condition.

## Manual bounded Dreaming in the same MCP entry

### Dreaming scope and completion

The user-aligned default is an objective spanning successive batches, with scope expansion when relevant evidence is discovered. The first baseline includes the applicable readable historical Pi/Codex backlog and existing memory, not just recent or completed sessions; later rounds review new/changed inputs and unresolved work since the last reviewed positions. An explicitly narrower request retains its own scope. A first batch, source count or file inventory alone never establishes historical semantic coverage.

Choose a cutoff for the objective. Active sessions contribute their already persisted complete events, preserving unfinished outcomes as unfinished. Follow relevant corrections, conflicts, related sessions, dependencies and original owners into additional source batches; relevant pre-cutoff discoveries enlarge the remaining work under the same objective. Record source-specific frozen ranges and capture times; do not claim an atomic filesystem snapshot from a wall-clock timestamp. Content after the admitted cutoff is work for the next round, not a reason to chase an active tail forever.

Continue while readable, unreviewed work remains in the objective. Per-response and backend protections remain; do not add a cumulative count, elapsed-time or fee stop that the user did not request. Closing one reconciled technical Run does not end the encompassing objective. Use successive Runs under the existing lane rules as necessary, carrying outstanding selections/dispositions forward. A real harness/context interruption or concrete permission, parsing, version or publication blocker requires an exact remaining-work position and explicit partial coverage; a user stop always takes precedence. Do not relaunch uncertain writes before reconciliation or recreate a rejected action through another route. A reviewed partial batch cannot advance a whole-history baseline past unread or pending material. Independently supported work can complete while a dependent gap remains.

Desired read access follows the originating Agent's effective read permissions, including relevant unregistered sources, without a second fixed directory allowlist. Relevance selects reads; write targets and publication authority stay separately scoped. Existing accepted memory is itself an eligible consolidation input: ordinary merging need not reread every raw transcript or rebind every original source digest. Retain its actual evidence level, qualifications and gaps; check a current original owner for a current-status answer, action or conclusion correction. Obsolete, duplicate or conflicting memory, including research evidence and user corrections, can be absorbed into reviewed successors and leave default recall while raw sources and recoverable lifecycle history remain. Different conditions remain explicit; an unresolved same-condition conflict can become a concise undecided account with the essential alternatives and revisit condition, without accepting either disputed conclusion.

SHA/revision fences protect source ranges, concurrent edits, replay and recovery; they are not a semantic truth test or a reason to requalify unchanged knowledge. Treat returned references as opaque handles, keeping human-facing accounts focused on meaning and usable source routes. Do not invent handles or omit fields required by the current API.

Runtime contract: trusted `read_access="inherited"` profiles admit relevant absolute source selectors (`absolute_path`, `format`, `schema`, optional `native_version`) within the process's effective access. `source_list` also accepts an absolute directory in that mode. Existing grants remain useful navigation and retain their original bindings; read access never widens write targets or publication actions. Restricted profiles continue to require grants. Preserve returned cutoff/page selectors verbatim. Appends after a frozen cutoff do not invalidate consumed ranges; consumed-byte changes, replacement, truncation and relevant structural changes still block dependent publication.

`dream_start(review_objective=...)` freezes configured historical roots plus exact-file grants and target memory into a durable objective inventory. Reviewed positions are keyed by target: a new objective on a reviewed target pends only new or changed sources, and `review_objective.reread=[{source_id, range}]` restarts a source from byte 0. Without `review_objective`, the default maintenance objective inventories candidates by age (including stale and `model-extracted` ones), self-reviewed actives, duplicate titles, missing sources, expired actives and open issues, and reads no native history. Explicit `sources` narrows the initial source selection or expands an existing objective by another batch. `dream_status` reports `objective_progress` (remaining sources, memory revisions, gaps and ready selections) and the bounded `changes`; every Dreaming response's `next` names the following call with filled arguments. `dream_materials` without `event_key` returns a summary page (key, length, 200-character preview) with a cursor; a preview counts as read only when it holds the whole text. Read a memory record fully with `dream_materials(event_key="record:<id>")`. Record coverage as `dream_draft` operations `{"type":"coverage","statuses":{...}}` (`processed`, `excluded`, `no-signal`, `pending-review`); it takes effect at `dream_publish`. Marking an event or record not served to the current attempt fails `unserved_event` (after `dream_takeover`, re-read). Empty readable pages use `source:<source_id>` coverage. Delivery alone never advances review. A source's reported permanent gap can be accepted with `dream_close(accept_gaps=[{source_id, reason, note}])`, which advances past it; unreported gaps cannot be accepted. Closing strips retained event text (`text_retained: false`), keeping keys, digests and receipts. Close each reconciled batch without `objective_outcome` while backlog remains, then start the same id/question for the next batch. Only the final reviewed/disposed close can complete the whole cutoff objective. Later appends and changed/new memories become a subsequent increment after completion; unchanged reviewed inputs keep their positions. Interrupted close is recovered from the durable Run. Internal sharded checkpoints preserve backend file limits without imposing a cumulative reading quota.

Use `source_list` (without `grant_id` it lists grants and active runs) and `source_read` to select admitted sources; `dream_start(review_objective={"id":"...", "question":"..."})` starts a bounded review only when authorized. Use `dream_status`, `dream_materials`, `dream_draft` (reviewed operations and coverage; returns the frozen draft), `dream_publish` and `dream_close` in the current lane, following each response's `next`. Do not equate page delivery with semantic review, or no source changes with objective completion. Unresolved `issue_list` / `issue_close` proposals are advisory and never grant permission to run experiments. History episodes use `collection="history"` with provenance ranges and stay outside default context.

Bind the review question, selected source versions/cutoff and relevant scope before synthesis. Inspect existing work through `dream_status`, and relevant records through bounded status `search`, including candidates and inactive items where needed. Search related advisory issues; review their actual gaps even when source bytes are unchanged. Compare granted original owners against memory for missing accepted findings, stale current claims, duplicate accounts, apparent conflicts and scope mistakes. Do not turn a bounded selection into a claim of whole-history coverage.

Choose a disposition from evidence rather than aiming for a number of new records, applying the [evidence-preserving distillation rubric](#evidence-preserving-distillation):

| Reviewed situation | Disposition |
| --- | --- |
| Unchanged candidate with sufficient original-source evidence | `record_approve` using its exact audited content digest and sources; preserve original payload, provenance and qualifier. |
| Review changes a candidate's proposition | Create separately reviewed knowledge; justify withdrawal of the old candidate or leave it pending with the precise gap. Dreaming supersession requires active predecessors, so do not relabel this as unchanged approval or supersede a candidate. |
| Compatible active duplicates with the same qualifier | `record_supersede` with every predecessor and a source-linked successor retaining decision-changing conditions and limitations. |
| Different populations, checkpoints, versions or conditions | Retain separate conditional observations; establish actual replacement before superseding. Unresolved conflict stays explicit. |
| Established rejection or no-use | Granted `record_withdraw` with its source-checked reason; retain logical history. |
| Merely obsolete relevance, with no retirement action | Report the retirement need. Do not substitute withdrawal or call ordinary `annotate` to bypass the DreamRun action policy. |
| Missing evidence, permission, ancestry or a user-owned decision | Defer the affected claim with its blocker and revisit condition in existing candidate content or run disposition; do not publish it through a view. |

Apply the [progressive reading guidance](#progressive-task-driven-reading) to the selected review sources: use supported exact event/body/page continuation before classifying needed material as oversized or unreadable, with no cumulative count quota. Keep source revisions and branch selection fixed; delivered pages are not semantic review. If access is forbidden, sensitive-content filtering rejects material, ancestry is unresolved or supported continuation is exhausted, retain that dependent gap and finish independently supported work. A moved source path is not proof that a prohibition can be bypassed.

When the reviewed account changes, refresh affected compact views/navigation as needed. Keep as-of status, original-source routes, necessary conditions and counterevidence attached; detailed records carry the longer account. A compact view is not a place to promote unresolved candidate claims. Fit is determined by the actual serialized consumer budget, not a universal character count; retain whole qualified units or explicit read routes.

After publication, verify applicable ordinary target `context` plus discriminating `search/read` with real caller identity and default active eligibility, rather than relying on audit visibility. Never borrow a target session identity; report a consumer gap when that boundary cannot be exercised. Resolve an advisory issue only after checking its requested correction or conclusion at the authoritative owner, with evidence; publishing a memory alone does not resolve it. Close the technical Run after reconciling effects and dispositions, reporting what was added/approved/replaced/deferred, remaining gaps, coverage and consumer usefulness separately from technical success. Continue the encompassing authorized objective through further relevant batches while readable unreviewed work remains; stop at objective completion, a concrete remaining blocker or user interruption, with exact continuation for any gap.

## Session handoff

Write the requested local handoff document with current state, owned files, next actions and any running-job recovery information. The receiving session reads it directly. Store a separate durable finding only if it adds reusable source-linked knowledge. A release/progress/assignment snapshot by itself is not such a finding and cannot be captured as `handoff`.
