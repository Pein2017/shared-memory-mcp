## ADDED Requirements

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
