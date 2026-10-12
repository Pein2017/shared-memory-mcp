## Why

The 2026-10-12 review of the live store, 145 Codex/Pi sessions and the Dreaming code found that the read/publish contract is strong but the write side and the lifecycle side are not: user corrections rarely enter memory, 50 candidates have no owner, 176 of 181 published records are self-reviewed, nothing in the store is ever pruned, and manual Dreaming cannot complete on real history because permanent reader gaps re-stage the same page every batch (20 of 24 runs ended with partial coverage, only 7 real session events ever entered the store). The 27-tool surface also uses five different pagination/revision/budget conventions, which produced most of the observed tool errors. The user has decided the trade-offs (recorded below) and wants one coherent v0.3 contract that subagents can implement in disjoint work packages.

## What Changes

- **BREAKING** Public interface v0.3: 27 tools become 21. `create` merges into `capture`; `update` becomes `supersede`; `delete` becomes `withdraw`; `curate` becomes `annotate`; `memory_audit` merges into `search`; `dream_catalog` merges into `source_list`; `run_observe`+`run_changes` become `dream_status`; `draft_submit`+`draft_read` become `dream_draft`; `coverage_mark` folds into `dream_draft` operations; remaining Dreaming tools take the `dream_` prefix (`dream_start`, `dream_materials`, `dream_publish`, `dream_close`, `dream_takeover`); `overview_read` becomes `overview`; issue tools become `issue_open`/`issue_list`/`issue_close`. No aliases are kept.
- **BREAKING** Argument and envelope normalization: the caller identity parameter is `caller` on every tool; one opaque `cursor`/`next_cursor` pagination form replaces offset/page/expected_revision; one `expected_revision` fence replaces content digests and run generations in caller-visible arguments; budgets are `limit` and `max_bytes` only (`max_events` stays on `source_read`); every success envelope has the same shape and every error carries a minimal correct example payload; `idempotency_key` becomes optional with a server-derived default.
- Caller identity gains optional `role`, `model`, `parent_session_id` and externally issued `task_id`, so a multi-harness workbench (HarnessDeck) can issue one identity per lead/worker. Task-scope records default to a bounded expiry and appear in task context.
- Review assurance is labeled, not blocked: cards and audit report `self-reviewed`, `cross-session-reviewed` or `dreaming-reviewed`. Candidates untouched for 7 days become `stale`: out of default recall, still searchable and reviewable.
- Retention policy: closed Dreaming runs drop retained transcript excerpts, config backups keep the latest three, stale lane markers and orphan checkpoints are prunable through an operator dry-run/apply command; canonical records are never physically deleted. Store directories get one consistent private permission.
- Secrets in ordinary writes produce a warning, never a rejection; `live_correction` required fields are unchanged.
- Dreaming closure: readers ignore known benign Codex and Claude event types instead of reporting unknown schema; `dream_close` can accept named permanent gaps; the reviewed baseline is keyed by target project so a new question does not re-review old history; view refreshes may cite claims of the previous revision; `dream_materials` is always paged; coverage marks are verified against served events; every Dreaming response carries a server-computed `next` step; a run without an objective defaults to candidate triage, self-review re-check, duplicates, conflicts and expiry; the five historical budget settings are documented as unenforced.
- **BREAKING** New capability `shared-memory-session-extraction`: a bounded, startup-triggered, cheap-model extraction of idle native sessions into non-recalled candidates (phase one), consumed by manual Dreaming (phase two). This reverses the current "no automatic transcript extraction, no background model call" requirements under explicit bounds: at most two sessions idle for at least one hour per root-session startup, no daemon, candidates never enter default recall, native memories are read-only inputs, subagent sessions are classified by harness/model/role rather than excluded.
- Claude: Agent-tool subagents receive a bounded caller identity through the documented SubagentStart injection; the Claude history reader treats `attachment`, `relocated` and `continued-in` as benign metadata.

## Capabilities

### New Capabilities
- `shared-memory-session-extraction`: startup-triggered bounded extraction of idle native session transcripts into source-linked, non-recalled candidates with harness/model/role lineage, for later manual Dreaming review.

### Modified Capabilities
- `shared-memory-public-interface`: operation names, merged tools, caller parameter, uniform pagination/fence/budget arguments and envelopes.
- `shared-memory-recall`: cursor-based continuation, assurance label on cards, audit folded into search, uniform envelope and `next` hints.
- `shared-memory-core`: caller identity fields, derived idempotency keys, stale candidates, task-scope default expiry, retention and permissions.
- `shared-memory-curation`: capture absorbs create, annotate replaces curate, secret warnings, future-organizer boundary replaced by the extraction capability.
- `shared-memory-dreaming`: benign event types, target-keyed baseline, previous-revision view refs, paged materials, verified coverage, server-computed next step, unenforced historical budgets.
- `shared-memory-history-review`: manual consolidation now consumes extracted candidates; accepted permanent gaps at close; default objective.
- `shared-memory-harness-integration`: lifecycle adapters may spawn bounded extraction; delegated workers receive bounded identity; Dreaming tools reachable through the same entrypoint under new names.
- `shared-memory-claude-integration`: SubagentStart identity injection; benign Claude event types.

## Impact

- Code: `src/shared_memory_mcp/` (mcp_operations, server, operations, cli, core, recall, curation, maintenance, adapters, dream_*), new `extract.py`, `scripts/install-local.py`, skill `skills/shared-memory/` and its operations reference, README tool table.
- External consumers that must follow (not tasks in this change): Pi `toolExposure` names in `/data/CoordExp/.pi/mcp.json`, the web-codex gateway tool name lookup and its redeploy, `routing/<project>.json` background records and the Dreaming policy source grants for `rollout_summaries`/Claude auto-memory directories (operator content, user-owned).
- Live installation of new hooks (SubagentStart, extraction spawn) and any paid cheap-model qualification need their own user authorization; this change plans and qualifies them with disposable stores and no model calls.
- Open change `improve-capture-and-dreaming-closure` tasks 3.1–3.3 remain user-gated and are referenced, not duplicated.

## User decisions encoded by this change (2026-10-12)

| Decision | Where encoded |
|---|---|
| 1A: native Codex/Claude memories and shared-memory split ownership; native stores are read-only Dreaming inputs, never written | session-extraction spec; skill guidance task |
| 2A: self-review is labeled, never blocked | recall spec (assurance), core spec |
| 3B: candidates untouched for 7 days become stale, still searchable | core spec |
| 4B: original transcripts are the primary extraction input; extraction and Dreaming resume after interruption | session-extraction, history-review specs |
| 5A: Dreaming may accept named permanent gaps and complete | history-review spec |
| 6A: reviewed baseline keyed by target project | dreaming spec |
| 7: trigger cadence/backlog line owned by the user | out of scope |
| 8A: retention: run excerpts cleared, backups keep three, markers prunable, originals never deleted | core spec |
| 9A: secrets warn only; `live_correction` fields unchanged | curation spec |
| 10: never modify native memories | session-extraction spec, non-goal in design |
| Extraction model gpt-6-luna or Claude Haiku; next-startup trigger; ≤2 sessions idle ≥1 h; candidates not in default recall; subagent sessions classified, no hard minimum size | session-extraction spec |
| Names `supersede`/`withdraw`/`annotate`; `coverage_mark` folded into `dream_draft`; no compatibility aliases | public-interface spec |
