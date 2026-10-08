# Design

## Context

The existing candidate has a recoverable publication engine and a fixed-Run endpoint. The clarified product allows any authorized Agent to discover material, audit current and historical memory, select a batch, review and publish it. The ordinary nine-tool memory API retains its task/cwd semantics; Dreaming access is a separately configured capability of the same package and store.

## Goals / Non-Goals

Provide one harness-neutral path from authorized discovery and audit to scoped canonical publication. Preserve source identities, qualifiers, source-use restrictions, original evidence, concurrent writers and interrupted-effect recovery. No new knowledge store, background model runtime, scheduler, transcript mirror or globally atomic multi-project transaction is required.

## Decisions

### Access grants and batch selection

Evolve the unreleased Dreaming policy to version 2. Each profile has `target_projects`, `executor_projects`, `source_grants`, actions and existing resource/scenario limits. A source grant has an ID, absolute path, `kind=file|directory`, format/schema, and required native-version metadata; file grants can retain exact event attestations. This replaces fixed `target_project` and `sources` policy fields rather than adding parallel representations. Ordinary canonical memory remains version 1.

The trusted launcher binds an actual caller, a profile and whether publication is enabled. Harness/model labels never confer authority. The general MCP endpoint lets that Agent select a permitted target and source subset, start/inspect/take over a Run explicitly, freeze/review/publish/close batches, and read views. It cannot rewrite its own grants or caller binding. The fixed-Run endpoint is a wrapper for restricted delegation, not a mandatory second operator. Semantic review may be performed by the authorized executing Agent; it is not a per-record human approval queue.

Keep the selected target and concrete sources in each Run snapshot. Key active/checkpoint lanes by profile plus target plus selected sources/branch/window identity, preventing unrelated projects or batches from resuming one another. Revalidate current grants on every access and before publication. Global work enumerates authorized projects and processes bounded batches independently.

### Discovery, paging and historical audit

Source discovery lists children under a granted file/directory with stable pagination and explicit revision checks. Paths cannot escape a grant through traversal, symlinks or replacement at open time. No source loader executes native sessions. Reading returns public events, original identity, bounded coverage/gaps and a reusable exact selection for a Run. Source paging must make progress past the previous 8 MiB/1,024-event lifetime limits with bounded per-call work. Cursor state and inherited identity must be server-validated; caller-controlled cursors cannot manufacture human attribution. Selected pages are revalidated before becoming publication evidence, and source mutation produces explicit stale/gap results.

Directory traversal checks the identity of the actual opened grant-root descriptor before opening descendants. A paging pass fixes the file epoch, so edits or appends require a new pass. Opaque handles retain bounded parser state and locators, not transcript text; Run selections retain compact reconstruction descriptors. Retrying a retained input cursor returns the same page, including concurrent retries. Handle collection may expire unused capabilities without invalidating an already selected Run descriptor.

The audit entrypoint spans every authorized target, all project/worktree/task qualifiers and all retained statuses. It supports IDs, filters and revision-fenced pagination and includes source, lifecycle and curation history. Audit access is distinct from ordinary recall and evidence admission: historical or no-reuse content may be inspected by the authorized consolidator with an explicit unusable/restricted marker, but cannot silently return to active evidence or ordinary recall. Removing a source access grant still denies that source read. This broader audit behavior is deliberate; ordinary inactive reads keep their existing restrictions.

### Canonical scoped operations

Reuse existing canonical create/approve/supersede/withdraw effects and source admission. Create defaults to project scope and may explicitly identify an authorized registered worktree/task qualifier. Approve/withdraw preserve the target's exact qualifier; supersession requires matching qualifiers for every predecessor. Cross-scope synthesis creates a new appropriately scoped claim with sources; it does not disguise cross-scope references as an ordinary supersession. Persist real executor provenance independently from the target scope.

