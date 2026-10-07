# Harness-neutral Dreaming operations and qualification boundaries

This is source implementation, not a deployment. The ordinary nine-tool MCP server is unchanged. No existing installation, shared native harness configuration, live memory records or research owner files are changed by these instructions being present.

## Reproduce the disposable delivery example

From this checkout, with Python >=3.11 and the existing test dependencies:

```sh
PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python scripts/dreaming-fixture-demo.py \
  --output outputs/my-new-dreaming-example
```

The output must be new or empty. The command creates only a temporary synthetic store and the selected output directory. It never reads configured production memory or native histories. It emits:

- `candidate-diff.json`, the actual frozen draft returned by the implementation; `draft-input.json` and `materials.json` bind it to its input.
- `source-manifest.json` and archived synthetic source bytes, because original temporary source paths intentionally disappear when the example ends.
- `publication.json`, both views before withdrawal, default/historical research views after withdrawal, the closed Run and a receipt.

The example publishes A, rejects a risky B, independently publishes collaboration, then withdraws A through ordinary CRUD. The old research view becomes unavailable for default and historical reads; collaboration remains usable. Neither executor identities nor claims in this example are real Pein session evidence. Do not replay its IDs against another store.

## Trusted operator setup

The store must already be explicitly initialized and registered through the existing `init`/`register` CLI. A Dreaming profile uses **memory registry IDs**. Resolve the actual executor project and permitted target projects separately. The operator supplies `dreaming/policy.json` through the CAS-guarded `dream configure` command. Policy configuration remains outside the Agent-facing endpoint; discovery, target/material selection and Run lifecycle are available within the installed grant. Any authorized Agent can perform Dreaming regardless of harness or model.

A policy has version 2, subject `Pein`, a central `collaboration_projects` list and a `profiles` mapping. Each profile contains:

```json
{
  "target_projects": ["actual-registered-target"],
  "executor_projects": ["actual-registered-executor", "actual-registered-target"],
  "source_grants": [{"id": "owner", "kind": "file", "path": "/approved/owner.md", "format": "document", "schema": "document-v1"}],
  "actions": ["record_create", "record_approve", "record_supersede", "record_withdraw", "collaboration_create", "collaboration_publish", "collaboration_withdraw", "view_publish"],
  "provider": "operator-selected-channel",
  "transport": "operator-selected-transport",
  "budgets": {"source_bytes": 262144, "events": 64, "operations": 16, "drafts": 3,
              "view_chars": 2400, "view_bytes": 9600, "model_calls": 0,
              "input_tokens": 0, "output_tokens": 0, "seconds": 3600, "repair_rounds": 2},
  "scenarios": ["general", "research", "engineering", "acceptance"],
  "allow_inferred": true
}
```

This is a profile fragment, not an installed policy. Replace placeholders only from current authorization. Zero model budgets are appropriate for fixtures; a real externally launched Dreamer needs independently authorized provider/token/cost limits and launcher enforcement. The core never invokes a model and cannot enforce usage by another process. `model_calls` in a Run counts core calls, not external harness usage. Policy configuration is explicit: pass `--expected-revision absent` initially, or the exact prior revision when replacing it. Profile/source/caller strings and review prose are not authentication credentials.

Use `kind=directory` to grant discovery beneath one explicit root, with the public format/schema and native version selected by the operator. A selector refers to a grant and relative path, optionally a branch or returned page selection. Grants do not confer permission to escape through symlinks or traversal. The unreleased version-1 Dreaming policy is replaced explicitly; ordinary version-1 memory records and sealed historical qualification receipts remain intact.

## Manual start, inspect, review and publication

The source checkout supports `PYTHONPATH=src python -m shared_memory_mcp.cli` without installing it. Below, `sm` denotes that command or an explicitly selected installed `shared-memory` entrypoint. Set the values from the trusted launcher's actual caller and approved profile; do not substitute the target cwd for the executor cwd.

