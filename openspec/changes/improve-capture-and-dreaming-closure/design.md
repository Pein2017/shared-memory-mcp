## Context

See [proposal.md](proposal.md) for the bounded audit motivation. The source baseline was `3e963865cc1aa9c8edad9f67ef9e3f547095eccd` in `/data/CoordExp/codex-tools/shared-memory-mcp`. The candidate was developed in `/data/CoordExp/codex-tools/.worktrees/shared-memory-capture-curation`, branch `codex/memory-capture-curation`, and subsequently integrated and cleaned up as recorded below.

The existing core already supports reviewed capture, hidden candidates, exact-scope successors, logical withdrawal, ordinary retirement, manual DreamRuns and compact context. `dream_records.py` admits unchanged candidate approval, same-qualifier supersession and withdrawal; retirement is absent from its action set. The task's reported omissions and backlog do not establish a missing storage abstraction. Historical source-read friction is not evidence that the current bounded event/ancestry decoder needs changing.

The canonical checkout is also a live dependency: the shared-memory venv's `direct_url.json` and editable `.pth` resolve its `src`, Codex's `shared-memory` skill link resolves its bundled skill, and `.shared-memory/.state/adapters/shared-memory.ts` imports its Pi adapter. Source edits there can activate on a new consumer without an installer invocation. Initial authorization covered candidate development and this OpenSpec change. The user subsequently authorized integration and temporary-worktree cleanup on 2026-10-11; a production Dreaming batch remains separately requested.

## Goals / Non-Goals

**Goals:** complete task-local capture and manually requested consolidation through existing owners, preserve unresolved evidence and incompatible conditions, and make empty-mode browsing usable through the public caller.

**Non-Goals:** no transcript extractor, scheduler, new candidate queue/schema, semantic similarity algorithm, retirement action, source permission expansion, policy migration, research-owner edits or production memory writes. Improve guidance without asserting that prompt edits guarantee future capture quality.

## Decisions

### Meaningful evidence transitions drive capture

Add a short decision rule to the existing skill. The owning Agent checks relevant memory and captures durable accepted lessons/corrections while original evidence is available, before closeout when warranted. Routine owner edits and elapsed time do not imply a record. Reuse existing `details.conditions` or body for candidate gap/revisit information; a newly relevant task or resolved gap motivates reconsideration. This avoids both waiting for a curator and converting every task into a changelog.

### Consolidation uses existing lifecycle distinctions

Extend the existing operations reference rather than adding an instruction framework. A requested run selects an objective and source cutoff, inspects relevant candidates and issues through bounded audit, and checks missing/stale/duplicate/conflicting knowledge against granted owners.

- Unchanged candidate plus sufficient original-source review: approve exact audited content.
- Changed proposition: retain the candidate disposition and create separately reviewed knowledge; do not pretend the rewrite is approval. Candidate predecessors cannot be used in the active-only Dreaming supersession path.
- Compatible active duplicates at the same qualifier: reviewed successor preserving necessary sources and conditions.
- Different checkpoints, populations, versions or conditions: coexist unless evidence establishes replacement; unresolved contradictions retain their gap.
- Withdrawal: justified rejection/no-use, not a synonym for obsolete relevance. Retirement absent from current run actions: report the need, without substituting withdrawal or using ordinary CRUD to bypass the run policy.

An issue is resolved after its requested owner correction/conclusion is verified. Publication alone does not resolve it. A source failure blocks dependent claims; supported exact continuation precedes an oversized-source conclusion, with denial, sensitive-content restrictions and unresolved ancestry preserved.

### Readback qualifies consumer usefulness

Publish a reviewed compact navigable account when relevant, keeping decision-changing qualifiers and as-of/source references attached. Verify ordinary target `context` and targeted `search/read`; audit visibility is not default recall. The observed 1,612-character packet fit is not a universal character threshold: the serialized consumer budget governs. Do not insert unsupported candidate assertions into an active view or relabel stale state as current.

Stop after bounded dispositions, effects reconciliation and readback, reporting remaining scope/coverage/consumer gaps. Counts of records, views or closed runs are not the success metric.

### Empty query is browsing

