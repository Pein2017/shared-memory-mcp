## Context

See [proposal.md](proposal.md) for motivation and scope. This successor incorporates the user's design decisions, including the final agreement to preserve as-of understanding and check current owners when a judgment requires it. The [earlier content pilot](pilot.md) is historical diagnostic evidence, not implementation completion or authority to repeat it. This session owns specifications; the user's receiving web-codex session owns implementation.

The inspected source baseline is `b19a564bf5f11816742dec90162271ebd6601dd8` with unrelated, in-progress Dreaming changes. Preserve them. Existing owners to extend are:

| Owner | Observed responsibility | Next-version seam |
|---|---|---|
| `core.py`, `curation.py` | Canonical Markdown, source-linked publication, exact-scope successors, withdrawal, revision-fenced metadata | Shared ordinary-agent lifecycle across project and collaboration collections; mode metadata |
| `recall.py` | Field-aware lexical search; empty-query routing; bounded cards | Compose actual profile/background content and task evidence under one budget |
| `server.py`, `cli.py` | Nine ordinary tools and public CLI bridge with actual caller context | Extend those operations; do not introduce a parallel ordinary tool family |
| `dream_records.py`, `dream_views.py` | Collaboration claims, independently published views, source/lifecycle checks | Reuse claim admission and derived-view invalidation outside a DreamRun |
| `dream_catalog.py`, `dream_sources.py`, `dream_incremental.py`, `dreaming.py` | Granted source paging, branch evidence, coverage, processing states, checkpoints, frozen publication | Historical episode directory and readable incremental changes |
| `adapters.py`, `adapters/pi/shared-memory.ts`, `scripts/install-local.py` | Native identities, startup hooks and Pi ephemeral prefix | Deliver the common packet without host-specific knowledge logic |
| `tests/native_startup_probe.py`, `tests/pi_adapters.mjs`, `tests/test_stdio.py` | Native CPU/intercepted-request and transport checks | Verify final context delivery rather than tool availability alone |
| WebCodex `src/tool_runtime/coding_task.rs`, `context_projection.rs` and `memory.rs` in its own checkout | Workflow startup/tool-result projection; native `memory.bootstrap` reads WebCodex's own database | Attach shared memory to automatic Workflow Session start/resume output; do not confuse tool output with a Host model request |

The [reconciliation entry](../../README.md) records ten implemented baseline capabilities and seven archived changes. The successor modifies the exact conflicting requirements, including navigation-only startup, the separate Dreaming gateway and all-or-nothing freshness. Read baseline plus active deltas as one target contract. Unchanged scope, provenance, concurrency, source restriction and native-store requirements remain mandatory. Historical model-specific receipts do not authorize new model calls.

## Goals / Non-Goals

**Goals:**

- Deliver useful shared context before a user must ask an agent to search.
- Optimize for a coherent research account and a small operating surface; additional record counts and tool counts are not success measures.
- Separate task mode, storage ownership, permission and evidence level.
- Let every authorized agent maintain memory during ordinary work; reserve large cross-session synthesis for explicit manual Dreaming.
- Keep source-linked, dated project understanding available; refresh relevant current facts when the foreground task depends on them.
- Bound the material actually handed to models and make omitted detail recoverable.

**Non-Goals:**

- An autonomous scheduler, per-turn extractor, extra classification model or model calls inside the MCP core.
- A human-maintained memory notebook, a new dashboard, or automatic ingestion of arbitrary editor/shell modifications to canonical memory files. The human asks; the Agent uses the MCP lifecycle.
- Replacing native Codex/Claude/WebCodex memories, synchronizing them bidirectionally, or copying raw session corpora into the memory store.
- A second scientific ledger, permissions inferred from memory, or automatic checkpoint/experiment promotion.
- Embeddings, a general plugin framework, multi-host transactional storage or a new memory Git repository.
- A model-quality benchmark in this change. The user deferred it; delivery/correctness checks do not establish subjective parity with Codex Memory.

## Decisions

### Agent-oriented operating contract and one entrypoint

