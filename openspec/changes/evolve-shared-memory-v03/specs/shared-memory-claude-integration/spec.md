## MODIFIED Requirements

### Requirement: Native Claude context and capture
Claude startup SHALL deliver the shared core's bounded view with actual caller cwd, harness, and session provenance on the documented startup, resume, clear, compact and fork sources. Claude Agent-tool subagents SHALL receive, through the documented subagent-start injection, a bounded caller identity carrying the parent session, the subagent identifier as the worker session, `role: worker`, the agent type and any task identity, without the full background packet. Qualification SHALL distinguish native request delivery, explicit reviewed capture and actual model consumption. The archived Haiku trial records the completed bounded real-model case; it MUST NOT imply unmeasured resume/compaction/fork behavior or authorize another paid trial. Shared records SHALL retain their epistemic kind and original sources. Because a Claude conversation can continue under new session identifiers after fork or compaction, extraction and live corrections SHALL locate evidence by transcript file, not session identifier alone.

#### Scenario: Native Haiku consumes and publishes shared knowledge
- **WHEN** a separately authorized isolated Claude Haiku qualification session starts in a registered project and receives synthetic peer records
- **THEN** it reports a startup-only sentinel, reads peer IDs, publishes one reviewed candidate using its actual session context, and a fresh Haiku session recalls the same ID

#### Scenario: Independent peer readback
- **WHEN** independent scoped SDK clients identify as Codex and Pi after Claude publication
- **THEN** both retrieve the same canonical Claude record with matching source, body, lifecycle, and origin session

#### Scenario: Subagent starts
- **WHEN** the Agent tool spawns a subagent in a registered project
- **THEN** the subagent-start hook emits a bounded caller identity under the common serialized budget, the subagent's capture records `role: worker` and the parent session, and no startup packet is duplicated into the subagent

#### Scenario: Session identity changes mid-conversation
- **WHEN** a fork or compaction continues the conversation under a new session identifier
- **THEN** startup recall is delivered again for the new identifier, and extraction later attributes both transcript files to the same conversation lineage through their recorded parent links

## ADDED Requirements

### Requirement: Claude history reader coverage

The Claude transcript reader SHALL admit `user` and `assistant` messages of the configured native versions, skip `attachment`, `relocated`, `continued-in` and other known versionless navigation records without exposing their payloads, retain compaction boundaries as unproven-original gaps, and read subagent transcripts under a session's subagent directory as delegated events with their agent identifier. A history root MAY list several native versions.

#### Scenario: Current transcript with attachments
- **WHEN** a transcript of the configured version contains attachment records between public messages
- **THEN** every public message is admitted, coverage is complete and no attachment payload is returned

#### Scenario: Subagent transcript
- **WHEN** a session directory contains subagent transcripts
- **THEN** listing discovers them, reading marks their events delegated with the agent identifier, and they cannot become direct user preferences

#### Scenario: Mixed versions under one root
- **WHEN** a root lists two native versions and contains transcripts of both
- **THEN** both are readable with their actual version retained, and a third version remains an explicit gap
