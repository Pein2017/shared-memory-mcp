## Purpose

Evaluate retrieval against task-relevant original sources and correctly distinguish historical memory creation from current recall eligibility.

## ADDED Requirements

### Requirement: Source-conditioned retrieval cases
Qualification SHALL retain explicit task questions, original source pointers, expected useful targets, nearest distractors and applicability reasons across entity, version, negative-result, CJK/alias, derivative-source and isolation cases. Ranking defaults SHALL remain unchanged by this change. Reports SHALL disclose misses and limitations; truncation or lexical overlap alone SHALL NOT establish retrieval quality.

#### Scenario: Same topic with different conditions
- **WHEN** qualification retrieves a target, a condition-mismatched result and a relevant negative result
- **THEN** it evaluates them using task/source applicability rather than treating matching topic words or preferred conclusions as truth

### Requirement: Retirement-aware lifecycle reporting
Read-only reporting SHALL distinguish records created in a selected time window from their current curation-aware recall status, including retired, candidate, superseded and withdrawn history. Historical creation SHALL NOT imply active recall. Original audit receipts SHALL be preserved when appending corrections.

#### Scenario: Historical handoff creation after retirement
- **WHEN** an audit window contains handoff records created before their retirement
- **THEN** reporting counts their creation events separately and does not count those retired records as currently recallable knowledge
