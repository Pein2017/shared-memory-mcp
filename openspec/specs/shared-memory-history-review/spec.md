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

### Requirement: Evidence-preserving consolidation closure
For a manually requested consolidation objective, the Agent SHALL review relevant omissions, candidates, advisory issues, stale claims, duplicates and apparent conflicts using eligible reviewed knowledge and permitted original sources as needed. It SHALL record evidence-based dispositions using the existing lifecycle, retain conditions and unresolved gaps, and verify useful ordinary recall before claiming consumer usefulness. The objective MAY expand across successive frozen source batches under its existing question and cutoff. Technical publication, source delivery, objective review and corpus coverage SHALL remain distinct. Neither output counts nor a technically successful Run SHALL establish semantic completion or full coverage.

#### Scenario: Compatible duplicates and incompatible conditions
- **WHEN** selected material contains duplicate accepted claims and observations under different conditions
- **THEN** compatible same-scope duplicates can receive a reviewed successor preserving provenance and decisive limitations, while different conditions remain distinguishable unless evidence establishes replacement

#### Scenario: Candidate and advisory backlog
- **WHEN** relevant candidates or advisory issues remain from an earlier review
- **THEN** consolidation reviews their original gaps, records approval, justified replacement, withdrawal or explicit deferral, and resolves an issue only after checking its requested correction or conclusion at the authoritative owner

#### Scenario: Retirement lacks a granted action
- **WHEN** a record is merely obsolete for recall and the current consolidation action set has no retirement operation
- **THEN** the Agent reports the retirement need without declaring the record false, substituting withdrawal or bypassing the action policy through ordinary maintenance

#### Scenario: Compact account is published
- **WHEN** consolidation publishes a compact account intended for ordinary recall
- **THEN** the Agent checks applicable ordinary context and targeted search/read within the actual consumer budget, retaining as-of status, decisive conditions, limitations and source routes; omitted required material remains an explicit gap

#### Scenario: Selected source remains inaccessible
- **WHEN** a granted read cannot deliver enough original material after supported bounded continuation, or access or ancestry is unresolved
- **THEN** claims depending on that evidence remain pending, independently supported work can finish, and the missing material is not treated as unchanged or reviewed

### Requirement: Consolidation retains evidence and retrieval anchors
Consolidation guidance SHALL retain claim-linked original sources, decision-changing conditions, counterevidence and distinctive user wording, error strings and API identifiers when producing a compatible successor or refreshing affected compact navigation. It SHALL use existing content and supported retrieval metadata, not invent new record fields. Derivative repetition MUST NOT count as independent support. An unavailable or deleted source MUST NOT by itself declare a claim false or remove independently supported parts. Unsupported dependent assertions SHALL remain distinguishable and pending, outside accepted view claims. Readback SHALL use original discriminating query terms and full detail as needed, rather than only the newly paraphrased title or audit visibility.

#### Scenario: Duplicate accounts carry different original query wording
- **WHEN** compatible records with the same conditions are merged and contain distinct useful error strings or API names
- **THEN** the successor retains the necessary original sources and wording, affected views preserve qualifiers and read routes, and ordinary searches using the original discriminating terms are checked for the qualified successor

#### Scenario: One source of a mixed-support account disappears
- **WHEN** one original or derivative source becomes unavailable while other checked evidence supports only part of the account
- **THEN** the Agent retains the independently supported part and its sources, explicitly marks the dependent gap for the unsupported part, and does not publish that pending assertion through a compact view

### Requirement: Expandable historical and incremental review objectives
The first default Dreaming baseline SHALL include applicable readable historical Pi/Codex backlog and existing memory without a silent recency or completed-session filter. Later objectives SHALL consider new/changed inputs and unresolved work from retained reviewed positions. Relevant discoveries SHALL be admissible through additional frozen batches under the same review question and cutoff; the first batch MUST NOT cap the objective's scope. While reviewable unprocessed work remains, the Agent SHALL continue without an invented cumulative-count, time or fee stop. User interruption, actual harness limits and concrete blockers SHALL retain exact remaining-work positions and truthful partial coverage. Source inventory, delivered pages and reconciled partial batches MUST NOT advance a reviewed baseline past unread, truncated or pending evidence.

#### Scenario: Relevant older correction is discovered after the first batch
- **WHEN** review discovers another permitted pre-cutoff session with a relevant correction or conflicting result outside the first selected batch
- **THEN** the objective expands through further batches and accounts for that evidence before claiming objective completion, without a new review question or cumulative quota

#### Scenario: Historical intake is interrupted
- **WHEN** an initial historical objective stops at a real context/harness interruption with reviewed and unreviewed source ranges
- **THEN** the retained progress distinguishes those ranges and resumes the remaining work without declaring a completed historical baseline or unnecessarily replaying all completed review

#### Scenario: One technical batch has completed
- **WHEN** a publication batch is reconciled and closed but additional relevant readable material remains within the objective
- **THEN** work continues in further authorized batches, and the completed batch is reported only with its own coverage

### Requirement: Active-session intake uses persisted cutoffs
Dreaming SHALL admit already persisted complete events from active sessions without waiting for session closure. It SHALL retain actual source-specific frozen ranges, memory revisions and capture boundaries, and SHALL distinguish unfinished outcomes from accepted results. Relevant pre-cutoff discoveries MAY enlarge the objective; later appends SHALL remain a subsequent increment. A wall-clock label alone MUST NOT establish an atomic filesystem snapshot. An append outside an unchanged consumed range MUST NOT alone invalidate that range, while changed consumed bytes or relevant authority changes SHALL reject stale dependent operations.

#### Scenario: Session remains active after intake
- **WHEN** a session appends events after the admitted complete-event cutoff
- **THEN** its frozen earlier events can be reviewed and valid effects reconciled, unfinished claims retain their status, and appended events remain for the next increment

#### Scenario: Consumed event bytes are changed
- **WHEN** a previously consumed source range changes before publication
- **THEN** the stale dependent operation is rejected and the affected selection is reconciled rather than mixing versions

### Requirement: Task-relevant read reach inherits existing authority
Dreaming read eligibility SHALL follow the originating Agent's effective read boundary as bound at the trusted harness/integration boundary, including relevant unregistered sources. A fixed catalog directory list MUST NOT impose a second eligibility ceiling within that boundary. Relevance SHALL determine reads; read reach MUST NOT enlarge publication projects, write/action authority or sensitive-content permissions. Caller-declared identity alone MUST NOT confer additional access. A denied or unsupported read SHALL remain an explicit gap rather than being bypassed or presented as reviewed.

#### Scenario: Relevant readable source lies outside catalog roots
- **WHEN** the originating Agent's bound permissions allow a relevant source not yet listed in the catalog or project registry
- **THEN** Dreaming can admit that source for reading without separate path approval, while retaining its independent publication scope and provenance

#### Scenario: Effective authority is absent or revoked
- **WHEN** the trusted integration cannot establish the needed read authority or that authority is revoked
- **THEN** the dependent read is denied or explicitly unsupported, without borrowing another session's labels or permission boundary
