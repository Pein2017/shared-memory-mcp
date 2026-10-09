## MODIFIED Requirements

### Requirement: Bounded trusted run
The system SHALL bind each Run to stable project/source configuration, an Agent-selected authorized target and source subset, a frozen review objective, real executor, explicit invocation/source bounds and one current Attempt. Objective selection SHALL reuse existing checkpoint/lane protection and MUST NOT create a concurrent replacement for unresolved work. Model input MUST NOT expand authority. Harness and model labels MUST NOT confer privileges or determine who can perform Dreaming. The model-free core SHALL NOT gate continuation by cumulative elapsed time, draft count, repair count or read bytes. Per-transaction verification, payload, operation/object bounds and all source/access/recovery fences SHALL remain enforced. Pi structural scanning SHALL have a separate explicit 128 MiB ceiling with reported I/O, in addition to the 8 MiB event and 16,384 graph-identity bounds; graph capacity SHALL be independent of the 1,024-event page bound and payload page caps SHALL NOT be described as bounding the first full structural scan.

#### Scenario: Stale or impersonated continuation
- **WHEN** a request carries an old generation or a different bound executor
- **THEN** mutation is rejected without changing canonical effects.

#### Scenario: Select another authorized project
- **WHEN** an Agent selects a second target or source set permitted by the effective stable configuration
- **THEN** the selection has its own Run/checkpoint lane and does not implicitly resume or alter the first selection.

#### Scenario: Permission does not follow a harness label
- **WHEN** the same request is made with a different harness label but without the required grant
- **THEN** it remains denied, and no caller-controlled identity, profile or publisher field can enlarge the configured authority.

#### Scenario: Valid review continues beyond historical cumulative settings
- **WHEN** a bound open Run has exceeded the old elapsed, draft, repair or accumulated read setting but has no unresolved replacement-blocking effect
- **THEN** a new individually bounded operation can continue under the same current caller, generation, source/access and replay checks without treating the old cumulative settings as gates

### Requirement: General Agent-operated consolidation
The system SHALL expose authorized discovery, complete retained-memory audit, batch selection and Run lifecycle through the same harness-neutral CLI/MCP integration as ordinary memory. Retained fixed-Run CLI delegation SHALL preserve its scope but MUST NOT require another installed MCP registration. Ordinary memory CRUD SHALL retain its caller-scoped behavior and become available for authorized collaboration/history maintenance without a DreamRun.

#### Scenario: Agent completes a selected batch
- **WHEN** an authorized Agent discovers a source, audits prior memory, selects a target and material, freezes a reviewed draft and publishes it
- **THEN** the ordinary memory consumer observes the resulting canonical change with the actual executor identity and retained source provenance, without requiring a second operator for each batch.

#### Scenario: Advisory execution
- **WHEN** the actual caller/target scope has not been granted publication
- **THEN** it may inspect and draft within its grants but cannot enable publication through model arguments.

### Requirement: Independently invalidated views
Views SHALL publish revisions through fenced current pointers, enforce current source restrictions for default and historical reads, and trim only whole qualified units. Ordinary source drift SHALL preserve usable as-of understanding with review time, source identity and affected-unit freshness markers under shared-memory-recall. Drift MUST NOT certify a remembered current state as freshly verified.

Current caller, target, scenario, cited access dependencies, dispositions, canonical lifecycle and collaboration permissions SHALL be enforced before and after source I/O. Historical receipts SHALL remain unchanged. A migration SHALL validate retained source/dependency bindings before producing a current as-of projection; unknown legacy authority MUST NOT be treated as permitted content. Frozen publication SHALL still validate the exact reviewed basis; tolerant historical consumption MUST NOT allow publication from changed or unreviewed source bytes.

#### Scenario: Unrelated policy edit versus relevant revocation
- **WHEN** an unrelated profile is added or only current resource budgets change
- **THEN** a new view remains readable under current caps.
- **WHEN** relevant access is revoked, including during dependency verification
- **THEN** current and historical reads return no claim text.

#### Scenario: No applicable claims
- **WHEN** an authorized scenario has no applicable view claims
- **THEN** the read returns navigation with available authorized scenarios rather than a valid empty digest.

#### Scenario: Current research selection anchor
- **WHEN** the production current research Overview is refreshed
- **THEN** it links canonical research/index.md plus selected original result owners, records the reviewed closure/stop state and as-of date, and declares omitted branches and partial scope; later ordinary index edits mark affected current-state claims for checking without deleting the dated account.

#### Scenario: Research drift versus privacy withdrawal
- **WHEN** an owner changes normally
- **THEN** the research view retains eligible as-of narrative, marks affected current-state units for an owner check and keeps independent collaboration/background available.
- **WHEN** a dependency is withdrawn or forbidden
- **THEN** neither current nor historical view returns its claim or excerpt.

