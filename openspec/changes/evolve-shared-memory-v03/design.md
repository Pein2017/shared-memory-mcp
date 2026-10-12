## Context

See proposal.md for motivation. Starting point: canonical HEAD `af4ffb7` plus the uncommitted working-tree changes of 2026-10-12 (Claude history reader allowlists, `.credentials.json` exclusion, Claude `fork` hook matcher, 85 focused tests passing). The open change `improve-capture-and-dreaming-closure` keeps its user-gated tasks 3.1–3.3; this change does not duplicate them. Live store: `/data/CoordExp/.shared-memory` (231 records, 24 closed runs, 50 candidates, 23 stale lane markers). Consumers: Codex hook, Pi extension, WebCodex gateway (looks up the tool named `context`), Claude hook; the user will redeploy WebCodex and update Pi exposure after the rename.

Facts that shape the design (verified 2026-10-12):
- Tool errors are dominated by argument shape: wrong caller field name, five pagination/fence conventions, `max_chars` accepted but not enforced.
- Dreaming cannot complete whole-history objectives because permanent reader gaps re-stage the same page (`objective_close` skips any non-`bounded_partial` gap; 60 % of sampled Codex files hit `unknown_event_schema`; Claude `attachment` is 28 % of current transcript lines).
- Reviewed positions are keyed by `(target, objective_id)`; 22 distinct objective ids exist, so every new question restarted from zero.
- `coverage_mark` is unverified; `run_materials` without `event_key` returns up to 96 × 4096 characters unpaged; five policy budgets are validated but never enforced while README calls two of them enforced.
- Claude session identity changes within one conversation (startup 14, fork 9, compact 8 hook firings in one project); Agent-tool subagents get no startup packet.
- Codex native memory (reference source under `/data/CoordExp/external/harness/codex`) extracts at startup, ≤2 rollouts idle ≥1 h, leases jobs in SQLite, redacts after the model call, and runs a second consolidation model. Its dedup is prompt-only.

## Goals / Non-Goals

**Goals:**
- One externally consistent v0.3 surface of twenty-one tools that a small model can drive from the `next` hints alone.
- Dreaming that completes on real history with explicit accepted gaps and a target-keyed baseline.
- A phase-one extraction that mirrors Codex's proven trigger/lease mechanics while keeping shared-memory's provenance, idempotency and candidate boundary.
- Disjoint work packages so subagents can implement in parallel without sharing files.

**Non-Goals:**
- Any write to native Codex or Claude memory directories, or cleanup of the Codex memories junk (user decision 10).
- A scheduler, daemon, per-turn hook extraction, or automatic publication of extracted content.
- Trigger cadence and the backlog reminder line (user decision 7, owned by the user).
- Compatibility aliases, shims or dual-name periods.
- Background briefing records, routing `background_ids` and new policy source grants: operator content, performed after installation.
- HarnessDeck integration itself; this change only makes the caller identity and extraction entrypoint Deck-ready.

## Decisions

**D1. Rename in place, no aliases, param `caller`.** The 0.2 CRUD names mislead (`update` is supersession, `delete` is withdrawal) and the tool/parameter collision on `context` is the single most frequent error. Alternatives: keep names and only fix descriptions (keeps the lie), or keep `context` as the parameter name (keeps the collision). The tool `context` keeps its name because the WebCodex gateway and all hooks look it up by name and the user will redeploy consumers anyway; renaming the argument is enough to remove the collision.

**D2. One cursor, one fence, one envelope.** Cursors become opaque base64url JSON `{kind, revision, position}` produced and validated by one helper; a changed revision rejects. `expected_revision` on writes maps internally to whichever digest the object uses (content digest, curation revision, run generation) through one resolver, so callers never see generations. Envelope assembly moves into one function in the operations layer so every tool shares `status/scope/revision/items|item/next_cursor/omitted/truncated/notices/budget` and Dreaming adds `next`. Alternative considered: per-tool envelopes with a shared subset; rejected because the inconsistency is what small models trip over.

