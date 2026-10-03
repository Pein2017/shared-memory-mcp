## Purpose

Expose one shared-memory contract to Codex CLI and Pi through MCP and native lifecycle adapters while preserving native stores and unrelated configuration. Claude support and actual activation are deferred; retained source is an inactive prototype.

## ADDED Requirements

### Requirement: Shared transport behavior
The CLI, MCP tools, and lifecycle adapters SHALL use the same scope and record semantics. MCP SHALL expose context, search, read, propose, promote, and supersede through a stdio transport. The operator interface SHALL support store initialization, explicit project registration, and diagnostics.

#### Scenario: Cross-harness read/write
- **WHEN** one harness proposes and explicitly promotes an in-scope record through MCP
- **THEN** the other supported harness can retrieve that same canonical ID and provenance through its supported interface

### Requirement: Native startup context
Each of Codex CLI and Pi SHALL have a native adapter that supplies actual session cwd and identity and injects a bounded recalled view on supported startup/resume/compaction boundaries. The adapter SHALL obtain current scope at refresh time and SHALL NOT infer it from the MCP server cwd.

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
Lifecycle adapters SHALL perform recall without automatic transcript/tool extraction, canonical capture, or background model calls. Shared workflow guidance SHALL direct explicit candidate capture at durable decisions, findings, results, root causes, and handoffs and SHALL prohibit treating repeated recalled memory as new independent evidence.

#### Scenario: Ordinary tool activity
- **WHEN** a harness executes routine tools without an explicit propose call
- **THEN** no canonical shared record is created

### Requirement: Graceful unavailability with closed scope
An unavailable or unconfigured memory store SHALL NOT prevent ordinary harness use. A lifecycle adapter SHALL emit empty recall and a bounded diagnostic on scope/store failure; it SHALL NOT inject another project's content as fallback. MCP operations SHALL expose actionable errors.

#### Scenario: Unknown project startup
- **WHEN** a harness starts outside registered projects
- **THEN** it continues normally with no shared project memory and a diagnostic describing the missing binding

### Requirement: Isolated verification before actual activation
The implementation SHALL verify the official stdio MCP interface and both supported installed native adapter paths with isolated store/configuration fixtures, including bounded real GPT-6-Luna sessions in Codex and Pi, before actual activation. The model identifier SHALL be resolved against the live catalog. Actual activation SHALL modify only owned Codex/Pi configuration entries and the single shared skill entry, preserve native memories and unrelated settings, and have a documented narrow rollback. Actual Claude configuration SHALL remain outside the current read/write/activation scope; historical prototype tests SHALL NOT count as current supported-harness acceptance.

#### Scenario: Native memory preservation
- **WHEN** the integration is activated in actual Codex/Pi configurations
- **THEN** existing native memories remain unchanged and fresh-session checks establish the newly configured startup/read path

#### Scenario: Isolated real-model acceptance
- **WHEN** disposable Codex and Pi sessions run with the user-selected GPT-6-Luna
- **THEN** evidence establishes bounded startup recall, correct current session provenance, and explicit shared-memory tool behavior without using real project knowledge as test payload

#### Scenario: Unsupported native runtime
- **WHEN** an installed harness cannot execute the required adapter interface
- **THEN** verification reports that limitation and does not equate mocked envelopes or MCP availability with completed native integration
