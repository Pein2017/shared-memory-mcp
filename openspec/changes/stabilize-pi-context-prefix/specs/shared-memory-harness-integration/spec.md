## Purpose

Provide current, scoped shared recall to native harnesses while preserving
ordinary Pi conversation prefixes, native histories and honest evidence limits.

## ADDED Requirements

### Requirement: Stable ephemeral Pi recall prefix
Pi SHALL include at most one owned user-level recall snapshot at a stable early
conversation position. Within an unchanged recall and session epoch, appending
ordinary conversation messages SHALL preserve the earlier converted conversation
prefix. Recall SHALL remain ephemeral and refresh at the existing lifecycle and
identity boundaries. Failed refresh SHALL remove the owned recalled snapshot.

#### Scenario: Ordinary continuation
- **WHEN** unchanged recalled content accompanies a conversation and new assistant, tool or user messages are appended
- **THEN** the earlier converted conversation remains a prefix of the later converted conversation
- **AND** only one owned recalled snapshot is present and native history is unchanged

#### Scenario: Refresh changes knowledge
- **WHEN** a supported lifecycle refresh supplies new recalled content
- **THEN** one current snapshot replaces the old snapshot with the actual caller identity
- **AND** freshness is preserved even when replacing the snapshot invalidates cache reuse

#### Scenario: Invalid or unavailable recall
- **WHEN** refresh returns invalid, oversized, unavailable or unmapped recall
- **THEN** the owned snapshot is absent and ordinary harness use continues

### Requirement: Honest cache qualification
Documentation SHALL distinguish native CPU prefix correctness from actual
provider cache behavior. A cache improvement claim SHALL identify its measured
model, backend, request population, contrast and raw usage denominator.

#### Scenario: CPU qualification only
- **WHEN** an installed-SDK regression proves a stable converted prefix without provider requests
- **THEN** the result claims prefix correctness and does not claim a measured cache-hit improvement
