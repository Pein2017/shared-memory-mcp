## Purpose

Exclude transient handoff snapshots from new durable memory without disabling ordinary local document handoff or losing historical audit and recovery integrity.

## ADDED Requirements

### Requirement: No new handoff memory
New handoff proposals, captures and publications SHALL be rejected before publishing new record or capture-binding state. The rejection SHALL explain that local handoff documents remain supported and reusable findings can be captured separately. Other admitted knowledge kinds SHALL retain existing source-review, scope and recovery behavior.

#### Scenario: New handoff capture
- **WHEN** a caller attempts a new handoff capture with or without review
- **THEN** the call rejects it without leaving a candidate or capture receipt

### Requirement: Historical handoff integrity
Historical handoff records SHALL remain decodable, explicitly readable, retireable and withdrawable with original content preserved. Completed identical legacy operation retries SHALL remain replayable; changed payload reuse SHALL conflict. Unfinished historical handoff operations SHALL NOT newly publish or bypass admission through replay.

#### Scenario: Completed versus unfinished legacy operation
- **WHEN** a caller retries a completed legacy handoff operation or attempts to finish an unpublished legacy handoff candidate
- **THEN** the exact completed retry returns its original result, while the unfinished operation is explicitly blocked without changing historical files

### Requirement: Independent local handoff and reviewed capture guidance
Shared workflow guidance SHALL preserve local document handoff independently of memory. It SHALL explain reviewed one-call capture, candidate capture for unresolved interpretation and stable source-event idempotency. Routine progress and whole handoffs SHALL NOT be recommended as durable knowledge.

#### Scenario: Session writes a local handoff
- **WHEN** a session prepares a local document for another session
- **THEN** the workflow remains available without creating a memory entry, and independently reusable findings can be source-reviewed separately
