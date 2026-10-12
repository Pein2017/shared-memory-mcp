## MODIFIED Requirements

### Requirement: Actual caller scope
Every scoped operation MUST receive the actual absolute session cwd and harness/session/actor provenance as the `caller` argument. The caller MAY additionally declare `role` (lead or worker), `model`, `parent_session_id` and an externally issued `task_id`; these SHALL be retained as origin provenance and MUST NOT widen scope or authority. A project hint SHALL only assert consistency with resolved scope. Unknown or ambiguous bindings SHALL fail closed without cross-project fallback. A successfully emitted startup view SHALL include the current caller context within its existing output budget so subsequent model-initiated writes can preserve actual session provenance.

#### Scenario: Project hint cannot override cwd
- **WHEN** cwd resolves to project A and a caller hints project B
- **THEN** the operation fails and returns no project B memory

#### Scenario: Missing caller directory
- **WHEN** a scoped request omits cwd
- **THEN** the system rejects it without substituting the server process directory

#### Scenario: Current session differs from remembered origin
- **WHEN** startup recall includes records created in an older session
- **THEN** its caller header identifies the current native session separately from record-origin provenance, allowing subsequent writes to use the current session ID

#### Scenario: Worker identity issued by a workbench
- **WHEN** a worker session calls with `role: worker`, `model`, `parent_session_id` and a `task_id` issued by its lead's workbench
- **THEN** its writes record that lineage, task-scope reads require the same worktree and task, and the declared role grants no additional source or publication permission

### Requirement: Explicit candidate promotion
Unreviewed creation SHALL produce a candidate excluded from default recall. A candidate that receives no review, annotation, supersession or withdrawal for seven days SHALL have the effective status `stale`: still searchable with explicit statuses and still approvable; it SHALL leave default recall and SHALL sort after fresh candidates in Dreaming's default triage. Explicit approval SHALL preserve content and add nonempty validation reason, evidence references, reviewer identity, session, and time. An authorized source-checking Agent SHALL also be able to supply that review through the one-call capture contract. Reviewer labels MUST NOT be treated as authenticated roles or expanded authority. Publication SHALL NOT change kind or imply that an active hypothesis is established fact.

#### Scenario: Candidate is not recalled as accepted knowledge
- **WHEN** an agent proposes a discovery but has not reviewed it
- **THEN** ordinary context/search excludes it while an explicitly requested in-scope inactive read can inspect it

#### Scenario: Evidence-free promotion
- **WHEN** promotion supplies no validation reason or evidence references
- **THEN** the transition fails and the candidate remains unchanged

#### Scenario: Candidate ages past seven days
- **WHEN** a candidate has had no lifecycle operation for seven days
- **THEN** status searches report it as `stale`, approval still succeeds with review, and no file is rewritten to record the staleness

### Requirement: Idempotent and collision-safe writes
Cooperating single-host local-filesystem writers SHALL serialize canonical mutations. A repeated operation key with identical input SHALL resolve to the original result; reuse with different input SHALL fail. When a caller omits the key, the system SHALL derive it deterministically from the caller session and the canonical payload and report the derived key in the response. Record ID/path collisions SHALL NOT overwrite unrelated content. Writer waits SHALL be bounded and reported explicitly, and read-only operations SHALL wait a bounded time for a busy coordination database instead of failing immediately.

#### Scenario: Concurrent identical proposals
- **WHEN** two processes submit the same proposal with the same operation key
- **THEN** exactly one candidate exists and both successful responses identify it

#### Scenario: Conflicting replay
- **WHEN** an already used key is submitted with different content
- **THEN** the system rejects it and retains the original record

#### Scenario: Derived key replay
- **WHEN** the same caller session captures the same payload twice without a key
- **THEN** the second call replays the first record and reports the same derived key

#### Scenario: Audit during a Dreaming write
- **WHEN** a status search runs while a Dreaming publication holds the writer gate
- **THEN** the search waits within its bounded time and returns, rather than reporting a locked database

## ADDED Requirements

### Requirement: Task-scope working memory

Task-scope records SHALL default to an explicit expiry of fourteen days when the caller supplies none, and SHALL be included in task context for callers sharing the same worktree and task. Expired task records SHALL remain readable as history. A task record SHALL NOT be promoted to project scope implicitly.

#### Scenario: Team members share a task
- **WHEN** a lead and a worker call with the same issued `task_id` in the same worktree
- **THEN** both receive the task-scope records in their task context, and another task in the same worktree receives none of them

#### Scenario: Default task expiry
- **WHEN** a task record is captured without `expires_at`
- **THEN** it carries an expiry fourteen days after capture and leaves default recall afterwards

### Requirement: Retention without evidence loss

Canonical records, curation journals, capture receipts and sealed Dreaming receipts SHALL never be physically deleted by the system. The operator CLI SHALL provide a prune operation that lists, as a dry run, and on explicit apply removes only: lane markers pointing at closed runs, objective checkpoints no run references, unpublished drafts of closed runs, and configuration backups beyond the newest three. Closing a Dreaming run SHALL clear retained transcript excerpts from its run record while keeping event identities, digests, coverage and publication receipts. Store directories SHALL be created with one consistent private permission, and diagnostics SHALL report deviations.

#### Scenario: Prune dry run
- **WHEN** the operator runs prune without apply
- **THEN** the output lists each removable path with its reason and removes nothing

#### Scenario: Prune never touches canonical content
- **WHEN** prune is applied
- **THEN** every record, journal, receipt, published view revision and issue file remains byte-identical

#### Scenario: Run closes
- **WHEN** a Dreaming run is closed
- **THEN** its retained event text is removed while event keys, digests, coverage and receipts remain, and a later material read reports the text as not retained rather than failing

#### Scenario: Inconsistent directory permission
- **WHEN** a store directory is more permissive than the configured private mode
- **THEN** doctor reports the path and the expected mode
