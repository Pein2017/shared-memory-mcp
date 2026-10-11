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
