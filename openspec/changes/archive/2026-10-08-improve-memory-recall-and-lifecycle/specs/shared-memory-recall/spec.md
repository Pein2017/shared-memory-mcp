## Purpose

Help agents discover applicable prior work and its original owners without injecting unrelated history, treating recall as evidence, or breaking harness context stability.

## ADDED Requirements

### Requirement: Stable navigation before task knowledge
The system SHALL render empty-query startup from curated project routing and actual caller identity, without automatically loading historical record bodies, dynamic activity counts or an inferred task. Unknown or ambiguous scope SHALL inject no memory and return a diagnostic. Task-known recall SHALL remain explicitly callable without a mandatory execution gate.

#### Scenario: New session has no task yet
- **WHEN** a registered session requests context without a query
- **THEN** it receives bounded routing and search instructions, not the oldest or newest experiment records
- **AND** adding an unrelated record does not change the startup navigation text for the same caller

#### Scenario: Scope resolution fails
- **WHEN** the caller is outside a unique registered project
- **THEN** startup contains no project data and reports the failure rather than claiming an empty history

### Requirement: Meaningful lexical admission and explainable ranking
Search SHALL admit meaningful word, identifier, CJK or explicitly curated alias matches. Latin character-bigram overlap alone SHALL NOT admit a result. Ranking SHALL distinguish fields, account for common terms and document length, and disclose match reasons. Record age and retrieval frequency SHALL NOT establish validity or retire evidence.

#### Scenario: Unrelated letter fragments
- **WHEN** a query for pytest encounters a record sharing only es, st or te
- **THEN** the record is not returned unless another meaningful query or alias term matches

#### Scenario: Curated multilingual route
- **WHEN** a task uses a configured alias for a topic
- **THEN** search can discover that route and related records while reporting the alias expansion

### Requirement: Bounded cards with recoverable full material
Search SHALL return relevance cards rather than full audit envelopes. Cards SHALL retain identity, epistemic kind, applicable conditions when available, source pointers and explicit disclosure limits. Missing summaries SHALL be presented as previews, not complete claims. Pagination SHALL report omissions and a continuation that makes progress, including oversized records. Full reads SHALL retain original content and provenance; audit detail SHALL remain requestable.

#### Scenario: Long conditional record
- **WHEN** a record cannot fit complete text in a search card
- **THEN** it remains discoverable with a marked preview or compact read pointer, and a full read recovers every original qualifier and source

#### Scenario: Many results or changing corpus
- **WHEN** the caller continues a bounded search
- **THEN** the response exposes the corpus revision and offset so a changed corpus is not silently presented as the same snapshot

### Requirement: Deliberate cross-project engineering reuse
Imported recall SHALL require both an explicit directional project allowlist and an explicit record-level share declaration with engineering domain and project scope. The system SHALL preserve source-project attribution and SHALL NOT allow imported read access to authorize mutation. Research, candidate, retired, worktree and task records SHALL NOT be implicitly imported.

#### Scenario: Both permissions are present
- **WHEN** a published project engineering record is shared to an allowlisted target
- **THEN** task-time search and full read in the target can retrieve it with its original project identity

#### Scenario: One permission is absent
- **WHEN** either project permission or record-level sharing is absent
- **THEN** the foreign record is not returned, even with historical visibility enabled

### Requirement: Harness-friendly MCP contract
The MCP SHALL keep stable tool order and static descriptions, declare read/write effects accurately, preserve actual caller scope, and bound both its structured projection and serialized text fallback. Startup adapters SHALL retain their existing identity/failure semantics and the separately implemented stable early Pi prefix. Task-time results SHALL NOT rewrite prior conversation history or tool definitions.

#### Scenario: Ordinary Pi conversation growth
- **WHEN** the recalled navigation is unchanged and ordinary messages are added
- **THEN** the prior converted provider-message prefix remains unchanged under the retained installed-SDK regression

#### Scenario: WebCodex uses the local bridge
- **WHEN** a WebCodex Workflow Session invokes supported memory operations through the CLI
- **THEN** its real harness and session identity are retained rather than impersonating a native Codex session
