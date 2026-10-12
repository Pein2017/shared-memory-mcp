## MODIFIED Requirements

### Requirement: Bounded trusted run
The system SHALL bind each Run to stable project/source configuration, an Agent-selected authorized target and source subset, a frozen review objective, real executor, explicit invocation/source bounds and one current Attempt. Objective selection SHALL reuse existing checkpoint/lane protection and MUST NOT create a concurrent replacement for unresolved work. Model input MUST NOT expand authority. Harness and model labels MUST NOT confer privileges or determine who can perform Dreaming. The model-free core SHALL NOT gate continuation by cumulative elapsed time, draft count, repair count or read bytes. The enforced invocation bounds SHALL be exactly `source_bytes`, `events` and `operations`; `drafts`, `seconds`, `repair_rounds`, `view_chars` and `view_bytes` SHALL be documented as retained historical policy fields that are not enforced. Per-transaction verification, payload, operation/object bounds and all source/access/recovery fences SHALL remain enforced. Pi structural scanning SHALL have a separate explicit 128 MiB ceiling with reported I/O, in addition to the 8 MiB event and 16,384 graph-identity bounds; graph capacity SHALL be independent of the 1,024-event page bound and payload page caps SHALL NOT be described as bounding the first full structural scan. The caller-visible attempt fence SHALL be the run `revision` returned by every Dreaming response.

#### Scenario: Stale or impersonated continuation
- **WHEN** a request carries an old run revision or a different bound executor
- **THEN** mutation is rejected without changing canonical effects.

#### Scenario: Select another authorized project
- **WHEN** an Agent selects a second target or source set permitted by the effective stable configuration
- **THEN** the selection has its own Run/checkpoint lane and does not implicitly resume or alter the first selection.

#### Scenario: Permission does not follow a harness label
- **WHEN** the same request is made with a different harness label but without the required grant
- **THEN** it remains denied, and no caller-controlled identity, profile or publisher field can enlarge the configured authority.

#### Scenario: Valid review continues beyond historical cumulative settings
- **WHEN** a bound open Run has exceeded the old elapsed, draft, repair or accumulated read setting but has no unresolved replacement-blocking effect
- **THEN** a new individually bounded operation can continue under the same current caller, revision, source/access and replay checks without treating the old cumulative settings as gates

#### Scenario: Documented budget matches enforcement
- **WHEN** a run is started
- **THEN** its reported budgets list only the three enforced bounds, and a view larger than the historical `view_bytes` field publishes without a budget error

### Requirement: General Agent-operated consolidation
The system SHALL expose authorized discovery, complete retained-memory audit through status-filtered search, batch selection and Run lifecycle through the same harness-neutral CLI/MCP integration as ordinary memory. The historical fixed-Run CLI delegation and the separate dated-profile gateway SHALL be retired; the unified entrypoint is the only Dreaming surface. Ordinary memory CRUD SHALL retain its caller-scoped behavior and become available for authorized collaboration/history maintenance without a DreamRun.

#### Scenario: Agent completes a selected batch
- **WHEN** an authorized Agent discovers a source, audits prior memory, selects a target and material, freezes a reviewed draft and publishes it
- **THEN** the ordinary memory consumer observes the resulting canonical change with the actual executor identity and retained source provenance, without requiring a second operator for each batch.

#### Scenario: Advisory execution
- **WHEN** the actual caller/target scope has not been granted publication
- **THEN** it may inspect and draft within its grants but cannot enable publication through model arguments.

#### Scenario: Fixed-Run delegation is retired
- **WHEN** a caller invokes the historical fixed-Run CLI delegation or the dated-profile gateway
- **THEN** it is reported as retired with a pointer to the unified operations, and no run is created

### Requirement: Source honesty and bounded coverage
Source readers SHALL use pure read-only bounded parsing, distinguish human attribution from role, retain lineage and return explicit gaps rather than fabricated completeness.

