## Purpose

Provide auditable shared Markdown knowledge and continuation records with explicit provenance, scoped applicability, validated lifecycle transitions, and reliable local concurrent access.

## ADDED Requirements

### Requirement: Canonical portable records
The system SHALL store each canonical record in one UTF-8 Markdown file with versioned fenced JSON metadata and a readable body. It SHALL preserve ID, kind, scope, origin, source references, timestamps, and review provenance. Native harness memory and formal research records SHALL remain independent.

#### Scenario: Round-trip preserves epistemic role
- **WHEN** a hypothesis with evidence references is proposed, promoted, and read
- **THEN** it remains a hypothesis with its original body, sources, and origin provenance plus separate review provenance

#### Scenario: Unsupported or malformed metadata
- **WHEN** a canonical record has an unsupported schema version or malformed lifecycle metadata
- **THEN** the affected store operation fails explicitly with a diagnostic rather than silently omitting knowledge that could change lifecycle interpretation

### Requirement: Actual caller scope
Every scoped operation MUST receive the actual absolute session cwd and harness/session/actor provenance. A project hint SHALL only assert consistency with resolved scope. Unknown or ambiguous bindings SHALL fail closed without cross-project fallback. A successfully emitted startup view SHALL include the current caller context within its existing output budget so subsequent model-initiated writes can preserve actual session provenance.

#### Scenario: Project hint cannot override cwd
- **WHEN** cwd resolves to project A and a caller hints project B
- **THEN** the operation fails and returns no project B memory

#### Scenario: Missing caller directory
- **WHEN** a scoped request omits cwd
- **THEN** the system rejects it without substituting the server process directory

#### Scenario: Current session differs from remembered origin
- **WHEN** startup recall includes records created in an older session
- **THEN** its caller header identifies the current native session separately from record-origin provenance, allowing subsequent writes to use the current session ID

### Requirement: Registered identity and nested repository isolation
The system SHALL use stable registered project IDs with explicit directory bindings and compatible Git common-directory recognition for linked worktrees. The most-specific explicit registered root SHALL own a registered nested project. Equal-specificity and conflicting bindings SHALL fail closed. An unregistered independent nested Git repository SHALL NOT inherit parent-project memory solely by directory ancestry.

#### Scenario: Linked worktree recognizes the project
- **WHEN** a session starts in a linked worktree of an explicitly registered repository
- **THEN** it resolves to that stable project with its own worktree applicability qualifier

#### Scenario: Nested independent repository
- **WHEN** cwd is inside an unregistered Git repository below a registered parent and its Git identity differs
- **THEN** no parent-project memory is returned

#### Scenario: Aliased directory
- **WHEN** cwd reaches the same registered project subdirectory through a symlink
- **THEN** scope agrees with its canonical realpath and no second knowledge namespace is created

### Requirement: Applicability precedes retrieval limits
The system SHALL support project, worktree, and task applicability. Worktree records SHALL require the same worktree; task records SHALL require the same worktree and task. All scope restrictions SHALL apply before matching, ranking, or limits, including explicit inactive/historical reads.

#### Scenario: Independent worktree continuations
- **WHEN** two worktrees query the same project
- **THEN** both can retrieve applicable project knowledge but neither receives the other's worktree or task records

#### Scenario: Historical read does not widen scope
- **WHEN** a caller requests an out-of-scope ID with inactive records enabled
- **THEN** its contents remain unavailable

### Requirement: Explicit candidate promotion
Capture SHALL initially create a candidate excluded from default recall. Promotion SHALL be a separate explicit operation preserving content and adding nonempty validation reason, evidence references, reviewer identity, session, and time. The shared workflow SHALL designate the main agent or consolidator to validate/promote. Promotion SHALL NOT change kind or imply that an active hypothesis is established fact.

#### Scenario: Candidate is not recalled as accepted knowledge
- **WHEN** an agent proposes a discovery but has not reviewed it
- **THEN** ordinary context/search excludes it while an explicitly requested in-scope inactive read can inspect it

