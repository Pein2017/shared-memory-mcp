## Purpose

Support source-linked low-burden capture and reversible recall curation while preserving canonical history, scientific uncertainty, native memories and independent handoff workflows.

## ADDED Requirements

### Requirement: Optional integrity-bound curation
Records SHALL remain readable Markdown with their accepted body and source list intact. Optional summaries, conditions, topic aliases, source roles, epistemic distinctions and recall metadata SHALL be bound to exact record identity/content and retained with reviewed operation provenance. Malformed, mismatched or unsafe curation SHALL fail closed rather than silently widening visibility.

#### Scenario: Existing record gains routing metadata
- **WHEN** reviewed curation adds metadata to a version-1 record
- **THEN** the original Markdown bytes remain unchanged and the curation operation is idempotently auditable

#### Scenario: Derived summary is the only available account
- **WHEN** curation identifies a source as derivative
- **THEN** it stays derivative after publication and is not counted as independent corroboration

### Requirement: Low-risk capture in one call
An authorized caller SHALL be able to capture a source-linked record with optional reviewed metadata and publish it in one operation call when review evidence is supplied. Without review it SHALL remain a candidate. Idempotent replay SHALL recover the same capture after interruption; changed reuse SHALL fail. Publication SHALL NOT establish scientific truth, change a user decision or grant execution authority.

#### Scenario: Reviewed hypothesis
- **WHEN** a caller captures a hypothesis with a source-check reason and evidence
- **THEN** it becomes eligible for recall but remains a hypothesis

#### Scenario: Interrupted or conflicting replay
- **WHEN** publication was interrupted and the identical source-event key is retried
- **THEN** the original record is recovered without duplication
- **AND** reuse of the key with changed content, metadata or review is rejected

### Requirement: Retirement is not correction
Reviewed retirement SHALL exclude a record from default recall while retaining its original bytes, metadata and evidence links. History reads SHALL disclose retirement separately from candidate, superseded, withdrawn and expired status. Restoring recall eligibility SHALL NOT revive an underlying superseded, withdrawn or expired record. Different experimental conditions or interpretations SHALL be allowed to coexist without mandatory supersession.

#### Scenario: Completed handoff
- **WHEN** a handoff snapshot is retired after checking its durable content and owners
- **THEN** it disappears from default recall, remains explicitly readable as history, and is not declared false

#### Scenario: Superseded record is unretired
- **WHEN** the retirement flag of a superseded record is cleared
- **THEN** the record remains superseded and excluded from default recall

### Requirement: Independent handoff and bounded migration
Migration SHALL enumerate exact input record identities and content fences, record per-item dispositions and source checks, and preserve all original records and research artifacts. It SHALL reuse existing durable records/owners before creating new summaries. Handoff transport, prompts and skills SHALL remain usable independently of memory. Candidate/operational records SHALL remain outside Git; only selected curated routing is eligible for version control.

#### Scenario: Durable result already exists
- **WHEN** a handoff duplicates an existing result or owner
- **THEN** migration links that material and retires the redundant recall snapshot without creating a second result

#### Scenario: Source cannot be verified
- **WHEN** migration cannot read enough primary material for a durable assertion
- **THEN** it preserves the uncertainty and historical record instead of inventing a validated finding

### Requirement: Future organizer boundary
The system SHALL expose record enumeration through bounded search, stable identities, original source references, derivation metadata and idempotent capture/curation suitable for a later independent organizer. This change SHALL NOT start a scheduler, background model extraction or bulk transcript distillation.

#### Scenario: Organizer revisits a source event
- **WHEN** a future authorized organizer submits the same source event again
- **THEN** it can detect or replay the prior record without representing repeated summaries as additional evidence