```sh
BIND=(--profile "$PROFILE" --cwd "$ACTUAL_CWD" --harness "$ACTUAL_HARNESS" \
      --session-id "$ACTUAL_SESSION_ID" --actor "$ACTUAL_ACTOR")

sm --root "$MEMORY_ROOT" dream configure --expected-revision absent < approved-policy.json
sm --root "$MEMORY_ROOT" dream catalog "${BIND[@]}" --limit 50
sm --root "$MEMORY_ROOT" dream audit "${BIND[@]}" --target-project "$TARGET_PROJECT" --filters-stdin < audit-filters.json
sm --root "$MEMORY_ROOT" dream source-list "${BIND[@]}" --grant-id "$SOURCE_GRANT_ID" --limit 50
sm --root "$MEMORY_ROOT" dream source-read "${BIND[@]}" < source-selection.json
# Put the returned selection into the sources array of run-selection.json.
sm --root "$MEMORY_ROOT" dream start "${BIND[@]}" --selectors-stdin < run-selection.json
# Read run_id and generation from this result, not from a prior example.
sm --root "$MEMORY_ROOT" dream inspect "${BIND[@]}" --run-id "$RUN_ID"
sm --root "$MEMORY_ROOT" dream materials "${BIND[@]}" --run-id "$RUN_ID" --source-id "$SOURCE_ID"
sm --root "$MEMORY_ROOT" dream freeze "${BIND[@]}" --run-id "$RUN_ID" --generation "$GENERATION" < operations.json
# Read draft_revision from the freeze result.
sm --root "$MEMORY_ROOT" dream diff "${BIND[@]}" --run-id "$RUN_ID" --revision "$DRAFT_REVISION"
sm --root "$MEMORY_ROOT" dream publish "${BIND[@]}" --run-id "$RUN_ID" --generation "$GENERATION" --revision "$DRAFT_REVISION"
sm --root "$MEMORY_ROOT" dream mark "${BIND[@]}" --run-id "$RUN_ID" --generation "$GENERATION" < event-statuses.json
sm --root "$MEMORY_ROOT" dream overview "${BIND[@]}" --target-project "$TARGET_PROJECT" --view research --scenario research --max-chars 2400
sm --root "$MEMORY_ROOT" dream close "${BIND[@]}" --run-id "$RUN_ID" --generation "$GENERATION"
```

`audit-filters.json` may be `{}` or contain `collection` (`research` or `collaboration`), `ids`, `query`, `statuses`, `scopes`, `cursor`, `limit` and `max_chars`. `source-selection.json` identifies a grant, for example `{"grant_id":"owner"}` for the file grant above or `{"grant_id":"history","path":"relative/session.jsonl","leaf_id":"selected-leaf"}` for a branch-aware directory grant. `run-selection.json` has `target_project` and `sources`, where `sources` contains returned page selections unchanged. The source page identifies `source_id` for the materials command. Catalog/list continuation uses `--cursor`; source-read continuation uses the original source selection plus the returned `--cursor`, while audit continuation is supplied in the filter JSON. Enumerate the permitted target projects and audit each selected collection explicitly for global consolidation.

`operations.json` is an array using the structure in the disposable example. Claims contain topic, text, level, conditions, exceptions, counterevidence, scenarios, projects, refs and risks. Reviews contain decision, reason, scope_checked, counterexamples_checked and checked_refs; the authorized Agent may perform that review. Source refs come from the exact frozen materials; `op:A` can refer to another operation in the same draft. Only create operations accept candidate visibility. A later publication of inferred collaboration must cite the unchanged candidate and retain `inferred`.

Record creation defaults to project scope; explicit `qualifier` selects a registered worktree or task. Approval/withdrawal preserve the existing record's qualifier, and every predecessor in a supersession must have the same qualifier. The executor cwd stays real even when the effect belongs to another authorized project/worktree. A cross-scope synthesis is a new sourced claim, not a fabricated same-scope supersession.

Every `record_approve` operation must include `record_id` and the exact `expected_content_digest` returned by audit, plus its reviewed claim and review. This also approves ordinary `propose`/`capture` candidates with arbitrary Markdown: the original body, kind, title, sources and provenance are preserved. Each original source URI and any locator must match authorized frozen evidence in `review.checked_refs`; the claim expresses the review and does not replace the candidate. Changed content, retirement, no-reuse or unverifiable original sources blocks approval.

`event-statuses.json` maps frozen event keys to `processed`, `excluded`, `no-signal` or `pending-review`. Missing processing states remain incomplete coverage. A successful process exit is not complete history or scientific validation. CLI publication returns exit 3 for `partial`/`blocked`, exit 2 for rejected input/operation errors and exit 0 for successful observations/effects. Always inspect the structured result.

## Continuation and conflicts

First inspect the exact Run. A nonclosed active Run makes `start` for the same target/source selection return `resume-required`, never a second worker. Other authorized target/source selections have separate lanes. To continue from another **actual** caller, bind that caller in `BIND`, then explicitly run:

