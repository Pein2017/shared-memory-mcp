# shared-memory-curation Specification

## Purpose

Support source-linked low-burden capture and reversible recall curation while preserving canonical history, scientific uncertainty, native memories and independent handoff workflows.

## Requirements

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

### Requirement: Ordinary Agent maintenance
Every authorized Agent SHALL be able to create, read, correct and logically delete memory within its permitted scope, including applicable collaboration knowledge and historical accounts. Ordinary maintenance MUST NOT require a Dreaming run, a special curator identity, a separate publisher connection or a human-operated candidate workflow. The supported writes SHALL use the shared MCP/CLI lifecycle.

#### Scenario: Conversational installation-path correction
- **WHEN** the user asks an Agent to correct a remembered installation path and the target and new value are established
- **THEN** the Agent can complete the scoped correction through the common operation and the next eligible read reflects it without waiting for Dreaming or a manual synchronization step

### Requirement: Evidence-preserving admission
Publication SHALL retain original sources, applicability and evidence level. An explicit reusable preference SHALL retain its original scope; an inferred preference SHALL first remain a candidate and any later reviewed publication MUST preserve its inferred status. A hypothesis, derivative summary or repeated Agent report MUST NOT acquire stronger evidence merely through publication.

#### Scenario: One task instruction is not a global preference
- **WHEN** an Agent extracts a request that applies only to the current task
- **THEN** it preserves that applicability instead of silently publishing a permanent global preference

#### Scenario: Inferred preference is subsequently reviewed
- **WHEN** an authorized Agent checks the original sources and publishes an inferred candidate
- **THEN** the result remains labeled inferred with its conditions and does not require a newly invented human approval stage

### Requirement: Disclosed live-conversation source review
An authorized foreground Agent SHALL be able to publish a scoped correction from a direct current user message using explicitly labeled cooperative Agent review. The record SHALL preserve actual caller/session, available original locator, a bounded necessary source excerpt, applicability, review time and method, and disclose unavailable native-history evidence. This basis MUST NOT claim authenticated human identity or operator attestation. Historical, quoted, delegated or ambiguously attributed messages MUST NOT enter this path; historical personal-preference extraction SHALL retain its original-event attribution requirements. Inferred preferences SHALL retain their candidate/review distinction.

#### Scenario: Current user message has not reached readable history
- **WHEN** an authorized foreground Agent directly observes an explicit correction but the native event file or stable message locator is not yet available
- **THEN** it can publish an Agent-reviewed correction with the actual session and observed-message basis, disclose the missing locator, and expose the correction on the next eligible read without inventing an event ID or waiting for Dreaming

#### Scenario: Historical quotation resembles a live instruction
- **WHEN** source text quotes a past user request or carries an ambiguous/delegated user role
- **THEN** the Agent-reviewed live-message path cannot relabel it as a current original instruction or upgrade it to operator-attested evidence

### Requirement: Scoped correction and logical deletion
Corrections SHALL replace only the intended scoped assertion. Withdrawal SHALL remove the item from default recall while retaining authorized recovery and provenance. A withdrawal or reversal MUST NOT implicitly revive superseded predecessors. Derived context SHALL stop presenting withdrawn or corrected content on the next eligible read.

The affected assertion SHALL have an explicit stable scoped unit/claim reference, including for source-only views. All compact/cached renditions SHALL resolve the same correction and withdrawal relationships before delivery. A missing legacy mapping MUST NOT permit a known contrary current assertion to survive as valid; the caller SHALL receive the correction and a bounded mapping/review gap instead of a guessed prose edit.

#### Scenario: Consolidation merges obsolete duplicates
- **WHEN** reviewed duplicate records are replaced with a scoped consolidated account
- **THEN** ordinary recall presents the current account, while superseded history remains available only through the authorized historical path

#### Scenario: Replacement is withdrawn
- **WHEN** the current successor is withdrawn
- **THEN** neither it nor its predecessors silently returns to default recall

### Requirement: Shared concurrency and recovery
Ordinary maintenance and Dreaming SHALL use the same write coordination, expected-revision checks and exact-payload replay semantics. A stale writer MUST NOT overwrite a concurrent correction. An interrupted write SHALL be reconciled from its actual effects before replacement or retry.

#### Scenario: Ordinary correction races a Dreaming draft
- **WHEN** an ordinary Agent corrects an item after a Dreaming draft read it
- **THEN** publication of the stale draft is rejected or explicitly rebased after review without losing the ordinary correction

#### Scenario: Same operation key has different content
- **WHEN** a retry reuses a completed operation key with a different payload
- **THEN** the mutation is rejected rather than treated as the earlier successful operation

### Requirement: Labeled synthesis and discoverable proposals
Dreaming SHALL be able to retain new cross-source connections as labeled hypotheses or inferences and topic-linked notes/proposals. A relevant future Agent SHALL be able to find the unresolved proposal with its sources, distinguish it from accepted knowledge, and record its disposition. Resolution MUST prevent the same handled note from repeatedly appearing as unresolved.

#### Scenario: New interpretation of a historical turning point
- **WHEN** Dreaming infers a connection that was not an explicit historical explanation
- **THEN** it preserves the connection as a new inference rather than rewriting the user's original motive as fact

#### Scenario: Formal research document could be improved
- **WHEN** Dreaming identifies a possible omission or clarification in a formal owner
- **THEN** it leaves a source-linked proposal for a later Agent or the user instead of silently editing the owner, launching another Agent or creating an experiment queue

### Requirement: Proposal consumption respects current authority
A consuming Agent SHALL judge a proposal under the current task's authority and evidence, not the historical author's authority. A user-owned decision outside that scope SHALL remain pending user judgment. Recorded suggestions MUST NOT function as executable instructions.

