## MODIFIED Requirements

### Requirement: Manual consolidation with ordinary contributions
Dreaming SHALL run only when manually requested within a declared source and resource scope. Ordinary Agents SHALL still be able to capture meaningful corrections and durable findings during their tasks. Reading or task classification MUST NOT launch a scheduler, a daemon or per-turn transcript extraction. The only automatic writer SHALL be the bounded startup-triggered session extraction defined in shared-memory-session-extraction, which produces candidates that Dreaming consumes as inputs alongside original sources.

#### Scenario: Research owner changes without a Dreaming request
- **WHEN** an ordinary Agent encounters a changed owner
- **THEN** it can read the current owner and maintain the relevant memory within its task, without scheduling a separate consolidation model

#### Scenario: Extracted candidates reach Dreaming
- **WHEN** session extraction has produced candidates since the last reviewed position
- **THEN** a Run's inventory lists them as pending inputs with their source session identities, and publication still requires the Run's own review against original sources

### Requirement: Readable incremental change sets
A manual batch SHALL identify relevant changes since the last successfully consumed baseline for its target project, including source modifications, corrections, withdrawals, affected summaries and newly extracted candidates. Existing Git history and source/event identities SHALL supply provenance; no new memory Git repository or automatic commit SHALL be required. An unreadable source MUST NOT be reported as unchanged.

#### Scenario: Previous batch left unresolved material
- **WHEN** consolidation resumes after partial publication or incomplete review
- **THEN** completed effects remain acknowledged and pending changes remain visible instead of advancing an unsupported complete-review baseline

### Requirement: Objective-scoped semantic continuation
The foreground Agent SHALL derive and bind the bounded review objective from the current request, reuse its identity for continuation and explicitly select a new objective when the question changes. Source-change status, objective completion, pending review and unresolved publication effects SHALL remain distinct within the existing Run/checkpoint model. Reviewed source positions SHALL be shared across objectives of the same target under shared-memory-dreaming; semantic completion of a question SHALL NOT transfer to a different question. Objective selection MUST NOT bypass the single-live-lane, takeover, replay or current source-use restrictions.

#### Scenario: Unchanged source with pending semantic review
- **WHEN** every selected event has a processing mark but at least one remains pending-review for the current objective
- **THEN** continuation exposes actionable unfinished review even if source bytes are unchanged, rather than reporting no work or model-not-required as if semantic review were complete

#### Scenario: Same owners and a different research question
- **WHEN** a completed branch synopsis is followed by a requested preservation-counterexample review over the same owner files
- **THEN** the Agent can bind the new objective, request an explicit re-review range and perform bounded review using existing artifacts without an accidental source-only no-change skip or revival of prohibited material

#### Scenario: Same objective is fully reconciled
- **WHEN** source/basis are unchanged, the same objective is reviewed or explicitly disposed, no required material remains unprocessed or pending, and effects are reconciled
- **THEN** the system can report a no-work outcome with those conditions distinguished from merely unchanged source bytes

### Requirement: Bounded paging and honest review coverage
The system SHALL support bounded continuation for long source material and distinguish transport delivery, extraction and semantic review. Whole-source or whole-corpus completion MUST NOT be inferred from a file being readable, a page being delivered or a Run closing. A Run close MAY accept named permanent gaps: for each accepted gap the executor supplies the source identity, the gap reason and a note; the reviewed position then advances past the gapped range, the gap is retained in the checkpoint and reported by later inventories, and accepted gaps MUST NOT be presented as reviewed content.

#### Scenario: Long event is fully delivered but only selected claims are reviewed
- **WHEN** all pages have been read by transport for a narrowly scoped synopsis
- **THEN** the output can publish those reviewed claims while retaining partial or unprocessed coverage for the remaining historical-review objective

#### Scenario: Native message exceeds the old framing window
- **WHEN** a qualified native event is larger than 64 KiB but within the supported 8 MiB event bound
- **THEN** all reader paths decode the complete event and apply public/sensitive-content filtering before body paging; page pieces retain its event ID, digest and locator rather than becoming independent evidence

#### Scenario: Source page ends inside a supported event
- **WHEN** a page cannot admit the complete native event
- **THEN** it returns the exact event offset and a truthful required-size lower bound without advancing coverage past that event; a later supported larger page can admit it before bounded body delivery

#### Scenario: Permanent gap is accepted at close
- **WHEN** a source reports an unknown structure or unproven compaction originals and the executor closes the run accepting that gap with a note
- **THEN** the objective can complete, the next Run on that target does not re-stage the gapped page, and the gap with its note appears in the next inventory and in any view citing that source

#### Scenario: Gap is not accepted
- **WHEN** the executor closes without accepting an outstanding permanent gap
- **THEN** the objective remains pending and the close response names the gapped source and reason
