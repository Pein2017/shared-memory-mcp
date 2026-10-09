# shared-memory-history-review Specification

## Purpose
Recover useful task history and incremental changes through bounded manual review, without turning transcripts, processing receipts or historical permissions into current knowledge or authority.
## Requirements
### Requirement: Manual consolidation with ordinary contributions
Dreaming SHALL run only when manually requested within a declared source and resource scope. Ordinary Agents SHALL still be able to capture meaningful corrections and durable findings during their tasks. Reading or task classification MUST NOT launch a background model, a scheduler or automatic per-turn transcript extraction.

#### Scenario: Research owner changes without a Dreaming request
- **WHEN** an ordinary Agent encounters a changed owner
- **THEN** it can read the current owner and maintain the relevant memory within its task, without scheduling a separate consolidation model

### Requirement: Public historical source fidelity
Historical review SHALL preserve original event identity, public-message provenance, branch/ancestry and source-version boundaries. Supported file structure SHALL govern reader compatibility rather than exact equality with the currently installed CLI release. Unknown structure, unresolved ancestry and ambiguous human attribution MUST remain explicit gaps.

#### Scenario: Older CLI produced a supported history format
- **WHEN** a selected history was written by a different release but satisfies the qualified format contract
- **THEN** it remains readable with its actual producer version retained

#### Scenario: Pi branch has a missing structural ancestor
- **WHEN** ancestry cannot be established for a selected public event
- **THEN** the event is not published as established user knowledge merely because its displayed role is `user`

#### Scenario: Saved Pi branch has an ancestor outside the payload page
- **WHEN** offline history review selects the saved resume branch or an explicit leaf
- **THEN** complete frozen structural ancestry is checked before public admission and reused across payload pages with epoch/grant fences; saved selection is not described as a live in-memory branch

#### Scenario: Preserved original messages cross known private Pi nodes
- **WHEN** a supported private custom, usage, context-edit or summary entry has valid `id`/`parentId` links in the selected branch
- **THEN** those edges can establish ancestry for separately persisted original messages while private payloads remain excluded, summaries retain missing-original coverage gaps and human attribution is unchanged; branch-summary `fromId` does not become ancestry and offline review does not claim native model-context replay

#### Scenario: Structural projection changes after an earlier frozen read
- **WHEN** a retained graph reference belongs to an incompatible structural projection revision
- **THEN** it is rejected for continuation pending a fresh qualified read, without changing original source/receipt hashes or silently repinning its digest

### Requirement: Task episodes rather than session-shaped knowledge
The historical directory SHALL represent coherent task episodes with original source ranges, scope, modes and limitations. Mixed sessions SHALL be splittable by content. Historical accounts MUST remain distinguishable from reusable active knowledge, and directory names MUST NOT become authoritative research/general labels.

#### Scenario: Root session mixes engineering and research
- **WHEN** one historical session contains both an installation repair and a research decision
- **THEN** review can retain separate linked episodes and classifications without duplicating the transcript or granting either episode another project's access

### Requirement: Readable incremental change sets
A manual batch SHALL identify relevant changes since the last successfully consumed baseline for its frozen review objective, including source modifications, corrections, withdrawals and affected summaries. Existing Git history and source/event identities SHALL supply provenance; no new memory Git repository or automatic commit SHALL be required. An unreadable source MUST NOT be reported as unchanged.

#### Scenario: Previous batch left unresolved material
- **WHEN** consolidation resumes after partial publication or incomplete review
- **THEN** completed effects remain acknowledged and pending changes remain visible instead of advancing an unsupported complete-review baseline

### Requirement: Objective-scoped semantic continuation
The foreground Agent SHALL derive and bind the bounded review objective from the current request, reuse its identity for continuation and explicitly select a new objective when the question changes. Source-change status, objective completion, pending review and unresolved publication effects SHALL remain distinct within the existing Run/checkpoint model. Source cursors MAY be reused but MUST NOT transfer semantic completion across objectives. Objective selection MUST NOT bypass the single-live-lane, takeover, replay or current source-use restrictions.

#### Scenario: Unchanged source with pending semantic review
- **WHEN** every selected event has a processing mark but at least one remains pending-review for the current objective
- **THEN** continuation exposes actionable unfinished review even if source bytes are unchanged, rather than reporting no work or model-not-required as if semantic review were complete

#### Scenario: Same owners and a different research question
- **WHEN** a completed branch synopsis is followed by a requested preservation-counterexample review over the same owner files
- **THEN** the Agent can bind the new objective and perform bounded review using existing artifacts without an accidental source-only no-change skip or revival of prohibited material

#### Scenario: Same objective is fully reconciled
- **WHEN** source/basis are unchanged, the same objective is reviewed or explicitly disposed, no required material remains unprocessed or pending, and effects are reconciled
- **THEN** the system can report a no-work outcome with those conditions distinguished from merely unchanged source bytes

### Requirement: Bounded paging and honest review coverage
The system SHALL support bounded continuation for long source material and distinguish transport delivery, extraction and semantic review. Whole-source or whole-corpus completion MUST NOT be inferred from a file being readable, a page being delivered or a Run closing.

#### Scenario: Long event is fully delivered but only selected claims are reviewed
- **WHEN** all pages have been read by transport for a narrowly scoped synopsis
- **THEN** the output can publish those reviewed claims while retaining partial or unprocessed coverage for the remaining historical-review objective

#### Scenario: Native message exceeds the old framing window
- **WHEN** a qualified native event is larger than 64 KiB but within the supported 8 MiB event bound
- **THEN** all reader paths decode the complete event and apply public/sensitive-content filtering before body paging; page pieces retain its event ID, digest and locator rather than becoming independent evidence

#### Scenario: Source page ends inside a supported event
- **WHEN** a page cannot admit the complete native event
- **THEN** it returns the exact event offset and a truthful required-size lower bound without advancing coverage past that event; a later supported larger page can admit it before bounded body delivery

### Requirement: Single live work and recoverable partial outcomes
The system SHALL retain one live invocation for a bound consolidation lane, support explicit identity-preserving continuation and reconcile actual effects after interruption. It MUST retain successful bounded work without claiming unrelated source coverage or restoring the whole store.

#### Scenario: Publication times out after a possible write
- **WHEN** the caller cannot tell whether the operation completed
- **THEN** it inspects or replays the identical operation against retained effect evidence rather than starting a replacement batch or changing the payload under the old key

