## MODIFIED Requirements

### Requirement: Low-risk capture in one call
An authorized caller SHALL be able to capture a source-linked record with optional reviewed metadata and publish it in one operation call when review evidence is supplied. Without review it SHALL remain a candidate; this is the only candidate-creation operation. Idempotent replay SHALL recover the same capture after interruption; changed reuse SHALL fail. Capture SHALL scan the record body, title and details for secret-like content and attach a warning notice when found, without rejecting the write. Publication SHALL NOT establish scientific truth, change a user decision or grant execution authority.

#### Scenario: Reviewed hypothesis
- **WHEN** a caller captures a hypothesis with a source-check reason and evidence
- **THEN** it becomes eligible for recall but remains a hypothesis

#### Scenario: Interrupted or conflicting replay
- **WHEN** publication was interrupted and the identical source-event key is retried
- **THEN** the original record is recovered without duplication
- **AND** reuse of the key with changed content, metadata or review is rejected

#### Scenario: Secret-like text in a capture
- **WHEN** a captured body contains a private-key block or an API-token pattern
- **THEN** the record is written, the response carries a `secret_pattern` notice naming the pattern class, and the stored text is unchanged

### Requirement: Retirement is not correction
Reviewed retirement through annotate SHALL exclude a record from default recall while retaining its original bytes, metadata and evidence links. History reads SHALL disclose retirement separately from candidate, stale, superseded, withdrawn and expired status. Restoring recall eligibility SHALL NOT revive an underlying superseded, withdrawn or expired record. Different experimental conditions or interpretations SHALL be allowed to coexist without mandatory supersession.

#### Scenario: Completed handoff
- **WHEN** a handoff snapshot is retired after checking its durable content and owners
- **THEN** it disappears from default recall, remains explicitly readable as history, and is not declared false

#### Scenario: Superseded record is unretired
- **WHEN** the retirement flag of a superseded record is cleared
- **THEN** the record remains superseded and excluded from default recall

### Requirement: Future organizer boundary
The system SHALL expose record enumeration through bounded search, stable identities, original source references, derivation metadata and idempotent capture/annotation suitable for the bounded session extraction defined in shared-memory-session-extraction and for manual Dreaming. Extraction SHALL be the only automatic writer, SHALL produce candidates only, and SHALL NOT run as a scheduler or daemon.

#### Scenario: Organizer revisits a source event
- **WHEN** a future authorized organizer or extraction submits the same source event again
- **THEN** it can detect or replay the prior record without representing repeated summaries as additional evidence

### Requirement: Ordinary Agent maintenance
Every authorized Agent SHALL be able to capture, read, correct, annotate and logically withdraw memory within its permitted scope, including applicable collaboration knowledge and historical accounts. Ordinary maintenance MUST NOT require a Dreaming run, a special curator identity, a separate publisher connection or a human-operated candidate workflow. The supported writes SHALL use the shared MCP/CLI lifecycle under the v0.3 operation names.

#### Scenario: Conversational installation-path correction
- **WHEN** the user asks an Agent to correct a remembered installation path and the target and new value are established
- **THEN** the Agent can complete the scoped correction through capture then supersede and the next eligible read reflects it without waiting for Dreaming or a manual synchronization step

### Requirement: Disclosed live-conversation source review
An authorized foreground Agent SHALL be able to publish a scoped correction from a direct current user message using explicitly labeled cooperative Agent review. The record SHALL preserve actual caller/session, available original locator, a bounded necessary source excerpt, applicability, review time and method, and disclose unavailable native-history evidence. The required fields of this path SHALL remain `excerpt`, `original_locator`, `history_gap` and `review_method`. When the host can change the session identity within one conversation, the locator SHALL identify the transcript file or thread rather than only the session identifier. This basis MUST NOT claim authenticated human identity or operator attestation. Historical, quoted, delegated or ambiguously attributed messages MUST NOT enter this path; historical personal-preference extraction SHALL retain its original-event attribution requirements. Inferred preferences SHALL retain their candidate/review distinction.

#### Scenario: Current user message has not reached readable history
- **WHEN** an authorized foreground Agent directly observes an explicit correction but the native event file or stable message locator is not yet available
- **THEN** it can publish an Agent-reviewed correction with the actual session and observed-message basis, disclose the missing locator, and expose the correction on the next eligible read without inventing an event ID or waiting for Dreaming

#### Scenario: Historical quotation resembles a live instruction
- **WHEN** source text quotes a past user request or carries an ambiguous/delegated user role
- **THEN** the Agent-reviewed live-message path cannot relabel it as a current original instruction or upgrade it to operator-attested evidence

#### Scenario: Host forks the session after the correction
- **WHEN** a Claude conversation continues under a new session identifier after a fork or compaction
- **THEN** the earlier correction's locator still resolves to its transcript file and the correction remains attributed to the same conversation