`recall.rank` normalizes an empty/whitespace query and returns deterministic alphabetical records without lexical `match`. `recall.search` currently assumes a score whenever `task_mode` is present. Bypass only its lexical boost/sort for a normalized-empty query. Do not fabricate matches, change nonempty ranking, eligibility, explicit restrictions or the corpus fence. The shared core fix reaches CLI/MCP and history callers without changing their schemas.

### Task-driven reading has no cumulative workflow quota

In the 2026-10-11 reading follow-up, the user selected no cumulative reading quota while retaining per-batch and backend protections. Reuse the existing skill, operations reference and shared `WORKFLOW_REMINDER`; no new reader, queue, automatic loop or changed API limits are needed. The reminder reaches MCP initialization and composed CLI/native context; detailed continuation mechanics remain in the existing operations reference.

Read successive relevant batches until the task's required evidence, decisive conditions and counterevidence are understood, or expose the remaining concrete access/version/structure gap. Record/session/source/page/round counts are not stopping criteria. A declared full-scope review needs traversal of that authorized selection; an ordinary task need not exhaust unrelated history. Existing backend corpus-limit errors remain explicit blocked reads, not partial successes.

Context supplies selected claims and read pointers, not a complete cursor over omitted knowledge. Do not repeatedly issue the same context request to advance. Search uses the returned offset and corpus revision; detail reads reassemble revision-fenced JSON fragments and retry omitted IDs in smaller batches; memory audits and source readers use their own exact cursors. Frozen source selections belong to review provenance, not a made-up pagination cursor. Keep conditions/related counterevidence together and never use first-page ranking or a preview as completeness evidence. This guidance changes model instructions, not deterministic reader eligibility or source permissions.

### Advisor ruling and lead adoption

One read-only `ask-advisor` consultation with `gpt-6-astra`, high effort, on 2026-10-11 recommended the above minimal candidate. The advisor inspected code and current editable bindings; it did not re-audit the historical corpus or run a model/Dreaming experiment.

The lead adopts the recommendation after checking the load-bearing source distinction (`rank`/mode sort, original-payload approval, exact qualifiers and current actions) and reproducing the empty-mode failure through core and official MCP stdio. The strongest alternative, instructions only, leaves the public recall error. A new queue/scheduler/action becomes justified only by repeated bounded evidence of workflow failure or a concrete safe operation that the existing lifecycle cannot express. Instruction efficacy and live consumer improvement remain unmeasured here.

### Trigger recommendation is advisory

Capture at accepted durable evidence/corrections. Revisit a candidate when its evidence gap becomes actionable or a relevant task needs it. During an explicitly requested Dreaming round, prioritize relevant pending review, owner changes affecting current claims, duplicates/conflicts and recall gaps. Source drift alone prompts foreground current-owner checking; it does not automatically launch Dreaming. No daily hour, candidate threshold or batching interval is installed. If the user later wants scheduling, choose a bounded incremental cadence from observed backlog and benefit, under separate scheduling authority.

## Risks / Trade-offs

- Guidance can be ignored or overcapture routine state → narrow evidence-transition rule and later bounded outcome assessment; isolated tests establish lifecycle behavior, not model compliance.
- Merging hides incompatible observations → retain conditions and unresolved conflicts, use exact-scope successors only when evidence supports replacement.
- A compact view looks fresh or omits a decisive caveat → test actual ordinary delivery and disclose freshness/coverage; retain whole qualified units or read routes.
- Editing the canonical linked checkout deploys implicitly → keep all candidate files isolated and test with explicit candidate imports and disposable stores.

## Migration Plan

1. Prepare and validate the source/skill/OpenSpec candidate only. Preserve the canonical source, live links, configuration and store; do not commit or integrate without corresponding authority.
2. After explicit live adoption authorization, recheck canonical HEAD/dirty state and linked consumers, then adopt the reviewed exact candidate. Treat materialization into the editable source checkout as deployment; no link change is required by this design.
3. Qualify fresh real web-pi/Codex consumers for empty-mode search and current skill discovery. Preserve existing sessions rather than forcibly restarting another Agent. Do not infer activation from source tests.
4. Run the user's separately requested bounded Dreaming review under then-current grants. Assess omitted findings, candidate dispositions, conditional coexistence, view usefulness and issue closure at their original owners.
5. A deployment rollback restores only the owned adopted source/instruction changes. Production memory effects, if later authorized, require their own exact lifecycle/recovery handling; source rollback must not rewind the store or revive predecessors.