The ordinary experience is intent -> Agent context/search/read -> scoped MCP correction or contribution -> current knowledge on the next read. The user does not select an execution profile, manage a publication role, edit metadata or run a synchronization command. Keep manual Dreaming inside the same installed MCP entrypoint, using the same real caller identity and ordinary write authority. Batch discovery/recovery remains available to the Agent when that task is explicitly requested.

Reuse the current registry, project sharing, source grants and budget validation behind stable project configuration. Select the effective source scope from that configuration and the current task; do not require a dated profile name or an independently enabled publisher connection from an ordinary caller. Converge duplicated effect/admission paths instead of placing a new wrapper over two competing permission systems. A smaller operating surface does not remove scope checks, source verification, concurrency protection or interrupted-write recovery.

Installation leaves one owned `shared-memory` registration per harness. The former Dreaming endpoint and dated profile bindings are retired from active configuration after the replacement is qualified. Historical receipts may retain their original names and revisions. They are read-only provenance, not another live mode or an instruction to recreate the old endpoint. No fixed tool count or new general plugin framework is required.

### 1. One core, two task modes, independent ownership

Use `task_mode: research | general` as explicit request/session metadata, distinct from the existing `mode: navigation | task` response field. Startup before substantive input has no selected task mode; this is an unbound state, not a third category. The foreground agent selects a mode once it understands the first substantive request, without a second classifier request. User selection overrides inference; a material task transition permits an explicit switch. Record the selected mode and short reason in the host's normal task/session context.

The common core remains stateless with respect to classification: `context` and `search` do not persist a binding as a hidden read side effect. The caller passes its current binding. Adapters reuse their host session metadata or the latest explicit binding message on resume; if neither survives, report an unbound state and select again. Do not invent a task ID or inherit another session's selection. A cross-mode search passes an override for that lookup without silently changing the session binding.

Add reviewed `task_modes` metadata to curation and collaboration/history envelopes; allow either or both values. Existing unlabeled records remain discoverable with an unknown classification until reviewed. Do not mechanically map `domain=engineering` to general, equate `.worktrees/` with research, or create two physical knowledge databases. Mode is a soft ranking and presentation preference for knowledge, never a default exclusion of another mode's authorized relevant evidence. Corrections, necessary conditions and counterevidence remain discoverable across modes. Hard mode filtering requires an explicit user-selected restriction and reports that boundary; it cannot present a claim while dropping its necessary qualifiers. Preference applicability is separate and remains strict: a research-only preference need not apply to a general task. Neither rule creates cross-project access.

Alternative rejected: directory-only classification or a permanently research/general thread. Both misclassify the user's mixed root histories and engineering work inside research checkouts.

### 2. Three content levels with one authority per item

| Level | Persistence/owner | Role |
|---|---|---|
| Context | Rendered packet; reuse published collaboration/research views where applicable | Small profile, project background, relevant state and pointers |
| Reusable knowledge | Existing project records and `collaboration/Pein/records`, with curation | Conditional knowledge and preferences with reviewed lifecycle |
| Historical episodes | Source-linked Markdown accounts under `history/<project>/episodes/`, using existing source/Run evidence | What happened, what changed, what remains unknown, and where to inspect the original |

Episode metadata binds original harness/session, physical cwd/project/worktree, selected branch/leaf when applicable, exact event ranges and source versions, task modes, observed task state, summary revision and review receipt references. One episode represents a coherent task segment, not necessarily one whole session. Multiple episodes may refer to one session without duplicating its transcript or claiming independent corroboration.

History is an explicitly selected collection in `search/read`; it is not automatically eligible knowledge. Its summaries may describe unfinished work, but must not enter ordinary recall by being relabeled as durable observations. This preserves the existing rejection of handoffs/progress disguised as knowledge. Existing source cursors and Run processing receipts remain the authority for technical coverage; episode metadata references them instead of creating a second cursor ledger. A rebuildable index is optional implementation machinery, never another knowledge owner.

Alternative rejected: generating one permanent knowledge record for every conversation. Many sessions contain no reusable signal, and routine task state should not compete with preferences and evidence.