Codex public projection admission SHALL validate supported wire structure independently of producer release labels and retain the observed producer version. Known non-message Codex record types that carry no public text, including inter-agent communication metadata, agent-message items and tool-search calls and outputs, SHALL be skipped without a gap. Known Claude navigation and attachment record types, including `attachment`, `relocated` and `continued-in`, SHALL be skipped without a gap and without exposing their payloads. Unknown structures remain explicit gaps. Pi selected evidence SHALL bind complete, unambiguous ancestry through recognized private structural bridge nodes without publishing their payloads. Missing, conflicting or cyclic ancestry, including legacy unproven frozen events, MUST NOT support publication or usable views.

#### Scenario: Pi private bridge or missing ancestor
- **WHEN** a selected public Pi leaf descends through a recognized tool or metadata node to a proven root
- **THEN** the reader may return verified public ancestors without private payloads.
- **WHEN** any ancestor is absent, ambiguous, cyclic or structurally unsupported
- **THEN** a branch gap is retained and no selected suffix becomes publication evidence.

#### Scenario: Producer release update
- **WHEN** a Codex file records a different release but uses the supported public wire projection
- **THEN** its validated messages remain readable with observed release provenance; unknown event structures remain gaps and Claude's selected version contract is unchanged.

#### Scenario: Delegated user-role or unknown schema
- **WHEN** a public message is delegated, quoted, unverified or structurally unsupported
- **THEN** it cannot become an explicit Pein preference, and unsupported input remains a gap.

#### Scenario: Inherited Codex session metadata
- **WHEN** a rollout embeds later session headers after its own first header
- **THEN** its file owner remains unchanged and ambiguous inherited input cannot acquire human attribution through those headers.

#### Scenario: Selected Claude branch
- **WHEN** a Claude leaf is selected
- **THEN** only its verified ancestor chain is usable evidence, and missing or ambiguous ancestry remains a gap rather than admitting another branch.
- **WHEN** no Claude leaf is selected
- **THEN** the public projection is navigation only and cannot support publication.

#### Scenario: Benign native metadata between public messages
- **WHEN** a Codex rollout contains tool-search items or a Claude transcript contains attachment records between two public messages
- **THEN** both public messages are admitted, coverage is complete, and no payload of the skipped records appears in any response

### Requirement: Independently invalidated views
Views SHALL publish revisions through fenced current pointers, enforce current source restrictions for default and historical reads, and trim only whole qualified units. A new revision MAY cite a claim of the immediately previous revision of the same view as evidence by its claim identity, in which case the cited claim's original dependencies, review time and assurance are carried unchanged and the new revision does not refreeze those sources. Ordinary source drift SHALL preserve usable as-of understanding with review time, source identity and affected-unit freshness markers under shared-memory-recall. Drift MUST NOT certify a remembered current state as freshly verified.

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

#### Scenario: Refresh keeps an unchanged claim
- **WHEN** a new revision cites one previous-revision claim unchanged and adds one new claim from freshly frozen sources
- **THEN** the carried claim keeps its original dependencies and review time, the new claim carries the new run's, and revoking a dependency of the carried claim still hides it in both revisions

### Requirement: Integrity-bounded incremental continuation
The system SHALL preserve exact source cursors and processing states across bounded Runs, charge prefix verification to source budgets and distinguish unavailable verification from no-change. The reviewed position of each source and each memory record SHALL be keyed by target project, so that a Run with a new review objective on the same target continues from the previously reviewed position and reviews only material not yet reviewed under that target; an objective MAY explicitly request re-review of a named range. Semantic continuation SHALL additionally follow shared-memory-history-review: pending review, an unfinished objective or unresolved effects MUST NOT be suppressed by an unchanged source fingerprint. Changing the question SHALL bind a new objective without discarding source-use restrictions or bypassing the existing live lane.

#### Scenario: Read boundary intersects an event
- **WHEN** a byte budget ends inside a normal event
- **THEN** the cursor remains at the beginning of that event and later authorized continuation does not silently drop its remainder.

#### Scenario: Source cannot be reverified
- **WHEN** current source or consumed-prefix verification cannot fit the selected budget
- **THEN** the system returns a gap or blocked partial outcome, not an unchecked no-change or fabricated complete history.

