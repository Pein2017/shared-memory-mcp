# shared-memory-harness-integration Specification

## Purpose

Expose shared-memory scope and lifecycle semantics through MCP, CLI and native Codex/Pi adapters, with separately qualified optional Claude integration, while preserving native stores and unrelated configuration.

## Requirements

### Requirement: Shared transport behavior
The CLI, MCP tools, and lifecycle adapters SHALL use the same scope and record semantics. The ordinary stdio MCP SHALL expose the direct operations defined in shared-memory-public-interface. The operator interface SHALL support store initialization, explicit project registration, and diagnostics.

#### Scenario: Cross-harness read/write
- **WHEN** one harness proposes and explicitly promotes an in-scope record through MCP
- **THEN** the other supported harness can retrieve that same canonical ID and provenance through its supported interface

### Requirement: Native startup context
Each of Codex CLI and Pi SHALL have a native adapter that supplies actual session cwd and identity and injects the common bounded startup view on supported startup/resume/compaction boundaries. Empty-query content SHALL follow shared-memory-recall. The adapter SHALL obtain current scope at refresh time and SHALL NOT infer it from the MCP server cwd. Optional Claude behavior SHALL follow shared-memory-claude-integration.

#### Scenario: Server and session directories differ
- **WHEN** the MCP process starts in the package directory while the harness session starts in a registered worktree
- **THEN** startup memory is scoped to the harness worktree

#### Scenario: Resume after knowledge changes
- **WHEN** a session resumes after applicable canonical knowledge changes
- **THEN** the adapter requests a fresh bounded view rather than permanently suppressing it by session/record ID

### Requirement: Owned injection and honest native limits
Pi SHALL replace its owned memory message when refreshing context. Codex installation SHALL register one owned hook per supported lifecycle event, producing one bounded view per invocation without rewriting instruction files. Documentation SHALL state that append-only native context cannot erase prior history or compacted summaries. Local installation SHALL create only one shared skill entry in the existing shared `.codex/skills` directory and SHALL NOT create separate Claude or Pi skill copies.

#### Scenario: Repeated Pi context conversion
- **WHEN** Pi converts context repeatedly after refreshing shared memory
- **THEN** at most one current owned memory message is included

#### Scenario: Repeated installation
- **WHEN** the installer is run twice
- **THEN** it does not register duplicate owned hooks, MCP entries, or shared skill copies and preserves unrelated configuration

### Requirement: Explicit semantic capture only
Lifecycle adapters SHALL perform recall without automatic transcript/tool extraction, canonical capture, or background model calls. Shared workflow guidance SHALL direct source-linked capture of durable decisions, findings, results and root causes. Local handoff documents SHALL remain independent; new handoff records and unfinished legacy handoff publication SHALL follow the rejection contract in shared-memory-write-admission. Repeated recalled memory MUST NOT become new independent evidence.

#### Scenario: Ordinary tool activity
- **WHEN** a harness executes routine tools without an explicit memory mutation
- **THEN** no canonical shared record is created

### Requirement: Proactive shared workflow guidance
Successful context output SHALL include a fixed source-owned workflow reminder outside the untrusted recalled-record wrapper and within the existing total character budget, even when a registered project has no matching active records. The shared skill SHALL own proactive task/topic retrieval, meaningful candidate capture, reviewed correction, and delegation guidance. MCP initialization and tool descriptions SHALL provide the workflow entry and operation-specific usage triggers without promising automatic model compliance or server-enforced review roles. Recalled records SHALL NOT supply the operational reminder.

#### Scenario: Empty registered project
- **WHEN** a registered project has no active memory matches
- **THEN** its valid bounded context still exposes the shared workflow entry and the actual current caller context without creating records

#### Scenario: Required view exceeds budget
- **WHEN** a supported character budget cannot hold the reminder and complete scope/caller wrapper
- **THEN** context returns empty text with a diagnostic instead of exceeding the budget or truncating required metadata

#### Scenario: Delegated worker lacks its own native context
- **WHEN** a worker inherits a parent view but has no actual caller context of its own
- **THEN** guidance directs it to return source-linked candidate content to the lead rather than invent an identity or submit under the parent's session

### Requirement: Graceful unavailability with closed scope
An unavailable or unconfigured memory store SHALL NOT prevent ordinary harness use. A lifecycle adapter SHALL emit no recalled project content and a bounded actionable diagnostic on scope/store failure, including onboarding guidance when available; it SHALL NOT inject another project's content or register a project as fallback. MCP operations SHALL expose actionable errors.

#### Scenario: Unknown project startup
- **WHEN** a harness starts outside registered projects
- **THEN** it continues normally with no shared project memory and a diagnostic describing the missing binding

### Requirement: Isolated verification before actual activation
Changed integrations SHALL be qualified through official stdio MCP and affected installed native adapter paths with isolated store/configuration fixtures before authorized activation. Actual activation SHALL modify only owned entries and the single shared skill entry, preserve native memories and unrelated settings, and have a documented narrow rollback. Optional Claude activation SHALL follow its qualified contract. Historical selected-Luna/Haiku runs SHALL remain dated evidence, not permanent model defaults or permission for new paid calls. Any new real-model qualification SHALL use a separately authorized, currently available user-selected model and bounded scope.

#### Scenario: Native memory preservation
- **WHEN** the integration is activated in actual Codex/Pi configurations
- **THEN** existing native memories remain unchanged and fresh-session checks establish the newly configured startup/read path

#### Scenario: Isolated real-model acceptance
- **WHEN** separately authorized disposable Codex and Pi real-model sessions run with the model selected for that qualification
- **THEN** evidence establishes bounded startup recall, correct current session provenance, and explicit shared-memory tool behavior without using real project knowledge as test payload

#### Scenario: Unsupported native runtime
- **WHEN** an installed harness cannot execute the required adapter interface
- **THEN** verification reports that limitation and does not equate mocked envelopes or MCP availability with completed native integration

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