### 3. Common ordinary CRUD, with retained admission rules

Extend the existing ordinary operations with a strict collection selector where required: `project` (existing default), `collaboration`, and `history`. Reuse their existing candidate, review, successor, retirement/withdrawal and idempotency semantics. Typed collection payloads are explicit; a project record must not be silently converted to a preference or episode. Existing callers that omit the selector retain their project operation meaning.

Factor reusable claim/source validation and canonical effects out of DreamRun orchestration so an ordinary authorized agent can contribute collaboration knowledge without starting a Run or acquiring a special Dreamer identity. The same routines serve Dreaming. Keep current subject/project grants, actual caller provenance, original source locators, dispositions, exact-scope replacement and concurrency/replay fences. An explicit authorized correction updates memory in its established scope; a missing runtime observation is disclosed rather than fabricated. Caller-provided actor/role names are not authentication or extra authority.

An explicit reusable user preference can be published with its original scope and source review. An inferred preference starts as a candidate; a later authorized review can publish it while preserving `inferred`. One task request does not establish a global preference. Contradictory conditions may coexist; only a correction of the same scoped claim replaces it. Any authorized foreground agent can perform that review; no new human approval is required for each low-risk contribution already within the user's task grant.

Use an explicit **cooperative live-conversation review** path for a current, direct, unquoted user correction observed by the authorized foreground Agent. Record `agent-reviewed` assurance, actual caller/session, asserted scope, the available original message locator, review method, time and only the bounded source excerpt necessary to audit the correction. If the native history/event locator is not yet available, record that limitation and the observed current-message basis without inventing an event ID, source hash or operator attestation. The correction can take effect immediately within existing grants; admission never requires a new human metadata/approval workflow.

This path deliberately trusts the authorized Agent's account of the live conversation; it does not authenticate the human or equal `operator-attested` evidence. The current Dreaming attestation requirement for historical personal-preference extraction remains intact: historical/quoted/delegated/ambiguous material cannot be relabeled as a live original message or laundered through a newly admitted record. Inferred preferences remain candidates until reviewed, with their inferred status retained. Share scope, dispositions, negative source-use decisions and replay fences apply to both paths. These are distinct evidence bases in one lifecycle, not different publisher roles or another permission service.

Ordinary contributions are agent decisions at meaningful task nodes, not automatic transcript extraction by hooks. `read` never makes a candidate active. History review distinguishes extraction, source checking and semantic review; adding an episode summary does not mark every underlying byte reviewed. Concurrent ordinary changes and Dreaming use the same write gate and expected revisions; stale drafts must be rebased/reviewed, not forced over intervening work.

Derived context is not independently editable truth. Profile/path corrections update canonical claims through the Agent-facing MCP operation; the next context call selects current active claims and invalidates affected cached views. Reading must not wait for the next manual Dreaming to see an ordinary, already-published correction. The user does not have to create a candidate or approve a replacement manually; retained internal lifecycle steps must be completed by the authorized Agent/tool path. Deletion means withdrawal from default recall with recovery/provenance retained, not physical erasure or revival of an older superseded claim.

Make corrections reach source-only overviews as well as record-dependent views. Reuse the existing claim/view metadata to give a small number of narrative units stable scoped identities (for example goal, milestones, a branch account and its current decision). Each unit binds its sources, review time, optional canonical claim dependencies and explicit correction/replacement references. The original owners remain authority; this is not one record per sentence or another fact database. A reviewed correction identifies the affected scoped unit/current assertion, so unchanged owner bytes cannot preserve a contrary active statement.

Current context resolves these replacement/withdrawal relationships before selecting even a cached or compact variant. A new pause decision replaces the branch's current-plan assertion while its historical results and motives remain. Ordinary owner edits instead retain the dated account; forbidden dependencies return no text. If an old monolithic view has no safe unit mapping, do not guess or patch prose in the core: mark that affected legacy unit unusable for the current assertion, supply the correction, and have the authorized Agent publish a reviewed unitized account. Preserve old receipt bytes and independently identified units; do not block the correction on a full migration.