#### Scenario: New question on a reviewed target
- **WHEN** a target's sources were fully reviewed under objective A and a Run starts with objective B
- **THEN** the Run's inventory reports those sources as previously reviewed with their position, presents only appended or changed sources and unreviewed memory as pending (a changed source is re-read from its start when the reader cannot resume inside the file), and B can request an explicit re-review range

#### Scenario: Interrupted run resumes
- **WHEN** a Run is closed or abandoned mid-batch and a later Run starts on the same target
- **THEN** reviewed positions advanced by completed publications persist, pending material remains pending, and no reviewed position advances past material that was never served

### Requirement: Repeated bounded frozen-event reading
The existing material-read CLI and the general and gateway MCP calls SHALL permit bounded continuation of one admitted frozen event's complete public text, and SHALL always page: a materials request without an event selection returns a bounded page of event summaries with a cursor, never the whole frozen set. Continuation SHALL retain original event identity, source version and interpretation, revalidate source bytes and current access, and report character intervals, total length and bounded reconstruction I/O. Reads SHALL record which events were served to the current attempt, MUST NOT mark material reviewed, change frozen coverage or expand source/publication authority. After a run is closed, served text MAY be unavailable while identities and digests remain.

#### Scenario: Long owner or historical message
- **WHEN** an admitted event exceeds its retained working excerpt and the caller requests successive bounded parts
- **THEN** their exact concatenation recovers the full frozen public text, including Unicode and trailing caveats, while Run bytes, processing states and coverage remain unchanged.

#### Scenario: Source, interpretation or access changes
- **WHEN** a source is replaced or changed, its public interpretation differs, its grant or applicable disposition is revoked, or a cursor selects another Run/source/event
- **THEN** continuation is rejected without returning substituted text or publishing an effect.

#### Scenario: History gains an unselected suffix
- **WHEN** an exact-prefix history source is appended after collection
- **THEN** continuation may still read its unchanged admitted event at the original cutoff, without reading the new suffix as frozen evidence; epoch-bound catalog pages remain stale.

#### Scenario: Materials without an event selection
- **WHEN** a caller requests materials for a run with ninety-six frozen events and no event selection
- **THEN** the response holds a bounded page within `max_bytes` with a cursor to continue, and no single response exceeds the budget

## ADDED Requirements

### Requirement: Verified coverage within drafts

Coverage marks SHALL be submitted as operations of a draft rather than a separate tool. A mark of `processed`, `excluded` or `no-signal` for an event SHALL be accepted only when that event was served to the current attempt through a materials read, or its complete excerpt was recovered; marks for unserved events SHALL be rejected naming the event. Memory records SHALL be markable after a full read in the same run. Marks SHALL take effect when the draft is published.

#### Scenario: Mark without reading
- **WHEN** a draft marks an event `processed` that no materials read of this attempt served
- **THEN** the draft is rejected with the unserved event key, and no coverage changes

#### Scenario: Marks publish with the draft
- **WHEN** a draft containing marks and record operations is published
- **THEN** coverage and records change atomically with one receipt

### Requirement: Default review objective

When a run is started without a review objective, the system SHALL bind a default objective for the target that inventories, in order: candidates and stale candidates by age, self-reviewed active records not yet re-reviewed by Dreaming, records with identical titles, records whose sources no longer exist, expired active records and unresolved issues; the start response SHALL list those identities so the executor has a concrete deliverable. The default objective SHALL NOT read native history unless the executor adds sources.

#### Scenario: Start without a question
- **WHEN** an executor starts a run on a target with twelve candidates and two duplicate titles and no objective
- **THEN** the response lists the twelve candidate identities with ages and the duplicate pair, and `next` proposes reading the oldest candidate

### Requirement: Server-computed next step

Every Dreaming response SHALL include a `next` object naming the recommended following tool and its complete arguments, including the run id, current revision, cursors and event keys the caller would otherwise transcribe. Following `next` SHALL be optional and SHALL NOT change authority or skip any fence.

#### Scenario: Caller follows next verbatim
- **WHEN** the caller submits exactly the `next` arguments of the previous response
- **THEN** the call succeeds unless the run, source or access changed in between, in which case the diagnostic names the change