## Candidate Validation

Validated on 2026-10-11 in the isolated checkout with explicit candidate `PYTHONPATH` and disposable fixture stores. The existing Python environment supplies pytest and the official MCP SDK; it was not reinstalled or repointed.

- Before the core edit, the five new empty-mode cases failed: four core cases raised `KeyError('match')` and the official MCP stdio caller returned the corresponding tool error. After the one-branch guard fix, all five passed (2.04 s).
- The focused combined run passed 71 tests (8.92 s, exit 0): `test_recall_curation.py`, `test_recall_boundaries.py`, `test_context_modes_budgets.py`, `test_context_final_budget.py`, `test_dream_general.py`, and the candidate-to-view isolation case from `test_dreaming.py`. These exercise nonempty recall, hidden candidates, explicit mode restriction, revision-fenced browsing, unchanged candidate payload approval, exact-scope multi-predecessor supersession, counterevidence/compact delivery and source restrictions.
- Skill-creator `quick_validate.py skills/shared-memory` passed; OpenSpec strict validation and the owned whitespace diff check passed. Guidance cases were inspected against current lifecycle actions and eligibility; no extra instruction-efficacy model evaluation was run.
- At candidate validation, the canonical checkout remained clean at baseline HEAD; its editable package metadata/import, Codex skill link and Pi wrapper continued to resolve canonical paths. The source/instruction files and planning artifacts were then isolated and uncommitted.

This qualifies the source candidate and existing lifecycle invariants. It does not prove model compliance with the new instructions, improved production capture/consolidation, fresh native-client behavior or complete historical coverage. Tasks 3.1 and 3.2 retain the remaining native-consumer qualification and separate Dreaming assessment.

### Progressive reading follow-up (2026-10-11)

The reminder, skill and operations reference were checked against retained APIs. `context.continuation` is one read hint; it does not page all omissions. Search advances with `next_offset` and `expected_revision=corpus_revision`. `read` and `overview_read` share revision-fenced detail fragments and `next_page`; only `read` separately returns `omitted_ids`. `memory_audit` returns a cursor bound to selection/revision and exact JSON-slice offsets. `source_read` continues the original grant/path selection with `next_cursor`; each returned frozen selection/page is provenance. The corrected detail row retains the real `read`/`overview_read` selectors and projection flags.

- `env PYTHONPATH=/data/CoordExp/codex-tools/shared-memory-mcp/src /data/CoordExp/.shared-memory/.venv/bin/python -B -m pytest -q -p no:cacheprovider tests/test_recall_curation.py::test_pagination_is_bounded_and_revision_fenced tests/test_unified_entrypoint.py tests/test_dream_catalog.py::test_supported_history_continues_beyond_eight_mib_and_1024_ids tests/test_dream_catalog.py::test_read_cursor_replays_exact_page_after_lost_response tests/test_dream_catalog.py::test_frozen_page_epoch_rejects_mutation_for_cursor_and_publication tests/test_context_modes_budgets.py tests/test_context_final_budget.py` — 22 passed (pytest 4.66 s; wall 5.208 s; exit 0). Fixtures use disposable temporary stores.
- `/data/CoordExp/.shared-memory/.venv/bin/python -B /data/CoordExp/.codex/skills/.system/skill-creator/scripts/quick_validate.py /data/CoordExp/codex-tools/shared-memory-mcp/skills/shared-memory` — valid (0.050 s; exit 0).
- `openspec validate improve-capture-and-dreaming-closure --strict` — valid (3.566 s; exit 0). `git diff --check -- src/shared_memory_mcp/core.py skills/shared-memory/SKILL.md skills/shared-memory/references/operations.md openspec/changes/improve-capture-and-dreaming-closure/proposal.md openspec/changes/improve-capture-and-dreaming-closure/design.md openspec/changes/improve-capture-and-dreaming-closure/tasks.md openspec/changes/improve-capture-and-dreaming-closure/specs/shared-memory-recall/spec.md` — clean (0.004 s; exit 0).
- The reminder's common serializer remains subject to its existing combined byte budget; selected context budget and final-packet tests passed above. Deterministic checks establish retained protocol behavior, not instruction compliance by a model.
- Separate lead-owned fresh CLI check: `/data/CoordExp/.shared-memory/.venv/bin/shared-memory --root /data/CoordExp/.shared-memory call --tool context`, followed by the same command with `--tool search`, via `/data/CoordExp/.shared-memory/.venv/bin/python - <<'PY'`. With `PYTHONPATH` removed, cwd `/data/CoordExp`, and the actual root Codex caller, exit 0 (elapsed not measured). The current reminder was delivered in 7,920/7,923-byte packets; a `limit=1` search continued with its returned `next_offset` and `corpus_revision` as `expected_revision`, yielding two distinct pages from 17 matches. This is fresh CLI consumption, not native Pi/Codex MCP injection or model-compliance evidence.

