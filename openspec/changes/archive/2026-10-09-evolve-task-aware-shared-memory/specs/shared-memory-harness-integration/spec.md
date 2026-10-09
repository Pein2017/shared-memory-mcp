## ADDED Requirements

### Requirement: One shared-memory entrypoint
Each supported harness installation SHALL expose ordinary memory and manual Dreaming through one owned `shared-memory` MCP registration. Ordinary callers MUST NOT select dated profiles, open a separate Dreaming connection or enable a publisher role. Effective project/source scope and budgets SHALL remain validated by stable configuration.

#### Scenario: Agent moves from recall to manual consolidation
- **WHEN** the user asks an already connected Agent to perform Dreaming
- **THEN** it can use the same integration and real identity for authorized source discovery and maintenance without another installation or user-managed profile

### Requirement: Common context and declared delivery boundaries
Codex, Pi/Pi Web, WebCodex and the retained Claude integration SHALL consume the same common content contract through their declared delivery surfaces. Native startup/lifecycle paths SHALL deliver eligible background before task-specific retrieval. WebCodex SHALL automatically include it in successful work_on_project and explicit exact-session resume results without an extra memory request or opt-in context selector. Foreground task binding SHALL use substantive user input rather than pretending a startup hook already has it.

#### Scenario: Startup precedes the first task message
- **WHEN** a native startup hook has only caller identity and project scope
- **THEN** it delivers general applicable background with an unbound task mode, and the foreground Agent selects and retrieves task context after the task arrives

#### Scenario: WebCodex has independent native memory
- **WHEN** WebCodex returns a successful normal project-start or exact-session resume result
- **THEN** its final public serialized result carries the external shared-memory packet using the resolved Workflow Session/cwd, independently of native memory bootstrap and without a second memory call

#### Scenario: Host request internals are unavailable
- **WHEN** the server-owned automatic result delivery passes but the external Host exposes no observable final model-request seam
- **THEN** acceptance records server delivery as complete and Host final-request presentation/retention as unverified, without claiming pre-first-tool injection or blocking the other declared delivery surfaces

### Requirement: Actual caller isolation
Every read and mutation SHALL use the consuming Agent's real cwd, harness and session identity. Shared adapters MUST NOT substitute server cwd, a parent Agent's identity or a remembered project to obtain access. Cached context MUST remain isolated by the actual session and authorized scope.

#### Scenario: Two sessions share an MCP process
- **WHEN** two authorized sessions issue overlapping calls for different scopes
- **THEN** each receives its own scoped result and neither can resume or mutate the other's batch by inheriting process state

### Requirement: Bounded lifecycle refresh
Adapters SHALL suppress unchanged duplicate packets and refresh on supported resume, compaction, identity, task-mode and relevant-content transitions. Replacement-capable hosts SHALL keep only their owned active packet parts. Append-only hosts SHALL identify revisions and MUST NOT claim to erase old transcript content or bound the entire historical conversation.

#### Scenario: Pi switches from research to general work
- **WHEN** the foreground binding changes in an existing Pi session
- **THEN** the owned task context is replaced while eligible stable background and unrelated conversation remain intact

#### Scenario: Append-only host receives a correction
- **WHEN** a corrected packet is added to a host that cannot remove earlier messages
- **THEN** the new scope/revision is explicit, the update is not duplicated unchanged, and acceptance does not claim the old message was deleted

### Requirement: Owned cutover and native-store preservation
An authorized installer SHALL converge only the owned integration settings, verify one active registration and retire the old separate Dreaming binding. It MUST preserve unrelated settings, native Codex/Claude/WebCodex memories, existing source records and sealed historical receipts. Qualification MUST NOT require stopping active user sessions.

#### Scenario: Existing client retains an old tool snapshot
- **WHEN** a new integration is installed while an existing session still uses its previous snapshot
- **THEN** the installation reports the need for that client's supported reconnect/lifecycle refresh and does not claim it hot-reloaded or restart another session

### Requirement: Delivery evidence is separate from tool availability
Integration acceptance SHALL inspect the actual serialized content supplied to each declared consumer surface, including budgets and duplicate representations. For WebCodex this SHALL include automatic start/resume output after final public projection; Host model-request observation SHALL be reported separately if available. An installed tool, a successful explicit memory read or generic transport availability alone MUST NOT establish automatic delivery or model-quality benefit.

