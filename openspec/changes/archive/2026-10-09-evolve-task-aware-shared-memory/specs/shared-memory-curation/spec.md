## ADDED Requirements

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
