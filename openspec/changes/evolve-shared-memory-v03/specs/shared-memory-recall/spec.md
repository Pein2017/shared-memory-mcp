## MODIFIED Requirements

### Requirement: Bounded cards with recoverable full material
Search SHALL return relevance cards rather than full audit envelopes. Cards SHALL retain identity, epistemic kind, effective lifecycle status, review assurance, applicable conditions when available, source pointers and explicit disclosure limits. Missing summaries SHALL be presented as previews, not complete claims. Pagination SHALL use one opaque cursor that encodes the corpus snapshot, report omissions and make progress, including oversized records. Full reads SHALL retain original content and provenance; audit detail SHALL remain requestable. Search SHALL also serve the former audit role: an authorized caller MAY filter by effective statuses, including candidate, stale, superseded, expired, withdrawn and retired, and by scope qualifiers, without that visibility implying recall eligibility.

#### Scenario: Long conditional record
- **WHEN** a record cannot fit complete text in a search card
- **THEN** it remains discoverable with a marked preview or compact read pointer, and a full read recovers every original qualifier and source

#### Scenario: Many results or changing corpus
- **WHEN** the caller continues a bounded search with the returned cursor
- **THEN** the response continues the same snapshot, and a cursor from a changed corpus is rejected rather than silently presented as the same snapshot

#### Scenario: Effective-status audit
- **WHEN** an authorized caller searches with statuses `superseded`, `expired` and `stale`
- **THEN** the cards show each record's effective status derived from the full canonical set, and none of them becomes recall-eligible through that read

### Requirement: Harness-friendly MCP contract
The MCP SHALL keep stable tool order and static descriptions, declare read/write effects accurately, preserve actual caller scope, use the uniform envelope and argument conventions of shared-memory-public-interface, and bound both its structured projection and serialized text fallback. Startup adapters SHALL retain their existing identity/failure semantics and the separately implemented stable early Pi prefix. Task-time results SHALL NOT rewrite prior conversation history or tool definitions.

#### Scenario: Ordinary Pi conversation growth
- **WHEN** the recalled navigation is unchanged and ordinary messages are added
- **THEN** the prior converted provider-message prefix remains unchanged under the retained installed-SDK regression

#### Scenario: WebCodex uses the local bridge
- **WHEN** a WebCodex Workflow Session invokes supported memory operations through the CLI
- **THEN** its real harness and session identity are retained rather than impersonating a native Codex session

#### Scenario: Read-only annotation matches behavior
- **WHEN** a client inspects tool annotations
- **THEN** no operation annotated read-only persists state, and `dream_materials` is annotated as recording served material

## ADDED Requirements

### Requirement: Review assurance is visible

Each card, full read and startup unit SHALL carry an `assurance` value derived from retained provenance: `self-reviewed` when the reviewer session equals the author session, `cross-session-reviewed` when a different session reviewed it, `dreaming-reviewed` when a Dreaming publication reviewed it, `model-extracted` for unreviewed extraction candidates, and `candidate` otherwise. Assurance SHALL rank content only when other relevance is equal and MUST NOT block publication or reading.

#### Scenario: Same-session approval
- **WHEN** a record is captured and approved by the same session
- **THEN** its card shows `self-reviewed` and it remains eligible for default recall

#### Scenario: Dreaming re-review
- **WHEN** a later Dreaming run approves or supersedes a self-reviewed record
- **THEN** the effective record shows `dreaming-reviewed` without rewriting the original review receipt