```sh
sm --root "$MEMORY_ROOT" dream takeover "${BIND[@]}" --run-id "$RUN_ID" --generation "$OLD_GENERATION"
# Use the returned new generation; retain the same frozen draft revision.
sm --root "$MEMORY_ROOT" dream publish "${BIND[@]}" --run-id "$RUN_ID" --generation "$NEW_GENERATION" --revision "$DRAFT_REVISION"
```

Completed effects retain the original executor; unfinished effects use the new executor. Old generations are rejected. A namespace, source, curation, predecessor, policy or disposition conflict needs explicit local semantic review, not a blind retry. A replacement `freeze` requires `--reconsider-reason` while unresolved operations remain. Draft and repair budgets bound this process. Source grant changes require fresh authorized material; old excerpts cannot be reused merely by refreezing a draft.

`close --abandon-reason 'specific reason'` permits explicit partial closure for rejected operations or proven no-effect intents. An unactivated immutable view revision is not visible context. Visible/ambiguous canonical effects must be reconciled rather than abandoned. No command restores a whole store or revives superseded predecessors. If publication happened before its receipt, inspect and replay the exact operation: canonical effect evidence, not content similarity, resolves it.

If another writer normally promotes a just-created candidate before its receipt exists, replay can acknowledge the original creation from its unchanged proposal binding, content and provenance. It preserves the external review and publisher. Subsequent operations remain blocked by the external namespace change until a reviewed replacement draft or explicit partial close; acknowledgement does not adopt unrelated changes as already reviewed.

## General and fixed-Run MCP endpoints

The general Agent-facing endpoint binds the actual caller, profile and publication grant while leaving target/material/batch selection to the Agent:

```sh
sm --root "$MEMORY_ROOT" dream serve "${BIND[@]}" --enable-publisher
```

It exposes authorized catalog/source discovery, public source-page reading, full retained-memory audit and the Run lifecycle. The Agent can select a permitted target and material, start, inspect, draft, publish and close a batch without another operator per batch. Omitting `--enable-publisher` permits inspection/drafting only. Neither mode exposes policy reconfiguration, caller rebinding or arbitrary shell tools. Ordinary memory's nine tools remain unchanged.

The general tools are `dream_catalog`, `memory_audit`, `source_list`, `source_read`, `run_start`, `run_observe`, `run_takeover`, `run_materials`, `draft_submit`, `draft_read`, `coverage_mark`, `run_close`, `overview_read` and `issue_suggest`. Publication-enabled endpoints additionally expose `draft_publish`. Run operations carry explicit Run/generation identifiers where applicable. Catalog pagination returns current authorized active lanes; a policy or lane revision change invalidates continuation.

Full audit includes retained inactive and worktree/task records with lifecycle/curation provenance and explicit usability restrictions. It is not ordinary recall: a withdrawn or no-reuse item remains unavailable as active evidence. Paginated audit binds its revision and filters; stale continuation is rejected. Oversized items have explicit reconstructable JSON slices rather than silently omitted fields.

New collaboration records retain compact source bindings, so source-ID, URI and lineage prohibitions also appear in their audit usability. Older direct-event collaboration without those bindings returns `source_binding_unknown` and remains inspectable but unusable. `usable=true` means no detected canonical restriction; it is not source verification or semantic certification.

For optional restricted delegation, a trusted launcher may fix a Run and generation:

```sh
sm --root "$MEMORY_ROOT" dream serve "${BIND[@]}" --run-id "$RUN_ID" --generation "$GENERATION"
```

The fixed-Run mode is advisory by default. Its readonly tools are `run_observe`, `source_read`, `memory_read`, `draft_read`, `overview_read`; its bounded mutations are `draft_submit`, `coverage_mark`, `issue_suggest`. Explicit launcher `--enable-publisher` adds `draft_publish`. It hides target/profile/caller/Run selection, raw CRUD, shell and takeover. Extra arguments fail validation. This is an **endpoint restriction**, not an OS sandbox or a claim about a native harness's other tools. The general consolidator intentionally has a broader lifecycle surface; that does not weaken fixed-Run delegation.

## Work-session consumption

Ordinary empty-query `context` remains navigation-only. Optional `context` and Codex/Claude `hook` accept `--dream-profile PROFILE --dream-scenario general`. The actual consuming cwd must resolve to that profile's target. Missing, stale, revoked or unavailable collaboration adds no claims and never starts a Dreamer. Task-specific research content uses the explicit `dream overview` entrypoint.

Pi's existing `createSharedMemoryExtension` additionally accepts `dreamProfile` and `dreamScenario`; options are forwarded at existing startup/resume/compact/identity boundaries. Ordinary growth retains the stable prefix. Defaults do not opt in. No shared adapter configuration was installed in this change.