### Authorized reinstall qualification (2026-10-11)

The user authorized reinstalling into Codex and Web-Pi. The live Web-Pi processes use `/data/CoordExp/.pi`; the Codex configuration root is `/data/CoordExp/.codex`.

- Offline editable reinstall in `/data/CoordExp/.shared-memory/.venv` with `python -m pip install --no-index --no-deps --no-build-isolation -e '.[mcp,test]'` succeeded (exit 0). Import and package metadata resolve the canonical checkout; no dependency upgrade was requested.
- `scripts/install-local.py` with the existing root/CLI/Codex/Pi paths and cwd `/data/CoordExp` passed plan and `--apply` (exit 0). All four configuration files were byte-identical to their private backups at `/data/CoordExp/.shared-memory/.state/config-backups/20261011T032325Z-50fad505`. The native Codex hook is enabled and trusted; the shared skill symlink and registered Pi wrapper resolve the current source. Claude was not selected.
- Installed `doctor` returned `status=ok`, `scan_bound=10000`, 208 CoordExp records and two shared-memory-mcp records. A fresh installed CLI stdio MCP process exposed 27 tools and delivered the current progressive-reading reminder through both initialize and ordinary context, using the actual root Codex caller (exit 0). The current Codex MCP connection also returned successful empty-query searches in both modes, with empty match metadata.
- `env PYTHONDONTWRITEBYTECODE=1 /data/CoordExp/.shared-memory/.venv/bin/python -B -m pytest -q -p no:cacheprovider tests/test_pi_installed_adapter.py` passed both installed/native transport cases (2 passed, 12.08 s, exit 0). These exercise the installed Pi SDK and adapter against disposable stores, without provider calls or persistent Web-Pi session proof.

No live Web-Pi service was restarted and no production Dreaming run was started. Current Dreaming discovery reports an eligible publisher and no active runs. Existing Pi sessions may retain their loaded modules. Task 3.1 remains open for the retained fresh native Web-Pi search/skill-discovery boundary; instruction compliance and memory quality still require the separately requested Dreaming assessment in task 3.2.

### Authorized WebCodex refresh (2026-10-11)

The user separately authorized refreshing WebCodex. Its existing Runner provider and Skill roots already resolve the shared installation and canonical Skill. Before refresh, the public WebCodex gateway returned the old reminder and both empty-query modes failed with `'match'`; a current Skill load already contained the progressive-reading rule. Unchanged provider configuration retains its live connection, so another identical install/config reload would not refresh that process.