An original, explicit user decision about the current plan takes precedence over an older plan in a document for the same scope. Keep its source and mark the document discrepancy. A plan correction does not alter observed experimental evidence, silently broaden another project's scope, or grant a new execution action. Distinguish original user messages from delegated/quoted history before assigning that precedence.

### 4. A single content-bearing context contract

Extend the existing `context` operation/CLI with `task_mode` and bounded task/topic selectors; retain actual `CallContext` unchanged. `search` accepts a mode preference/override and collection selection. Keep current explicit full/history reads available; add bounded continuation where oversized detail would otherwise expand model input without limit. Do not create a second startup tool or require ordinary consumers to know DreamRun IDs, generations or publisher flags.

The common packet includes a packet revision, actual scope, selected/unbound task mode, source as-of/coverage, selected content, source/read pointers, omissions and budget accounting. Compose in this order:

1. Applicable reviewed collaboration preferences, including mode/project conditions.
2. Stable background of the resolved project and a small topic navigation map.
3. When a task is known, its relevant research/general summary, current-state material and evidence cards.
4. Necessary corrections, conditions and bounded one-hop related evidence.

Use readable semantic units rather than a flat sequence of execution receipts. A research overview's normal order is goal -> route-wide milestones -> relevant branch and turning points -> accepted outcome, limits and current/open question. Keep source details behind usable pointers and the audit projection; do not repeat full source hashes in both prose and envelope when a compact reference table suffices.

Mode-conditioned preferences wait for the relevant mode; genuinely shared preferences can appear before task selection. Registered project access remains a prerequisite for shared context in this deployment. Unknown/ambiguous cwd returns diagnostics without another project's profile or history. Missing views fall back to eligible canonical claims and navigation, not fabricated summaries.

Extend project routing with a versioned context section identifying reviewed background records, topic/mode selections and named authorized owner sources. Reuse existing collaboration allowlists and source-grant/disposition checks rather than allowing a claim to grant itself access. Reader configuration is independent of executor/batch budgets: published knowledge consumption does not require a Dreaming execution profile. Do not let an arbitrary URI in returned memory cause automatic local-file or remote-URL reads.

Use current lexical/topic retrieval first. Expand a bounded number of existing `corrects`, `conflicts_with` and `derived_from` relations after admission, deduplicate by canonical identity, preserve relation direction, and include the condition that makes a conflict comparable. A superseded hit can supply a pointer to its active correction, but its old body must not leak into default recall. If a necessary qualifier/correction cannot fit, omit the affected claim and retain a read pointer. A bounded search that found no counterevidence must not claim none exists.

Alternative rejected: replacing retrieval with embeddings before proving a lexical/topic miss, or pushing the entire profile/research view into every request.

### 5. Explicit serialized budgets and honest token accounting

Use a default **2,000-token target** for the combined active bootstrap/task packet, initially allocating approximately 800 to profile/background and 1,200 to task material. This allocation is a selection priority, not two independent 2,000-token limits. Profile-only startup need not fill unused task space.

The enforceable portable default is **8,000 UTF-8 bytes for the active shared-memory packet**, including bootstrap and task parts together, identity, wrapper, qualifiers, pointers and budget/omission metadata. Native text and MCP/CLI projections are measured after their actual serialization. If a host stores bootstrap and task parts in separate messages for prefix stability, their combined current exposure uses the same budget. When a transport/host exposes both structured content and its text fallback to the model, count the combined exposure or ensure that consumer selects only one representation. A transport-specific duplicate must not silently double the budget.

Where an already-available, qualified tokenizer is available at the consumer, also enforce the 2,000-token cap and select fewer whole items when needed. Otherwise label token accounting estimated/unavailable and enforce the byte limit; never claim that a character or byte ratio is an exact model-token bound. No tokenizer/model dependency or provider request is required in the core. Dense CJK, escaping and long identifiers are explicit qualification cases. This is a bounded first release, not a promise of exact token parity across arbitrary models.