Revocation applies on the next actual read or supported lifecycle refresh, not by erasing old model context. There is no new per-turn invalidation hook. A consequential revocation can require a fresh native session.

## Source windows and identity

Codex requires `codex-rollout-v1` plus an explicit native version; Pi requires `pi-session-v3` and an explicit selected leaf for usable branch evidence; Claude requires `claude-jsonl-v1`, an explicit native version and a selected leaf for usable branch evidence. These are the implemented public projections, not a promise to parse every historical version. Unknown schemas, corrupt/oversized/incomplete events and missing branch ancestry are gaps. No native session loader is called. System/developer, thinking and full tool payloads are excluded; a small secret-pattern filter is not a general DLP guarantee. Source grants and the model/provider data boundary still need operator review.

Codex pins the first header's file owner. A subsequent embedded header produces `inherited_session_metadata` and conservatively marks following input as delegated/unknown; the parser does not guess where inherited history ends. Claude requires the full selected ancestor chain in the current public event window; missing, cyclic or conflicting ancestry yields a gap with no selected events. Without a Claude leaf, public navigation is available but publication rejects it as `unverified_branch`.

The original exact-file prefix reader caps one consumed window at 8 MiB and 1,024 identities, with 64 KiB line allocation. General catalog paging separately traverses longer histories with bounded pages and server-validated continuation; it does not assert that an entire conversation fits one Run. A paging pass fixes the source file epoch; edits/appends invalidate that pass instead of mixing states. Selected page snapshots are revalidated before publication. Missing branch ancestry remains a gap, and native files are never rewritten into exports automatically.

Source pages accept 65,537–8,388,608 bytes and 1–1,024 events per call (defaults 262,144 bytes/128 events). The per-profile catalog retains at most 512 opaque handles, bounded per-page parser state, and a disk-backed identity digest index for retained paging passes; old handles may expire. It stores no transcript text. Selected Runs retain compact page descriptors and reconstruct from the original source, so handle eviction alone does not discard their evidence. Exact input-cursor retries return the same page while that handle and source epoch remain valid. A source append does not by itself revoke already published memory, but it makes an old page invalid for new publication.

A Run caps public working events at 128, selected sources at 16, drafts at 8, operations per draft at 32 and source read/verification budget at 16 MiB. Prefix verification for exact-file backfill is charged. Incremental batches preserve known gaps; unavailable verification produces a gap/blocked result, never unchecked `no-change`. Branch ancestry outside the selected working set remains partial; another branch is not silently claimed as the actual trajectory.

`role=user` is not Pein attribution. Only exact raw-event SHA256 attestations in trusted policy can confirm a qualifying original user expression; delegated/sidechain/RPC expressions stay unknown. Attestations cannot be supplied through Dreamer tools. Repeated/derived reports do not acquire independent evidence status. Record/source IDs are not authentication tokens.

URI-level no-use also applies to untagged existing records under default and historical reads. Equivalent local `file:///`, `file://localhost/` and percent-encoded paths match on both sides of the disposition comparison; remote file hosts remain distinct. Canonical records and the original disposition journal are preserved byte-for-byte.

## Harness capability matrix for this implementation

| Dimension | Codex | Pi | Claude |
|---|---|---|---|
| Versioned public-history reader | CPU fixtures, first-header owner | CPU fixtures, bounded explicit branch | CPU fixtures, verified bounded selected ancestry |
| Dedicated CLI/MCP with that caller label | Actual stdio process/client fixtures | Actual stdio process/client fixtures | Actual stdio process/client fixtures |
| Optional working-session consumer | Hook envelope + actual core fixture | Installed SDK loader/session dispatch; fixture CLI transport; profile/scenario forwarding | Hook envelope + actual core fixture |
| Native independent Dreamer/model session | Not run | Not run | Not run |
| Verified native executor identity | Not implemented; operator-bound | Not implemented; operator-bound | Not implemented; operator-bound |
| Entire native tool-pool enforcement | Not qualified | Not qualified | Not qualified |
| OS isolation | Not provided | Not provided | Not provided |
| Paid smoke / real memory pilot / semantic comparison | Not run | Not run | Not run |

A different caller label in a real stdio subprocess tests the bound transport contract, not a real Codex/Pi/Claude model session. Source existence and machine admission checks do not prove semantic entailment. The source implementation and measured fixture paths are deliverable; production acceptance remains separately gated by the attached proposal.