#### Scenario: Evidence-free promotion
- **WHEN** promotion supplies no validation reason or evidence references
- **THEN** the transition fails and the candidate remains unchanged

### Requirement: Durable supersession without evidence loss
The system SHALL supersede knowledge by accepting a successor with explicit predecessor IDs and review reason while retaining predecessor content and provenance. Supersession SHALL require the same project and exact applicability qualifiers and SHALL reject cycles, self-reference, or already superseded targets. Effective lifecycle state SHALL be derived from the full canonical set before retrieval limits. Expiring a successor SHALL NOT reactivate its predecessor.

#### Scenario: Successor outside the returned page
- **WHEN** a query matches an old record but its accepted successor is outside the query/page
- **THEN** the old record is still excluded from default active recall

#### Scenario: Branch-local successor cannot retire project knowledge
- **WHEN** a worktree-scoped candidate attempts to supersede a project-scoped active record
- **THEN** the transition fails without changing either lifecycle state

#### Scenario: Expired replacement
- **WHEN** an accepted successor expires
- **THEN** default recall includes neither the expired successor nor its superseded predecessor

### Requirement: Explicit expiry and progressive recall
Default recall SHALL include only applicable active, nonexpired, nonsuperseded records. Search SHALL return compact identifiers, status, and provenance before full reads. Startup output SHALL obey its total character and count budgets and report omissions. Memory SHALL be presented as contextual data, not instructions overriding user or project authority.

#### Scenario: Budget includes metadata
- **WHEN** a context request sets a small supported character budget
- **THEN** the complete emitted text including wrapper and source/status information remains within it, or returns an empty view when a valid minimal view cannot fit

#### Scenario: Large search matches remain bounded
- **WHEN** matching records contain large bodies or extensive source/provenance metadata
- **THEN** search keeps its serialized core response within 12,000 bytes, preserves complete metadata for returned items, reports omitted bodies/items explicitly, and supplies IDs for full scoped reads without changing startup's whole-record selection

#### Scenario: Expired active record
- **WHEN** an active record's explicit expiry has passed
- **THEN** default recall excludes it and an explicit scoped historical read identifies it as expired

### Requirement: Idempotent and collision-safe writes
Cooperating single-host local-filesystem writers SHALL serialize canonical mutations. A repeated operation key with identical input SHALL resolve to the original result; reuse with different input SHALL fail. Record ID/path collisions SHALL NOT overwrite unrelated content. Writer waits SHALL be bounded and reported explicitly.

#### Scenario: Concurrent identical proposals
- **WHEN** two processes submit the same proposal with the same operation key
- **THEN** exactly one candidate exists and both successful responses identify it

#### Scenario: Conflicting replay
- **WHEN** an already used key is submitted with different content
- **THEN** the system rejects it and retains the original record

### Requirement: Atomic publication and recoverable receipts
A completed write SHALL publish a complete canonical file durably. A crash SHALL leave either the prior valid canonical state or the complete new state. Retry after publication but before receipt completion SHALL recover the published operation without duplication. Operational coordination state SHALL NOT contain canonical knowledge or be misrepresented as disposable search cache.

#### Scenario: Crash after successor publication
- **WHEN** the process stops after publishing the successor and before completing its operation receipt
- **THEN** the next retry recognizes that successor, repairs operational state, and does not publish another record or resurrect the predecessor

#### Scenario: Interrupted temporary write
- **WHEN** the process stops before canonical publication
- **THEN** readers ignore unpublished temporary content and see the prior valid state

### Requirement: Contained storage access
The system SHALL validate IDs and paths and prevent symlink or traversal escapes from the selected data root. Registry updates and canonical writes SHALL use the same cooperating-writer guarantees.

#### Scenario: Escaping record path
- **WHEN** a record ID or symlink would direct a write outside the store
- **THEN** the operation fails without modifying the external target