### Requirement: Caller-per-call persistent bridge
The system SHALL expose persistent caller-per-call ordinary and Dreaming operations through one configured shared-memory gateway. Effective authorization SHALL be resolved from stable project/source configuration and actual caller context, with registered executor authorization, explicit takeover and attempt-generation checks retained. Caller-declared metadata MUST NOT be represented as authenticated native identity. Ordinary schemas SHALL extend the existing operations for the agreed collections/modes; active separate-publisher and dated-profile registrations SHALL be retired through an owned qualified cutover, preserving historical receipts.

#### Scenario: Two Workflow Sessions share one provider
- **WHEN** two permitted executors call the persistent gateway with different actual caller contexts
- **THEN** each effect retains its own caller provenance, calls cannot accidentally inherit the previous caller, and mutation of another current Attempt requires the existing explicit takeover protocol.

#### Scenario: Caller tries to enlarge endpoint grants
- **WHEN** caller context or top-level arguments contain a profile, publication switch, unregistered executor or ungranted target
- **THEN** the request is rejected without canonical effects.

#### Scenario: Production activation qualification
- **WHEN** an authorized WebCodex cutover exposes the unified gateway after its supported configuration transition
- **THEN** the receiving session verifies the single owned registration and actual consumer delivery with its real Workflow Session identity; if a bounded production consolidation is separately requested, it records discovery, inspection, reviewed publication, consumption and closure with its coverage and identity limits. Historical activation does not authorize that production write.


### Requirement: Claims and dispositions
Records and both views SHALL share claim/source admission. Inferred collaboration MUST first be candidate and MUST retain its inferred label after reviewed publication. Scoped rejection and no-use MUST survive backfill. Current direct corrections SHALL use the disclosed cooperative live-conversation review contract in shared-memory-curation; historical personal-preference extraction SHALL retain its original-event attestation requirements. Derived views and subsequent Dreaming reads MUST retain that original assurance label and MUST NOT upgrade Agent-reviewed provenance to operator-attested. A historical excerpt cannot become a live correction merely by passing through a new record.

#### Scenario: Overview bypass
- **WHEN** a draft view cites a pending, refused or revoked claim
- **THEN** it is not activated as usable context.

#### Scenario: Equivalent local file URI
- **WHEN** a source-use prohibition or existing record uses a localhost or percent-encoded alias for the same local file
- **THEN** the restriction still applies without rewriting the record or disposition history and without conflating remote file hosts.

#### Scenario: Audit prohibited collaboration evidence
- **WHEN** a source-ID, URI or lineage prohibition applies to a collaboration record's bound evidence
- **THEN** audit retains inspectable content with an unusable restriction and ordinary evidence admission remains denied; retained direct-event records without source bindings are explicitly unknown and unusable.


### Requirement: Preserve exact record scope during consolidation
Canonical consolidation SHALL support granted project/worktree/task scopes while preserving actual executor provenance. Approval and withdrawal SHALL retain the target qualifier; supersession SHALL require the same qualifier for every predecessor.

#### Scenario: Consolidator acts on another registered worktree's record
- **WHEN** an authorized consolidator approves or withdraws a record in a different worktree or task
- **THEN** the canonical effect retains that record's qualifier and records the consolidator's real caller identity without impersonating the target cwd.

#### Scenario: Approve an ordinary candidate
- **WHEN** an authorized consolidator reviews an ordinary proposed/captured candidate using its exact audited content digest and authorized evidence for every original source under its declared assurance contract, retaining frozen/attested historical evidence or a disclosed current-message review basis as applicable
- **THEN** approval preserves its original canonical payload, sources and provenance, regardless of whether its Markdown was rendered by Dreaming; a digest mismatch, prohibited source or evidence that cannot satisfy its declared assurance contract blocks the effect; a disclosed missing native locator in a permitted live correction is not fabricated historical proof.

#### Scenario: Merge crosses incompatible qualifiers
- **WHEN** a supersession attempts to merge predecessors with different qualifiers
- **THEN** it is rejected; a separately reviewed cross-scope synthesis must be represented as a new claim rather than a false same-scope replacement.


### Requirement: Integrity-bounded incremental continuation
The system SHALL preserve exact source cursors and processing states across bounded Runs, charge prefix verification to source budgets and distinguish unavailable verification from no-change. Semantic continuation SHALL additionally follow shared-memory-history-review: pending review, an unfinished objective or unresolved effects MUST NOT be suppressed by an unchanged source fingerprint. Changing the question SHALL bind a new objective without discarding source-use restrictions or bypassing the existing live lane.

#### Scenario: Read boundary intersects an event
- **WHEN** a byte budget ends inside a normal event
- **THEN** the cursor remains at the beginning of that event and later authorized continuation does not silently drop its remainder.

#### Scenario: Source cannot be reverified
- **WHEN** current source or consumed-prefix verification cannot fit the selected budget
- **THEN** the system returns a gap or blocked partial outcome, not an unchecked no-change or fabricated complete history.
