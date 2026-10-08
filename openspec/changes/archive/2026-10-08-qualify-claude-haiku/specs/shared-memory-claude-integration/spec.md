## Purpose

Lets native Claude sessions share the existing auditable memory store through bounded startup recall and explicit reviewed capture, without replacing native memory.

## ADDED Requirements

### Requirement: Native Claude context and capture
Claude startup SHALL deliver the shared core's bounded view with actual caller cwd, harness, and session provenance. Native Haiku qualification MUST demonstrate model consumption, candidate capture, explicit promotion, and recall from a fresh session. Shared records SHALL retain their epistemic kind and original sources.

#### Scenario: Native Haiku consumes and publishes shared knowledge
- **WHEN** an isolated Claude Haiku session starts in a registered project and receives synthetic peer records
- **THEN** it reports a startup-only sentinel, reads peer IDs, publishes one reviewed candidate using its actual session context, and a fresh Haiku session recalls the same ID

#### Scenario: Independent peer readback
- **WHEN** independent scoped SDK clients identify as Codex and Pi after Claude publication
- **THEN** both retrieve the same canonical Claude record with matching source, body, lifecycle, and origin session

### Requirement: Optional narrow Claude installation
Claude installation MUST be explicit and idempotent. It SHALL configure only the owned hook and MCP entry, preserve unrelated/native settings and default models, use the existing central store, and create no additional skill copy. A conflicting owned name MUST fail before mutation.

#### Scenario: Explicit activation and repeat
- **WHEN** the operator supplies a Claude configuration directory after isolated qualification
- **THEN** native Claude discovers the six tools, startup resolves the actual project/session, repeated installation creates no duplicates, and unrelated Codex/Pi/Claude settings remain intact

#### Scenario: Claude omitted
- **WHEN** the operator uses the original installer arguments without a Claude directory
- **THEN** installation retains the existing Codex/Pi behavior and accesses no Claude configuration

### Requirement: Bounded and isolated model qualification
Qualification SHALL use the user-selected Haiku model with no model substitution. Test credentials/native memory MUST remain isolated from durable test output and actual native-memory stores. Account/quota failures SHALL stop further paid calls and activation without weakening acceptance.

#### Scenario: Explicit provider failure
- **WHEN** native execution reports account, quota, unavailable model, or permission failure
- **THEN** the result remains a failure with retained evidence; no automatic relaunch, fallback model, or actual activation is performed
