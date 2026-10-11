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
