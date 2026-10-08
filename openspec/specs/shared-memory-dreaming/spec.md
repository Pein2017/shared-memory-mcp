# shared-memory-dreaming Specification

## Purpose

Support manually selected, source-linked consolidation with bounded public-history access, explicit authority and recoverable canonical publication.

## Requirements

### Requirement: Bounded trusted run
The system SHALL bind each Run to a trusted profile, an Agent-selected authorized target and source subset, real executor, explicit source/provider budgets and one current Attempt. Model input MUST NOT expand authority. Harness and model labels MUST NOT confer privileges or determine who can perform Dreaming.

#### Scenario: Stale or impersonated continuation
- **WHEN** a request carries an old generation or a different bound executor
- **THEN** mutation is rejected without changing canonical effects.

#### Scenario: Select another authorized project
- **WHEN** an Agent selects a second target or source set permitted by its bound profile
- **THEN** the selection has its own Run/checkpoint lane and does not implicitly resume or alter the first selection.

#### Scenario: Permission does not follow a harness label
- **WHEN** the same request is made with a different harness label but without the required grant
- **THEN** it remains denied, and no caller-controlled identity/profile field can enlarge the bound endpoint's authority.

### Requirement: General Agent-operated consolidation
The system SHALL expose authorized discovery, complete retained-memory audit, batch selection and Run lifecycle through one harness-neutral CLI/MCP workflow. The fixed-Run endpoint SHALL remain an optional delegated mode. Ordinary memory CRUD SHALL retain its existing caller-scoped behavior.

#### Scenario: Agent completes a selected batch
- **WHEN** an authorized Agent discovers a source, audits prior memory, selects a target and material, freezes a reviewed draft and publishes it
- **THEN** the ordinary memory consumer observes the resulting canonical change with the actual executor identity and retained source provenance, without requiring a second operator for each batch.

#### Scenario: Advisory execution
- **WHEN** an endpoint has not been granted publication
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
- **WHEN** an authorized consolidator reviews an ordinary proposed/captured candidate using its exact audited content digest and authorized frozen evidence for every original source
- **THEN** approval preserves its original canonical payload, sources and provenance, regardless of whether its Markdown was rendered by Dreaming; a digest mismatch, prohibited source or unverifiable locator blocks the effect.

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
Records and both views SHALL share claim/source admission. Inferred collaboration MUST first be candidate and MUST retain its inferred label after reviewed publication. Scoped rejection and no-use MUST survive backfill.

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
Views SHALL publish immutable revisions through fenced current pointers, enforce current source restrictions for both default and historical reads, and trim only whole claims.

New revisions SHALL retain global policy audit provenance while binding read usability to relevant authorization dependencies. Current caller, target, scenario, cited grants and attestations, dispositions, canonical lifecycle and collaboration permissions SHALL be enforced before and after source I/O. Legacy revisions retain their original fail-closed policy contract.

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
- **THEN** it binds canonical research/index.md plus selected original result owners, preserves their current closure and stop state, and declares omitted branches and partial scope; changed index bytes make the snapshot stale.

#### Scenario: Research drift versus privacy withdrawal
- **WHEN** an owner changes normally
- **THEN** the research view returns stale navigation without invalidating collaboration.
- **WHEN** a dependency is withdrawn or forbidden
- **THEN** neither current nor historical view returns its claim or excerpt.

### Requirement: Explicit integration qualification
The implementation SHALL report native history, independent Dreamer execution, work-session consumption and enforced restrictions independently for each harness. Fixture tests MUST NOT be called native E2E or production semantic validation.

#### Scenario: A bounded endpoint passes CPU qualification
- **WHEN** synthetic CLI/MCP processes reject unauthorized paths, extra binding fields and raw write tools
- **THEN** the report identifies endpoint-level qualification only and leaves native model execution, native identity, entire harness tool-pool enforcement and production semantic benefit unqualified.

### Requirement: Integrity-bounded incremental continuation
The system SHALL preserve exact source cursors and processing states across bounded Runs, charge prefix verification to source budgets and distinguish unavailable verification from no-change.

#### Scenario: Read boundary intersects an event
- **WHEN** a byte budget ends inside a normal event
- **THEN** the cursor remains at the beginning of that event and later authorized continuation does not silently drop its remainder.

#### Scenario: Source cannot be reverified
- **WHEN** current source or consumed-prefix verification cannot fit the selected budget
- **THEN** the system returns a gap or blocked partial outcome, not an unchecked no-change or fabricated complete history.

### Requirement: Caller-per-call persistent bridge
The system SHALL provide a separately launcher-configured general gateway whose tools require the current caller context, while fixing the profile and publisher capability outside tool arguments. It SHALL reuse registered executor authorization, explicit takeover and attempt-generation checks. Caller-declared metadata MUST NOT be represented as authenticated or operator-verified native identity. Existing bound endpoint caller/authority contracts and ordinary endpoint schemas SHALL remain unchanged.

#### Scenario: Two Workflow Sessions share one provider
- **WHEN** two permitted executors call the persistent gateway with different actual caller contexts
- **THEN** each effect retains its own caller provenance, calls cannot accidentally inherit the previous caller, and mutation of another current Attempt requires the existing explicit takeover protocol.

#### Scenario: Caller tries to enlarge endpoint grants
- **WHEN** caller context or top-level arguments contain a profile, publication switch, unregistered executor or ungranted target
- **THEN** the request is rejected without canonical effects.

#### Scenario: Production activation qualification
- **WHEN** the configured WebCodex provider exposes the general gateway after a fenced reload
- **THEN** an actual bounded production slice records discovery, source and memory inspection, reviewed publication, ordinary-memory consumption and Run closure, while preserving ordinary memory registration and reporting caller identity limits.

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