- The selected provider was idle and the current Dreaming catalog had no active runs. Its exact argv, cwd, parent Runner and process start time were checked. The first pidfd-based attempt stopped before sending a signal because this Python build lacks those bindings. After repeating identity/idle checks, standard SIGTERM stopped only the old provider PID 756088; passive gateway status then reported `connection_retired`.
- An explicit WebCodex gateway tools/list established one new provider, PID 2033998, under the unchanged Runner PID 751091. The Server/Runner and five observed Codex/Pi MCP processes retained their original PID/start-time identities. No configuration was edited and no Server/Runner restart occurred.
- The refreshed gateway exposed 27 tools, including Dreaming discovery/start/publish/close. Ordinary context delivered the current reminder in a 5,522-byte packet with the actual root Codex caller forwarded unchanged. Empty and whitespace search in both modes all passed (four checks, empty match metadata), replacing the reproduced old-process failure.
- Live WebCodex `skill_load(project="coordexp", name="shared-memory")` returned the current complete definition, revision `2138154141dc755061b6415a1b620610c6eff17d2240b11dbdba022453cb9d72`. Provider status is `healthy`, the same Runner instance remains online with zero active jobs, and installed doctor still returns `status=ok` with the same 210 records.

This qualifies refreshed WebCodex gateway/Skill consumption, without inventing a WebCodex Workflow Session or caller identity. No production Dreaming or model-compliance assessment was run. The separate native Web-Pi consumer boundary and Dreaming assessment remain open.

## Authorized Integration and Cleanup

On 2026-10-11, the user authorized merging the candidate and cleaning its temporary worktree. Exact owned paths were committed as `eae7334e4c746499bc7471f2233511278b0faeac` and fast-forwarded into canonical `main`. The clean, fully merged temporary worktree and its branch were removed after checking for active cwd/file holders. No package reinstall, link/config change, service reload, push or Dreaming run was performed.

A fresh existing installed CLI bridge, with candidate `PYTHONPATH` removed and the actual registered Codex caller context, successfully returned ordinary empty and whitespace search results in both task modes; all four checks preserved empty lexical matches. Package import and the Codex skill link still resolve the canonical checkout. This confirms new-process CLI consumption, not fresh native web-pi/Codex tool injection or skill discovery. Existing MCP processes can retain imported modules until reconnecting; task 3.1 remains open for that consumer boundary.

## Cross-Harness Comparison (Advisory)

Read-only comparison used `/data/CoordExp/external/harness/codex` at HEAD `4c43465133428898aa84f0bfc02c306ed65fb66a`, preserving unrelated dirty work. These recommendations do not add requirements or authorize another implementation batch. Automatic startup is outside the requested comparison.

- **Minimum signal:** `codex-rs/memories/write/templates/memories/stage_one_system.md:29` asks whether a future Agent will act better and permits empty extraction for routine status, transient facts and unchanged behavior. Shared-memory's evidence-transition rule covers much of this; an explicit no-new-knowledge disposition would make the rubric clearer without a new schema.
- **Outcome and useful failure:** the same template at line 153 distinguishes success, partial, fail and uncertain; original user corrections and tool validation outrank assistant claims. Reuse existing claim content, conditions and source review for the bounded outcome, uncertainty, failure shield and revisit trigger. Do not copy the heuristic that moving to another task establishes scientific acceptance.
- **Consolidation and retrieval wording:** `templates/memories/consolidation.md:157` updates affected material and dependent summary entries, retaining mixed-support blocks; line 334 preserves unresolved conflicts, source references and distinctive user/error/API wording. Keep shared-memory's original-source checks, exact qualifiers and review fences. A removed derivative source does not independently make the underlying claim false.
- **Existing equivalents:** Codex's per-rollout extraction followed by consolidation and its summary-to-handbook-to-source read path have counterparts in shared-memory's candidates, reviewed records, compact views and source routes. Shared-memory already has incremental run changes and semantic closure; do not add another queue, file hierarchy or diff mechanism merely to match Codex.
- **Usage signal:** `codex-rs/state/src/runtime/memories.rs:448` filters Phase 2 inputs by recent use/source update and ranks by usage count. This could inform future retrieval diagnostics, but popularity is not truth or sufficient reason to expire rare constraints and negative evidence. Defer automatic forgetting until a concrete recall/cost problem warrants it.

Before changing the engine, assess a bounded semantic slice: assistant-only success claims, an explicit user correction after apparent success, differing-condition observations, mixed-support claims with one unavailable source, and unchanged inputs with unresolved review. Deterministic lifecycle tests alone do not establish that model instructions handle those cases.