#### Scenario: Explicit Overview read succeeds but startup is navigation-only
- **WHEN** a consumer can call the research view manually but its startup packet contains no eligible research/background content
- **THEN** explicit reading is qualified separately and automatic content delivery remains incomplete

## MODIFIED Requirements

### Requirement: Owned injection and honest native limits
Pi SHALL replace its owned active packet parts when refreshing context, with at most one stable early bootstrap and one current task packet under the combined budget. Codex installation SHALL register one owned hook per supported lifecycle event, producing one bounded view per invocation without rewriting instruction files. Documentation SHALL state that append-only native context cannot erase prior history or compacted summaries. Local installation SHALL create only one shared skill entry in the existing shared `.codex/skills` directory and SHALL NOT create separate Claude or Pi skill copies.

#### Scenario: Repeated Pi context conversion
- **WHEN** Pi converts context repeatedly after refreshing shared memory
- **THEN** at most one current bootstrap and one current task packet are included, without duplicate exposure or native-history mutation

#### Scenario: Repeated installation
- **WHEN** the installer is run twice
- **THEN** it does not register duplicate owned hooks, MCP entries, or shared skill copies and preserves unrelated configuration

### Requirement: Stable ephemeral Pi recall prefix
Pi SHALL include at most one owned user-level bootstrap snapshot at a stable early
conversation position and at most one separate owned current task packet. Within an unchanged recall and session epoch, appending
ordinary conversation messages SHALL preserve the earlier converted conversation
prefix. Recall SHALL remain ephemeral and refresh at the existing lifecycle and
identity boundaries. Failed refresh SHALL remove the owned recalled snapshot.

#### Scenario: Ordinary continuation
- **WHEN** unchanged recalled content accompanies a conversation and new assistant, tool or user messages are appended
- **THEN** the earlier converted conversation remains a prefix of the later converted conversation
- **AND** only one owned bootstrap and at most one current task packet are present, their combined budget is enforced, and native history is unchanged

#### Scenario: Refresh changes knowledge
- **WHEN** a supported lifecycle refresh supplies new recalled content
- **THEN** the affected current packet part replaces its old snapshot with the actual caller identity
- **AND** freshness is preserved even when replacing the snapshot invalidates cache reuse

#### Scenario: Invalid or unavailable recall
- **WHEN** refresh returns invalid, oversized, unavailable or unmapped recall
- **THEN** the failed or unauthorized packet part is absent and ordinary harness use continues; an ordinary source-freshness change alone preserves eligible as-of context under shared-memory-recall

#### Scenario: Task mode changes without a bootstrap change
- **WHEN** the foreground Agent changes task mode within the same session
- **THEN** the task packet is replaced and unchanged early background retains its position; older native conversation text is not rewritten


### Requirement: Proactive shared workflow guidance
Successful context output SHALL include a fixed source-owned workflow reminder outside the untrusted recalled-record wrapper and within the common serialized context budget, even when a registered project has no matching active records. The shared skill SHALL own proactive task/topic retrieval, meaningful candidate capture, reviewed correction, and delegation guidance. MCP initialization and tool descriptions SHALL provide the workflow entry and operation-specific usage triggers without promising automatic model compliance or server-enforced review roles. Recalled records SHALL NOT supply the operational reminder.

#### Scenario: Empty registered project
- **WHEN** a registered project has no active memory matches
- **THEN** its valid bounded context still exposes the shared workflow entry and actual current caller context, describes missing eligible background honestly, and creates no records

#### Scenario: Required view exceeds budget
- **WHEN** a supported serialized budget cannot hold the reminder and complete scope/caller wrapper
- **THEN** context returns an explicit bounded budget diagnostic instead of misleading empty-success content, exceeding the budget or truncating required metadata

#### Scenario: Delegated worker lacks its own native context
- **WHEN** a worker inherits a parent view but has no actual caller context of its own
- **THEN** guidance directs it to return source-linked candidate content to the lead rather than invent an identity or submit under the parent's session