#### Scenario: Suggested experiment is recalled during a read-only task
- **WHEN** an Agent encounters an unresolved research suggestion while answering a question
- **THEN** it can explain or assess the suggestion but does not treat its presence in memory as permission to execute it

#### Scenario: Proposal observed an older action policy
- **WHEN** current configured actions differ from the proposal's explicit observed action list
- **THEN** search exposes current actions and the difference without rewriting the observation, changing its content revision or automatically disposing the advisory proposal

### Requirement: Task-local durable capture closure
Within an authorized task, the owning Agent SHALL assess meaningful evidence transitions for reusable source-linked capture before task closeout: accepted durable findings, useful negative results, established root causes and explicit scoped corrections. It SHALL reuse or correct relevant existing knowledge instead of duplicating summaries. An unresolved contribution SHALL remain a candidate with its evidence gap and a concrete revisit condition retained in existing content or metadata. Routine progress, elapsed time, candidate count and handoff transport MUST NOT independently require capture or launch consolidation.

#### Scenario: Accepted reusable root cause
- **WHEN** an authorized task establishes a reusable root cause and original evidence is available
- **THEN** the Agent checks existing knowledge and captures or updates the scoped lesson with the actual evidence and limitations before final closeout, without waiting for Dreaming

#### Scenario: Candidate gap becomes actionable
- **WHEN** a relevant task supplies the missing source or discriminating evidence for an existing candidate
- **THEN** the Agent reconsiders that candidate under its current authority; publication preserves its evidence level, while unresolved content remains outside default active recall

#### Scenario: Review changes the proposition
- **WHEN** review requires changing a candidate's claim rather than confirming its original content
- **THEN** the Agent creates a separately reviewed contribution and records the old candidate's appropriate disposition without treating rewritten content as unchanged approval

### Requirement: Decision-bearing extraction with truthful outcomes
Extraction guidance SHALL assess whether a future Agent could make a better concrete decision from the proposed account. No-new-knowledge SHALL be a valid disposition requiring no new memory when material is routine, transient or unchanged without a reusable lesson; it MUST NOT dismiss an existing unresolved review. Where an outcome matters, the Agent SHALL distinguish success, partial, fail and uncertain in existing content or disposition according to original evidence, without adding schema fields or confusing technical execution with scientific acceptance. Checked original corrections and observed owner/tool evidence SHALL take precedence over derivative assistant success claims on the same proposition and scope. Historical, quoted or delegated text, or a `role=user` marker alone, MUST NOT use the direct-current-user correction path. Unsupported conclusions SHALL retain their evidence gap and revisit condition outside accepted compact assertions.

#### Scenario: Routine material and an existing unresolved claim
- **WHEN** an unchanged source contains only routine progress, but a relevant earlier claim still lacks its acceptance evidence
- **THEN** the Agent can capture no new knowledge while retaining the earlier claim's pending disposition and concrete evidence gap

#### Scenario: Original correction follows assistant-reported success
- **WHEN** checked original evidence contains a scoped user correction contradicting an older assistant success summary
- **THEN** the Agent derives the qualified outcome from that evidence, corrects only the contradicted proposition through the granted reviewed lifecycle, preserves unrelated historical results, and does not treat a historical correction as a live current message

#### Scenario: Authorship or acceptance remains unverified
- **WHEN** the source has only a `role=user` marker, assistant self-report or a technical check that does not establish the requested scientific result
- **THEN** the Agent retains the attribution or conclusion gap and revisit condition rather than asserting a verified user decision or successful scientific outcome

#### Scenario: A reusable failure is established
- **WHEN** original evidence establishes a repeatable failure and checks a scoped repair
- **THEN** extraction retains the trigger, conditions, failure and validated repair as a future failure shield, distinguishing an established cause from any remaining hypothesis

### Requirement: Reviewed semantic reuse and absorption
An eligible reviewed memory revision SHALL be usable as a consolidation input without requiring every original raw source to be reread or refrozen for an ordinary merge. Resulting knowledge SHALL retain its actual evidence level, conditions, counterevidence, provenance routes and unresolved gaps; synthesis MUST NOT create stronger evidence. Current-status answers, actions and conclusion corrections SHALL check relevant current owners. Reviewed absorption MAY remove obsolete or redundant predecessors, including research evidence and user corrections, from default recall through the scoped lifecycle while preserving raw sources and recoverable history. Different conditions SHALL remain explicit. An unresolved same-condition conflict MAY become a concise account of its undecided state, essential alternatives and revisit condition without accepting either disputed conclusion. Existing access and publication restrictions SHALL remain in force.

#### Scenario: Accepted history is consolidated without an available raw transcript
- **WHEN** eligible accepted memory contains sufficient qualified information for an ordinary consolidation but its historical raw transcript is unavailable
- **THEN** the exact reviewed memory revision can support synthesis at its existing evidence level without mandatory transcript rereading or an upgrade to independently verified truth

#### Scenario: Research result and correction are absorbed
- **WHEN** reviewed successors retain the needed conditions, lessons and retrieval/source routes of obsolete research accounts or user corrections
- **THEN** eligible predecessors leave default recall through the scoped lifecycle, while raw sources and recoverable historical effects remain intact

#### Scenario: Same-condition conflict remains undecidable
- **WHEN** eligible accounts conflict under the same conditions and available evidence cannot choose between them
- **THEN** a qualified successor can retain that undecided state, decisive alternatives and revisit condition without asserting either disputed claim as accepted

#### Scenario: Absorption cannot be expressed by granted operations
- **WHEN** the current lifecycle/action policy cannot express the required absorption
- **THEN** the exact operational gap remains explicit instead of being bypassed through another write route or incorrectly reported as completed consolidation