For each unit intended for default context, the contributing/reviewing Agent supplies a reviewed compact rendition with the same identity, sources, conditions and evidence level. Reuse existing reviewed summaries/claim text where sufficient. The ordinary core selects complete compact units and pointers; it does not call a model or invent an on-the-fly paraphrase. A longer rendition is optional detail, not another truth owner. Publication and migration qualify a useful compact packet under the default serialized cap. An explicitly smaller caller cap can legitimately return budget-limited, but that diagnostic alone cannot pass normal populated-startup acceptance. Every compact rendition follows the same correction and revocation dependencies.

The core and every adapter use this one budget contract. Remove the observed independent gateway default that silently skipped a published 3,915-character synopsis at 2,000 characters. When all eligible semantic content is omitted, return an explicit budget-limited result with a bounded continuation/read route, not `valid` with an unexplained empty body. A declared smaller caller cap remains enforceable; the implementation must not silently raise it to make a test pass.

Trim whole semantic items, preserving conditions and source identity. Report an omission count and compact continuation pointers. If the minimal identity/status envelope itself cannot fit a requested smaller cap, return a bounded diagnostic rather than stripping provenance. Detail reads/page requests have their own explicit response budgets; successive pages are deliberately requested expansion, not free additions to the startup budget.

Avoid accumulating repeated packets. Pi replaces one owned ephemeral bootstrap and one current task packet. Append-only Codex/Claude boundaries receive versioned updates only when relevant content/binding changes; unchanged same-epoch recalls emit no duplicate. Resume/compaction re-establishes a fresh bounded packet. Older transcript text cannot be erased by these hooks, so the limit is per active delivered packet/response, not a false guarantee about all accumulated conversation tokens. Newer revision and scope markers disambiguate an update without presenting memory as system instructions.

The native `SessionStart` payload supplies no replay/epoch identity. Two equal payloads can be two real resumes: each native lifecycle invocation therefore re-establishes context. Do not persist a suppression key made from session ID and event source. Within an existing lifecycle, a consumer retaining the packet uses `previous_revision`; Pi retains its owned parts on an unchanged response. WebCodex's automatic attachment occurs at `work_on_project` creation or explicit resume, not at an ordinary observation call. These boundaries were qualified independently in the October 9 repair; equal hook arguments alone were not a valid duplicate-delivery counterexample.

### 6. Four thin consumer integrations

| Harness | Startup/background | Task selection and refresh | Required delivery evidence |
|---|---|---|---|
| Codex | Existing actual `SessionStart` hook renders the common packet | Foreground shared skill calls `context(task_mode, query)` after first input/switch; lifecycle refresh handles resume/compact | Installed hook trust plus intercepted final request containing selected content |
| Pi/Pi Web | Existing extension consumes the common packet and keeps its stable early position | Foreground selection is passed through the common call; extension retains packet revision/mode for replacement. `before_agent_start` can detect input/change, but does not implement another classifier | Installed SDK and actually configured MCP adapter conversion, including compaction/switch |
| WebCodex | Automatically attach common shared background to successful `work_on_project` start and explicit exact-session resume output, using the resolved cwd and real `wc_sess_*` identity | Foreground binding uses the common revision-aware API; explicit resume re-establishes a fresh scoped packet, including unchanged content | Real serialized automatic startup/resume result after final public projection; native `memory.bootstrap` remains independent. Host model-request visibility is a separate, optional evidence boundary |
| Claude | Retained `SessionStart` hook renders the same packet without changing auto-memory | Shared foreground skill selects mode; supported lifecycle refresh remains append-only | Installed hook/MCP request interception with native settings unchanged |

WebCodex's `context_projection.rs` populates `ToolResult.output`; it is not the ChatGPT Host's model-request builder. Its native `memory.bootstrap` is also independent. Before implementation broadens, identify the actual `work_on_project`/resume caller-to-public-result path, including any sparse projection that could drop new content. Default successful start/resume must carry shared background without a separate memory call or opt-in `context_request`. If no real Workflow Session is resolved, return a bounded honest diagnostic; never borrow a transport ID. Verify final serialized tool delivery, scope, failure handling, refresh and budget.