**D3. Derived idempotency keys.** `sha256(session_id || canonical_json(record, details, review, collection))`, reported back as `idempotency_key`. Replay semantics unchanged; a caller-supplied key still wins. Trade-off: two identical captures by the same session for different events collapse; acceptable because identical payloads are identical knowledge.

**D4. Extraction is admissible under the "no daemon" principle.** The three current requirements that forbid automatic extraction were written to prevent unbounded, unreviewed, unattributed memory growth. Extraction as specified keeps every one of those properties: it is triggered only by a root startup, claims ≤2 idle sessions, uses the same public-projection readers (so private payloads never reach the model), writes only candidates with `assurance: model-extracted` that never enter default recall, leases work in the existing writer-gate SQLite, and records model/tokens/time per window. What changes is only that a cheap model call may happen outside a user turn. The hook spawns a detached process (`subprocess.Popen` with `start_new_session=True`, stdout/stderr to the extraction journal) and returns within its 15 s timeout. Model invocation goes through the harness-native CLI the user already pays for (`codex exec --model gpt-6-luna` or `claude --print --model claude-haiku-4-5`), selected per store in a new `extraction` section of the store configuration; no API keys are read by shared-memory. Alternative considered: Claude `SessionEnd` hook for immediate extraction; rejected because a Claude conversation produces several session files (fork/compact) and would be extracted in fragments.

**D5. Extraction input and output contract.** Input: public message text from the Dreaming readers, tool noise removed, secrets redacted, windowed at 200 KB. Prompt: fixed template per session class (root vs subagent) requesting strict JSON `{candidates:[{kind,title,body,conditions,source_events[]}], no_output: bool}`; invalid JSON is one retry then failure. Output written through `capture` without review, sources = `file://<transcript>` with event-range locators. Session class comes from reader metadata (`isSidechain`/`agentId` for Claude, Codex sub-agent flag, Pi subagent directory). Worker lineage fields (`model`, `effort`, `parent_session_id`) are filled when the transcript carries them; HarnessDeck can supply them later through the CLI entrypoint. Alternative: feed raw JSONL to the model; rejected for size (87 MB Pi files) and privacy.

**D6. Target-keyed baseline.** The objective index moves from `(target, objective_id)` to `target`, with per-source and per-record reviewed positions; an objective adds optional `reread: [{source_id, range}]`. Accepted gaps are stored in the same checkpoint with reason and note, and the inventory reports them. Alternative: keep objective keys plus a `continue_from` argument; rejected because it still demands the model remember a prior objective id.

**D7. Coverage inside drafts, verified against served events.** `dream_materials` appends served event keys to the attempt; `dream_draft` operations gain `{"type":"coverage","statuses":{...}}` validated against that set (or recovered excerpts). This removes one tool and the possibility of marking unread material. Alternative: keep `coverage_mark` and only verify; rejected because the user chose to fold it.

**D8. Reader allowlists.** Codex: `inter_agent_communication_metadata`, `agent_message`, `tool_search_call`, `tool_search_output` → skip, no gap. Claude: `attachment`, `relocated`, `continued-in` → skip, no gap; `native_versions` list accepted per root. Unknown types still gap. These are one-line set changes beside the current working-tree edits.

**D9. Retention.** `doctor --prune [--apply]` implements the four prunable classes; `dream_close` strips `text` from `run.json` events after receipts are written, keeping keys/digests; `dream_materials` on a closed run answers `text_retained: false`. Store directories are created `0o700`; `doctor` reports deviations but does not chmod existing directories (operator step).

**D10. Stale candidates and assurance are derived, not stored.** Both come from existing timestamps and reviewer/author session equality at read time, like `effective_status`; no file rewrite, no migration.

**D11. Claude subagent identity.** `adapters.py` accepts `hook_event_name: SubagentStart` with `agent_id`/`agent_type`; emits only caller identity (`session_id = agent_id`, `parent_session_id = session_id`, `role = worker`, `actor = agent_type`) and a one-line pointer, under 1 KB. The installer adds the owned SubagentStart hook group only with `--claude-dir`.