Every record approval requires the audited `expected_content_digest`. Approval preserves the original canonical payload, sources and provenance, including arbitrary Markdown proposed through ordinary CRUD; it does not require a Dreaming-rendered body. The reviewer must bind each original source URI and any locator to currently authorized frozen events in `checked_refs`. Retired, prohibited, changed or unverifiable candidates remain blocked. Collaboration creation retains compact source bindings through later publication/withdrawal, allowing audit to apply source-ID, URI and lineage restrictions. Legacy direct-event references without bindings remain inspectable but explicitly unusable.

## Persistence and recovery

Use the existing SQLite writer gate and fsync/replace helper. Drafts and per-operation intents are immutable. Each canonical effect contains a stable operation key and semantic digest; Run receipts are secondary. Recovery checks exact planned bytes/effect bindings, preserves the original executor and advances only proven basis changes. Old Attempts fail their generation and bound-caller checks. Conflicts preserve prior successful effects and never resurrect predecessors.

A candidate-create effect remains provable after ordinary external promotion when the full non-lifecycle canonical envelope still matches the intent, including proposal key/digest and original provenance. Acknowledgement preserves external approval bytes and advances only the original intended basis; later operations still require review of the external change. Content similarity alone is insufficient.

Namespace snapshots cover canonical records, curation, collaboration and policy/dispositions. Source reads and model work stay outside the writer gate; external evidence is an as-of snapshot, not a globally atomic promise. View activation has its own pointer fence.

## Source and semantic admission

Pure bounded readers open regular files read-only and never import session loaders. Unknown schema, truncated lines, oversized entries, unavailable originals and ambiguous branches remain gaps. User-role is not human attribution. Only operator-attested event digests support explicit/induced Pein preferences. Source and lineage references remain separate from executor identity. Derived evidence cannot multiply support.

Codex file identity comes from the first session header; embedded later headers cannot replace it or establish human attribution. Claude selected-leaf evidence requires a complete, unambiguous ancestor chain in the current public window. Unselected Claude projection remains navigation only. Local file URI comparison recognizes canonical, localhost and percent-encoded aliases consistently with the existing source reader, without rewriting stored evidence or equating remote file hosts.

Claim units retain evidence level, conditions, exceptions, counterevidence, scope and explicit semantic review. Inferred collaboration starts as a candidate; a later reviewed publication retains its inferred label. Source existence is not semantic entailment. Rejected/no-use material cannot re-enter usable evidence, views or ordinary recall through the broader audit entrypoint.

## Views and limits

Research and collaboration have separate immutable revisions/current pointers. Current dependency loss invalidates historical access as well; ordinary research drift returns stale navigation by default. Budgeting drops whole claims, never their conditions. Empty ordinary memory context remains navigation-only. No-change uses observed source/basis checkpoints and excludes this workflow's own logs/views as experience.

## Delivery qualification

The original fixed-file reader's finite prefix-hash limits remain explicit; general source paging must separately qualify continuation beyond those limits and stale-page rejection. Cross-Run backfill never skips an unfinished bounded event or returns no-change without revalidation. A URI-level source prohibition also applies to existing untagged v1 recall without rewriting records. Source-grant changes prevent cached excerpt reuse. Empty-query routing stays unchanged; optional startup collaboration is a separate explicit opt-in.

Retrieval qualification now fingerprints all recall syntax except the explicitly changed visibility collector; constants/tokenization/ranking/routing/pagination stay frozen against the original baseline. A scoring-mutation test proves that fence still fails for ranking changes. The whole-file difference is separately reported, not hidden. A legacy stdio test explicitly supplies the checkout source path to the SDK's isolated child environment instead of requiring runtime installation.


First qualify an actual CLI/stdio caller that discovers a source, audits historical memory, starts a selected batch, publishes a scoped change and observes it through the ordinary consumer. Add denial, stale pagination, alternate-target lanes and interruption controls before expanding checks. Report source parsing, native independent execution, work-session consumption and enforcement separately. CPU transport tests prove endpoint behavior, not an entire installed native tool pool or model judgment.

## Migration and risks

Policy v2 is a clean cutover of the unactivated candidate: migrate maintained fixture/config examples, reject old Dreaming policy explicitly, and preserve previous qualification outputs and canonical v1 records. Do not activate or migrate a live store in this task. Bounded public projections cannot recover unknown schemas, private/unpersisted content or deleted source versions; report gaps. An audit grant enables inspection, not factual certification. Discovery/listing revisions and per-Run publication fences handle concurrent changes without a global lock during source I/O.