Inspect whether an observable Host request seam exists, but do not build a new Host adapter or require paid inference to manufacture it. If unavailable, record Host final-request inclusion/retention as unverified; it does not block completion of the defined WebCodex server-owned delivery contract or the other harnesses. No pre-first-WebCodex-call injection is promised. The companion implementation belongs to `/data/CoordExp/codex-tools/web-codex`, under its then-current owners and instructions.

Extend the installer and single bundled shared skill consistently, including removal of the separately installed Dreaming registration during the authorized cutover. Installing tools is not sufficient evidence of content delivery. Do not restart active user sessions or change native memory paths to obtain a passing check. Provider/token-use or subjective benefit claims remain deferred even when CPU/native delivery checks pass.

### 7. Manual historical review and incremental change sets

Manual Dreaming reuses its existing source discovery, frozen batches, attempts, generations, publication and recovery behind the common entrypoint. These support the Agent's work; they are not a human-operated approval pipeline. Add two bounded projections to the current workflow: historical episode inventory and changes since the last successfully consumed selection. Reuse existing catalog/audit/material calls with explicit selectors or extend them narrowly; do not add a second batch runner.

The change set describes added/appended/modified/unavailable source ranges; newly published/corrected/withdrawn/retired knowledge; episode changes; and derived views affected by those dependencies. It carries exact from/to revisions, pointers and bounded human-readable excerpts/diffs. A filesystem digest indicates identity; the readable difference tells the reviewer what changed. Check the whole dependency closure for a modified claim within the allowed batch; if the closure exceeds the budget, mark pending work instead of claiming complete consolidation.

Git-backed owner differences use the existing repository history, with the actual dirty working-file snapshot also bound when read. Native session inputs use existing event/prefix/cursor identities. No automatic commits, Git reset or memory repository are needed. A later export/version-browser feature would be a separate requirement, not a hidden prerequisite here.

Bind semantic consumption to a frozen review objective as well as the selected sources. The Agent derives the concise objective from the user's request, reuses the existing objective identity for a continuation, and explicitly binds a new one when the question changes; no human form, classifier model or second runner is needed. Reuse existing Run/checkpoint metadata: separate source change, objective completion, pending review and unresolved effects. Physical source cursors can be reused across objectives, but semantic completion cannot.

Keep the existing single-live-lane/takeover protection independent of objective selection; changing the objective cannot bypass a live invocation or ambiguous prior effects. Same sources plus a new question create new bounded review work after reconciliation, reusing established knowledge and exclusions. Same sources plus pending-review retain an actionable continuation even when every event already has a transport/processing mark. `no-change` describes source/basis changes only; it must not imply the objective is complete or return `model_required=false` as a claim that no review is needed when semantic work remains. A no-work completion requires the same objective to be reviewed/disposed, no pending review, no unprocessed required material and reconciled effects. Objective-scoped exclusions/no-signal remain distinct from global source-use prohibitions.

Advance that objective's semantic consumption baseline only after the affected publication/coverage outcomes are reconciled. Existing per-effect successful writes survive partial batches; unresolved changes remain pending. Recover interrupted publication through canonical receipts. Source disappearance or an invalid reader is not successful no-change. A later source correction invalidates the earlier episode/derived assertion as needed, without pretending an old historical observation never happened or reviving rejected/no-reuse material.

Keep review states distinct: discovered/scanned source coverage, extracted episode account, source-checked/reviewed outcome, no-signal, excluded and pending-review. Reuse existing processing states and add only the missing semantic review metadata. Reading a page changes neither publication nor reviewed status. Preserve result/control pairs, short user answers with their questions, and later corrections; a truncated excerpt cannot support a claim of complete review. Ordinary agents can maintain individual episodes through the common lifecycle, while manual Dreaming performs cross-episode synthesis.

Dreaming may propose a new connection across sources, but labels it as an inference/hypothesis and preserves the distinction from recorded findings and historical motives. An inferred explanation of why a route changed must not be rewritten as the reason the user originally gave. Reuse the existing issue/proposal representation for suggested owner-document improvements, adding topic/source retrieval where missing. A relevant future Agent sees a concise unresolved note, decides within its current task authority, or asks the user. Resolution remains recorded so handled notes do not recur as pending. This creates no automatic worker dispatch, notification service, new research queue or permission to change formal owners.