**D12. Work packages and ownership (one writer per surface).**
- WP1 Interface: `mcp_operations.py`, `server.py`, `operations.py`, `cli.py`, `skills/shared-memory/**`, README tool table. Lands first.
- WP2 Dreaming: `dreaming.py`, `dream_incremental.py`, `dream_sources.py`, `dream_catalog.py`, `dream_records.py`, `dream_views.py`, `dream_transport.py`, `dream_gateway.py`, `dream_cli.py`, `issues.py`.
- WP3 Lifecycle: `core.py`, `recall.py`, `curation.py`, `maintenance.py`, `context_packet.py`, `owner_checks.py`.
- WP4 Extraction and Deck-ready: new `extract.py`, `adapters.py`, `configuration.py`, `scripts/install-local.py`.
Tests follow the same split (`tests/test_*` by module). WP2–WP4 start after WP1 publishes the new names; WP2 and WP3 may run concurrently; WP4 after WP3's caller fields.

**D13. Status search is fail-closed.** The v0.3 status-filtered `search` replaces the old audit but sees only records visible to the caller's worktree and task, excludes shared imports and keeps Dreaming source-use restrictions hidden rather than flagged. A cross-worktree audit would need an explicit lead grant, which this change does not add.

## Risks / Trade-offs

- [Rename breaks every connected client] → No aliases by user decision; README and skill state the reconnect requirement; Pi exposure list and WebCodex redeploy are external follow-ups listed in the proposal.
- [Derived keys collapse identical payloads from one session] → Reported derived key lets the caller see the replay; different content never collapses.
- [Target-keyed baseline hides material a new question would re-read] → Explicit `reread` ranges and inventory listing of reviewed positions.
- [Accepted gaps become a way to skip work] → Gaps need reason and note, persist in checkpoints, surface in inventories and views; they never count as reviewed content.
- [Extraction cost or quota] → ≤2 sessions per startup, 200 KB windows, journal with tokens/time, hard stop on provider failure, no fallback model; live qualification is a separate user-authorized task.
- [Extraction candidates flood the store] → Never in default recall; stale after 7 days; Dreaming default objective triages them; replay on unchanged transcript.
- [Clearing run text loses re-reading ability] → Only after receipts are sealed; identities and digests remain, original transcripts are the source of truth (user decision 8A).
- [Claude session identity instability] → Locators use transcript paths; the reader records parent links between session files; `live_correction` keeps its fields but documents the transcript locator.
- [Working-tree edits in `dream_sources.py` collide with WP2] → WP2 owns that file and starts from the current working tree, not HEAD.

## Migration Plan

1. WP1 merges; fresh MCP processes serve v0.3 names; connected clients must reconnect (documented).
2. Operator updates Pi `toolExposure` names and redeploys WebCodex (external, user).
3. WP2/WP3 merge; no store migration: stale status, assurance and effective status are derived; existing checkpoints keyed by objective are read once and re-keyed by target on first `dream_start` per target, retaining accepted-gap-free positions.
4. WP4 merges with extraction disabled by default; operator enables it in store configuration with the chosen model; installer apply for SubagentStart and extraction spawn hooks is a separate authorized step.
5. Rollback: revert the package; derived fields disappear without data loss. Records written by callers that declared lineage (`provenance.role/model/parent_session_id`) carry extra provenance keys that the 0.2 strict validator rejects, so a rollback to 0.2 must either keep the relaxed validator or quarantine those records; this is accepted because no compatibility is required.

## Open Questions

- Claude transcripts discovered through history roots carry no selected leaf, so every Claude file reports `active_branch_unverified` and must be accepted as a gap or given a leaf selection before its messages become publication evidence. Pi defaults to the saved resume branch; whether Claude should default to the last message of the file is a contract decision for the user (it would modify the "unselected Claude is navigation only" requirement).

- Whether HarnessDeck will pass `effort` and `model` for workers through the CLI entrypoint or through an injected caller; either fits the caller schema and can be decided when Deck's spawn path exists.
- Exact window size for extraction input (200 KB proposed) may be tuned after the first authorized live qualification without changing the contract.