## Persistent MCP gateway activation (2026-10-08)

A Runner-wide static provider cannot carry one actual Workflow Session identity for all users of that connection. A separate `dream gateway --profile PROFILE [--enable-publisher]` endpoint therefore accepts required ordinary `CallContext` in each general tool call. It constructs a fresh Dreaming executor for that call and reuses existing profile ACL, target/source admission, Run ownership, explicit takeover and generation checks. Profile, publisher and policy editing remain absent from tool arguments. Context is caller-declared provenance, not authenticated native identity; startup validates the configured policy/profile without inventing a caller. Gateway-created and taken-over attempts disclose this assurance level.

The production setup adds a separate provider under the existing WebCodex MCP gateway. It does not replace ordinary memory or change WebCodex protocol/core. A fenced config check/reload must prove the new provider is live while preserving the ordinary provider and avoiding service restart. Pilot publication uses one bounded claim derived from an exact registered-project documentation source, observes it through ordinary memory and closes the Run; it is operational qualification, not semantic improvement or whole-history acceptance.

## Frozen material continuation (2026-10-08)

Keep the bounded 4096-character working excerpt and its historical coverage receipt. An explicit event key on the existing material-read path selects only an event already admitted to that Run. Reconstruct its full public text from the exact frozen source, compare source version and interpretation metadata, and return a bounded character slice with its original evidence identity. A prefixed string cursor binds Run/source/event/version/text digest and position; the prefix prevents the installed MCP SDK from converting JSON-looking strings into argument objects. Return the cursor unchanged on continuation, with an explicit interval, total length and reconstruction/verification byte costs.

Source reads remain outside the writer gate. Current caller/target, grant and source-use restrictions are checked before reading and again before return; changed bytes, replacement, changed interpretation or revoked access cannot substitute another event. Reading has no persisted effect on Run bytes, processed states, review or coverage. Full availability is separate from semantic review, verified ancestry and whole-history coverage. Current reconstruction repeats bounded source I/O per page; do not add a transcript cache or reading ledger for the approximately 10 KiB audited owners.

The requested read-only Astra consultation supports this decision. Its other recommendations remain proposals: verify Pi's structural chain before public projection and do not admit incomplete suffixes; qualify native producer formats separately from release labels; scope view authorization invalidation while retaining live revocation checks; use canonical research/index.md as the current-overview selection anchor and open selected result owners. None is implemented or activated by this material-reading follow-up.

## Authorized consolidation corrections (2026-10-08)

The user subsequently authorized those four corrections. Pi evidence must bind the complete selected chain of recognized raw node identities and parents, including private bridge nodes without their payloads. Missing, cyclic, conflicting or unknown ancestry supplies navigation/gaps, never a publishable suffix. Catalog reconstruction must enforce the same contract, including unsafe descriptors produced by the earlier parser.

For Codex, the explicitly selected public wire projection is the parser contract; the observed producer release is provenance rather than a global release pin. This admits known historical public message shapes without treating arbitrary new structures as understood. Claude's explicitly versioned contract remains unchanged. No native loader, package downgrade or unbounded transcript recovery is introduced.

New view revisions retain the full policy revision for audit and bind the authorization dependencies that affect their actual sources and consumers. Read checks still verify current caller, target, scenario, cited grants and attestations, dispositions, canonical lifecycle, collaboration scope and a second authorization check after source I/O. Unrelated profiles and resource-budget edits do not invalidate usable context. Existing immutable revisions retain their original fail-closed contract; republishing is explicit. A scenario with no applicable claims returns useful navigation instead of a misleading valid empty result.

The current research Overview binds the canonical research/index.md snapshot for selection, closure and stop state, and reads selected original result owners for substantive claims. It states its omitted branches and partial scope. Neither this view nor refreshed memory authorizes research execution or changes scientific decisions. No source-owner edits, GPU work, paid-model execution, service restart or Git publication are part of this correction.