### 8. CoordExp research lens and freshness without automatic synthesis

Use project-owned configuration plus the existing shared skill/curation instructions, not hardcoded research rules in the generic ranking engine. The initial configured owners are canonical `research/index.md`, the selected question pages, their catalog/result/state links, and the corresponding versioned source evidence. Exact authorized roots/files are selected through the existing registry/grant machinery; a recursive grant for all `/data/CoordExp` is not a substitute.

The research view answers: long-term objective; important route-wide milestones; the relevant branch and why it changed direction; current competing explanations and accepted outcomes; known limitations/closure; and missing observations that could change the judgment. The approved content example in [pilot.md](pilot.md) places the milestone paragraph between the objective and the airport branch. Keep historical episode accounts separate from current state. A next-observation summary is descriptive advice, never a queue or execution grant.

CoordExp summaries must distinguish physical-owner coverage from annotation matching, conditional/forced behavior from natural generation, local repair from generalization/preservation, and technical completion from scientific support. These are project interpretation rules. General mode uses the same machinery to surface work goals, accepted decisions, implementation state and reusable engineering lessons without inheriting unrelated research constraints.

The remembered account is the Agent's source-linked understanding **as of its last review**, not a continuously synchronized project database. Stable goals, historical milestones and the relevant branch account remain useful when an owner gains new material. Retain their source/version and review time. Normal source drift changes freshness metadata and which current claims require checking; it does not itself declare the old findings false or erase the whole account.

Keep freshness and eligibility separate. The core checks current permissions, withdrawal, supersession and source-use restrictions before exposing any unit. Revoked/prohibited content stays unavailable even through historical views. For ordinary permitted source changes, return the usable as-of account with affected-unit freshness markers and authorized owner pointers. Mark remembered current-state statements as historical/needs-check, never as verified current. If a known correction supersedes a claim, ordinary recall uses the corrected claim; staleness is not a way to revive it.

When the task asks “where are we now?” or the Agent is about to make a consequential current-state judgment or recommendation, the foreground Agent automatically reads the relevant current index/question/unit/result owners, compares changes and revises its understanding. It need not ask the user to arrange synchronization. General background recall does not trigger a full-source revalidation or another model call. Bind source dependencies to meaningful units so one branch update does not blank unrelated milestones. Preserve all sources needed for conditions and counterexamples; splitting cannot hide contrary evidence.

The core supplies bounded, authorized excerpts/pointers and honest changed/unavailable/unknown indicators; the foreground Agent performs the reasoning in its existing task. It can publish a reviewed correction through ordinary CRUD. If a current fact cannot be established, retain the useful dated account and disclose the current-state gap. If the source changes again during that bounded read, report a partial result rather than chasing an active writer. The pilot's whole-view invalidation after an execution-preparation note is the nearest wrong behavior: the next version must retain the dated narrative while checking the affected current state.

Current closure is scoped: the stopped airport sparse-token sequence can coexist with a separately preparing multi-scene investigation. The selected current owner, and a later explicit user decision when applicable, determine that distinction. Dreaming's suggestions to clarify a formal document remain proposals until a future Agent or the user decides under then-current authority.

### 9. Historical bootstrap is bounded ingestion, not a native-store migration

The user's proposed source order is accepted:

1. Inventory knowledge entrypoints and research/OpenSpec/source owners under `.worktrees/`, beginning with canonical research-probes; then correlate relevant Codex/Pi session task segments.
2. Inventory independently registered `codex-tools/` projects and their corresponding sessions.
3. Review root `/data/CoordExp` sessions, splitting mixed research/general tasks and resolving original versus current cwd/project mappings explicitly.

Current owners establish current state. Historical sessions supply reasons, explicit preferences, reversals and unfinished context. `.worktrees/` is a research prior and root/codex-tools a general prior, never a final classifier. Native memory summaries may locate original evidence; they do not become independent support or a writable synchronization target. Missing historical paths stay missing/unmapped until a documented exact mapping exists.

