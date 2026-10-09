# shared-memory-dreaming Specification

## Purpose

Support manually selected, source-linked consolidation with bounded public-history access, explicit authority and recoverable canonical publication.
## Requirements
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

### Requirement: Authorized source catalog and bounded page selection
The system SHALL support unified file/directory grants, revision-aware discovery, bounded public-event paging and revalidatable page selections. Traversal, symlink or replacement outside an authorized root MUST be rejected at the actual open boundary. Cursor inputs MUST NOT let callers fabricate parsing state or human attribution.

#### Scenario: History exceeds previous reader lifetime bounds
- **WHEN** supported public history extends beyond 8 MiB or 1,024 event identities
- **THEN** bounded page continuation makes progress with explicit coverage and gaps rather than looping at the old lifetime limit or claiming unchecked completeness.

#### Scenario: Source or grant changes during browsing
- **WHEN** a selected source page, listing or grant changes after observation
- **THEN** stale continuation or publication is rejected, and neither new content nor another path is silently substituted for the frozen selection.

### Requirement: Full authorized historical audit
The consolidator SHALL be able to inspect every retained status and project/worktree/task scope within authorized projects, including lifecycle and curation provenance. Audit SHALL support bounded revision-fenced pagination and explicit reconstructable continuation for oversized records. Audit visibility MUST NOT imply current recall eligibility or admissible publication evidence.

#### Scenario: Inspect a withdrawn or no-reuse record
- **WHEN** an authorized consolidator audits an inactive or source-restricted record
- **THEN** retained content and its restriction are distinguishable, ordinary recall stays restricted, and the record cannot become an active dependency merely because it appeared in audit.

#### Scenario: A later audit page would mix revisions
- **WHEN** canonical or applicability state changes after an audit page
- **THEN** continuation reports a stale revision instead of silently combining different states.

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

### Requirement: Frozen and recoverable publication
The publisher SHALL persist immutable semantic operations and intent before canonical effects, validate basis and policy under one writer gate, and recover using canonical effect evidence rather than Run receipts alone.

#### Scenario: Canonical write precedes receipt crash
- **WHEN** a process fails after a canonical write and a new authorized Attempt resumes
- **THEN** the exact effect is recognized without duplication or rewritten executor provenance.

#### Scenario: Partial publication
- **WHEN** operation A succeeds and B conflicts
- **THEN** A remains effective, B is reported unresolved and no view depending on B activates.

#### Scenario: External promotion before creation receipt
- **WHEN** a candidate creation completes before a crash and another writer promotes that candidate before acknowledgement
- **THEN** unchanged canonical proposal binding and original provenance prove the creation, external approval bytes are preserved, and later operations still require review of the changed basis.

### Requirement: Source honesty and bounded coverage
Source readers SHALL use pure read-only bounded parsing, distinguish human attribution from role, retain lineage and return explicit gaps rather than fabricated completeness.

Codex public projection admission SHALL validate supported wire structure independently of producer release labels and retain the observed producer version. Unknown structures remain explicit gaps. Pi selected evidence SHALL bind complete, unambiguous ancestry through recognized private structural bridge nodes without publishing their payloads. Missing, conflicting or cyclic ancestry, including legacy unproven frozen events, MUST NOT support publication or usable views.

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

### Requirement: Explicit integration qualification
The implementation SHALL report native history, independent Dreamer execution, work-session consumption and enforced restrictions independently for each harness. Fixture tests MUST NOT be called native E2E or production semantic validation.

#### Scenario: A bounded endpoint passes CPU qualification
- **WHEN** synthetic CLI/MCP processes reject unauthorized paths, extra binding fields and raw write tools
- **THEN** the report identifies endpoint-level qualification only and leaves native model execution, native identity, entire harness tool-pool enforcement and production semantic benefit unqualified.

### Requirement: Integrity-bounded incremental continuation
The system SHALL preserve exact source cursors and processing states across bounded Runs, charge prefix verification to source budgets and distinguish unavailable verification from no-change. Semantic continuation SHALL additionally follow shared-memory-history-review: pending review, an unfinished objective or unresolved effects MUST NOT be suppressed by an unchanged source fingerprint. Changing the question SHALL bind a new objective without discarding source-use restrictions or bypassing the existing live lane.

#### Scenario: Read boundary intersects an event
- **WHEN** a byte budget ends inside a normal event
- **THEN** the cursor remains at the beginning of that event and later authorized continuation does not silently drop its remainder.

#### Scenario: Source cannot be reverified
- **WHEN** current source or consumed-prefix verification cannot fit the selected budget
- **THEN** the system returns a gap or blocked partial outcome, not an unchecked no-change or fabricated complete history.

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

### Requirement: Repeated bounded frozen-event reading
The existing material-read CLI and general, gateway and fixed-Run MCP calls SHALL permit bounded continuation of one admitted frozen event's complete public text. Continuation SHALL retain original event identity, source version and interpretation, revalidate source bytes and current access, and report character intervals, total length and bounded reconstruction I/O. Reads MUST NOT mark material reviewed, change frozen coverage or expand source/publication authority.

#### Scenario: Long owner or historical message
- **WHEN** an admitted event exceeds its retained working excerpt and the caller requests successive bounded parts
- **THEN** their exact concatenation recovers the full frozen public text, including Unicode and trailing caveats, while Run bytes, processing states and coverage remain unchanged.

#### Scenario: Source, interpretation or access changes
- **WHEN** a source is replaced or changed, its public interpretation differs, its grant or applicable disposition is revoked, or a cursor selects another Run/source/event
- **THEN** continuation is rejected without returning substituted text or publishing an effect.

#### Scenario: History gains an unselected suffix
- **WHEN** an exact-prefix history source is appended after collection
- **THEN** continuation may still read its unchanged admitted event at the original cutoff, without reading the new suffix as frozen evidence; epoch-bound catalog pages remain stale.
