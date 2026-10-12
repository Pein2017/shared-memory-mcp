## MODIFIED Requirements

### Requirement: Explicit semantic capture only
Lifecycle adapters SHALL perform recall and MAY start the bounded session extraction of shared-memory-session-extraction as a detached process at root-session startup; they SHALL NOT perform canonical capture, publish records or call a model within the hook. Shared workflow guidance SHALL direct source-linked capture of durable decisions, findings, results and root causes. Local handoff documents SHALL remain independent; new handoff records and unfinished legacy handoff publication SHALL follow the rejection contract in shared-memory-write-admission. Repeated recalled memory MUST NOT become new independent evidence.

#### Scenario: Ordinary tool activity
- **WHEN** a harness executes routine tools without an explicit memory mutation
- **THEN** no canonical shared record is created

#### Scenario: Hook starts extraction
- **WHEN** a root-session startup hook finds extraction enabled and eligible idle sessions
- **THEN** it returns its recall output within its timeout, the extraction runs detached, and the hook output itself contains no extracted content

### Requirement: Proactive shared workflow guidance
Successful context output SHALL include a fixed source-owned workflow reminder outside the untrusted recalled-record wrapper and within the common serialized context budget, even when a registered project has no matching active records. The shared skill SHALL own proactive task/topic retrieval, meaningful candidate capture, reviewed correction, delegation guidance and the ownership boundary between native harness memories and shared memory. MCP initialization and tool descriptions SHALL provide the workflow entry and operation-specific usage triggers without promising automatic model compliance or server-enforced review roles. Recalled records SHALL NOT supply the operational reminder.

#### Scenario: Empty registered project
- **WHEN** a registered project has no active memory matches
- **THEN** its valid bounded context still exposes the shared workflow entry and actual current caller context, describes missing eligible background honestly, and creates no records

#### Scenario: Required view exceeds budget
- **WHEN** a supported serialized budget cannot hold the reminder and complete scope/caller wrapper
- **THEN** context returns an explicit bounded budget diagnostic instead of misleading empty-success content, exceeding the budget or truncating required metadata

#### Scenario: Delegated worker lacks its own native context
- **WHEN** a worker has no injected caller identity of its own
- **THEN** guidance directs it to return source-linked candidate content to the lead rather than invent an identity or submit under the parent's session

#### Scenario: Delegated worker receives a bounded identity
- **WHEN** a host or workbench injects a bounded caller identity with `role: worker`, `parent_session_id` and `task_id` at worker start
- **THEN** the worker can call `context` and `capture` under that identity, its writes carry the lineage, and it still receives no full background packet from the injection itself

### Requirement: One shared-memory entrypoint
Each supported harness installation SHALL expose ordinary memory and manual Dreaming through one owned `shared-memory` MCP registration under the v0.3 operation names of shared-memory-public-interface. Ordinary callers MUST NOT select dated profiles, open a separate Dreaming connection or enable a publisher role. Effective project/source scope and budgets SHALL remain validated by stable configuration. Harness-side tool exposure lists SHALL be updated to the new names by their owners; the server SHALL NOT serve old names to ease that transition.

#### Scenario: Agent moves from recall to manual consolidation
- **WHEN** the user asks an already connected Agent to perform Dreaming
- **THEN** it can use the same integration and real identity for authorized source discovery and maintenance without another installation or user-managed profile

#### Scenario: Stale exposure list
- **WHEN** a harness exposure list still names a retired operation
- **THEN** that entry resolves to nothing and the harness's own startup diagnostic reports it; the server does not alias it