Each manual batch binds project/source selections, cutoff/branch, resource envelope, reviewer, output target and stop boundary before reading beyond inventory. Select public supported history and relevant owner documents; exclude models, datasets, bulk runtime outputs and private payloads from indiscriminate traversal. Review evidence in bounded passages, retain coverage/gaps and resume from existing checkpoints. Do not sweep every session in one invocation or fill the foreground context with the corpus.

Check existing candidates, active/inactive records and dispositions before publishing to prevent duplicate or resurrected claims. Report new/updated/no-signal/pending episodes and knowledge with source pointers. Enable content-bearing context only from eligible published material; no empty store may invent a profile. First-batch size/model/cost is an execution parameter selected when the user launches that batch, not implicit permission granted by this plan.

## Risks / Trade-offs

- **Manual Dreaming leaves synthesis gaps** → ordinary source-linked contributions and current-owner reads keep important corrections visible; expose remaining historical coverage instead of promising complete recall.
- **First-message classification is imperfect** → reversible explicit mode binding, mixed episode labels and cross-mode lookup; no permission changes.
- **Small budgets omit useful knowledge** → preserve qualifiers, rank relevant material and return recoverable pointers; do not silently chop claims or inflate the packet.
- **Byte bounds are not exact provider token accounting** → report the counting method, enforce serialized caps and qualify actual consumers before token claims.
- **Concurrent agents publish against different snapshots** → common revision fences, exact-payload replay and existing writer gate; test an ordinary correction during Dreaming.
- **Append-only hosts retain old context** → revision/scoping markers, same-epoch deduplication and compaction refresh; no claim of erasing history.
- **Recent or frequently quoted summaries dominate evidence** → current-owner checks, conditions/corrections and derivative lineage; citation frequency is not correctness or independent corroboration.
- **Ongoing pilot work changes the integration base** → preserve its ownership and reconcile only affected interfaces before implementation; reuse compatible shipped capabilities rather than overwriting them.

## Migration Plan

1. The receiving session inventories the current dirty checkout and implements against disposable stores first, beginning with the correction-to-context-to-consumer slice: a current user correction, scoped ordinary write, replacement of the corresponding source-only overview assertion, useful compact context and actual consumer delivery. Use the retained pilot only as a bounded counterexample; do not rerun it or borrow its old write/installation authority.
2. Preserve existing record bytes and operation replay. Add optional metadata/versioned episode artifacts and extend typed public arguments without legacy aliases or a second ordinary API. Keep unlabeled records readable.
3. Implement the reconciled capability deltas and update the shared skill's routing-only wording; retain the stable Pi prefix and existing native-memory separation. Update source docs and installers together. Consolidate active configuration into one endpoint and stable project/source settings, preserving historical receipts and their original source bindings without rewriting hashes.
4. Qualify all four declared consumer seams with isolated/native CPU interception and actual configured serialization. WebCodex completes at automatic public start/resume delivery; report any unobservable Host final request separately. Missing required server/native delivery remains incomplete. Paid model-behavior comparison remains deferred.
5. When installation is requested, back up only owned settings, install the qualified package/adapter entries, and verify fresh/idle consumers without interrupting active work. Do not borrow authorization from an older pilot or qualification recipe.
6. When production historical bootstrap is requested, run the selected bounded manual batches in the source order above, publish reviewed output through ordinary/Dreaming shared effects, and retain partial progress. The ten-owner content pilot is not that bootstrap. The full corpus is not a prerequisite for useful initial context.
7. Roll back by disabling/restoring the new owned integration settings and packet selection, leaving published source-linked memory and receipts intact. Correct/withdraw bad outputs through the lifecycle; do not Git-reset the shared store or delete native history. Older binaries must not be pointed at unsupported new collection formats as a claimed safe downgrade.

## Open Questions

No unresolved architecture choice blocks implementation planning. The first real backfill's model, batch size and cost cap, final installed native versions, and any later model-quality study remain execution-time inputs with explicit evidence limits; they do not change the contracts or task decomposition here.
