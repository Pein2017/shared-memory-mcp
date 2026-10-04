## Context

See proposal.md for motivation and scope. The package started with only an initialized local OpenSpec root and no existing implementation or capability specs. The current user ruling approves supported implementation and actual activation for Codex and Pi after isolated acceptance; Claude is deferred. Native stores remain independent.

The user resolved the consequential choices: agents first propose candidates and then explicitly validate/promote; capture occurs at meaningful workflow transitions without automatic transcript extraction or background model calls; real Codex/Pi validation uses the user-selected GPT-6-Luna, and only their actual configurations are enabled after isolated acceptance. The model identifier/route is resolved from the live catalog before bounded validation. Existing Claude adapter code and prior isolated evidence are historical prototype work, not current support or activation evidence. These rulings supersede the generic planning-only instruction in the imported proposal skill.

The independent architecture advisor recommended Python plus the official MCP SDK, a local SQLite transaction gate for cooperating writers, and immutable successor relationships. The core owner adopts those recommendations for their lower operational burden; a SQLite coordination database is durable operational state, not a disposable search cache.

## Goals / Non-Goals

**Goals:** One canonical source shared by all harnesses; reliable scope and lifecycle semantics behind one small interface; auditable provenance; bounded startup recall; retry-safe local writes; portable source and configurable data paths.

**Non-Goals:** Multi-host/NFS writers, remote authentication, embeddings, semantic extraction services, automatic truth adjudication, automatic Git commits, native-memory synchronization, automatic code checkout relocation, and legacy memory-skill deletion. Support claims cover the current Linux local filesystem deployment; wider portability requires later validation.

## Decisions

### 1. One core and thin adapters

Use Python >=3.11 and package `shared_memory_mcp`. The core depends on the standard library; the stdio MCP transport uses the official Python MCP SDK (installed baseline 1.27.1). CLI, MCP, and hooks call the same `MemoryStore(root)` interface. No daemon is needed: each harness can start its own stdio process over the same store.

Separate implementation into a small number of modules for canonical records/persistence, context resolution, recall, and adapters. These are internal modules in one package, not independently deployed services. Pi's extension remains a thin TypeScript adapter because its native extension interface requires that language.

The data root is a required/configured deployment value; the initial local value is `/data/CoordExp/.shared-memory/`. Portable code exposes `--root` or `SHARED_MEMORY_ROOT`. The implemented store layout is:

```text
registry.json
records/<project-id>/<record-id>.md
.writer-gate.sqlite3        # persistent local writer coordination; not a search cache
.state/                    # installation backups and configured adapter entrypoints
```

The source package is independent of this data tree. Optional search caches can be added later and must never become knowledge authority. Initial recall scans the selected canonical corpus with deterministic lexical ranking.

### 2. Frozen core request interface

Every scoped operation receives a `context` object:

```json
{"cwd":"/absolute/actual/session/directory","harness":"codex","session_id":"session-id","actor":"main-agent","task_id":"optional-task","project_id":"optional-consistency-hint"}
```

`cwd`, `harness`, `session_id`, and `actor` are required nonempty values. Supported deployed harnesses are `codex` and `pi`; the core retains the `claude` provenance token for the inactive prototype and historical records without claiming current native support. `cwd` must exist and resolve as a directory. `project_id` is a consistency assertion, never an override. Missing context fails rather than defaulting to the MCP process cwd. Actor/session fields are provenance supplied by cooperating callers, not authenticated identity; designated-consolidator behavior is an explicit workflow policy, not a claimed multi-user authorization system.

Methods and MCP tool names:

```text
context(context, query="", limit=8, max_chars=6000)
search(context, query, limit=20, include_inactive=false)
read(context, ids, include_inactive=false)
propose(context, record, idempotency_key)
promote(context, id, review, idempotency_key)
supersede(context, id, old_ids, review, idempotency_key)
```

`record` input is `{kind,title,body,scope,sources,expires_at?}`. Scope is `project|worktree|task`; task scope requires `context.task_id`. Scope qualifiers are stamped by the resolver and cannot be chosen independently by the caller. `sources` and review `evidence` are nonempty lists of `{uri,locator?,note?}`. `review` is `{reason,evidence}`; the core stamps reviewer actor, session, harness, and UTC time. A source URI locates evidence; the core validates shape and preserves it but does not claim to verify its truth or fetch it automatically.

`context` returns `{status:"ok",scope,items,text,omitted,truncated}`. The scope includes `project_id`, `worktree_id`, optional `task_id`, and normalized `cwd`. `items` contain compact records; `text` is a complete bounded view including an owned `<shared-memory-context>` wrapper, epistemic status, source pointers, and a current `caller_context` JSON header containing resolved cwd, harness, actual session ID, actor, and optional task ID. This lets the model preserve actual native provenance in subsequent MCP writes instead of copying a remembered record's originating session. `omitted` counts eligible records excluded by limits; `truncated` reports budget restriction. Limits apply to the whole emitted text, including wrapper and caller header. A too-small budget returns empty text plus diagnostics instead of malformed/truncated metadata. Unknown/ambiguous/invalid context returns `{status:"unmapped"|"ambiguous"|"invalid",scope:null,items:[],text:"",omitted:0,truncated:false,diagnostic}`. Search/read consistently use an `items` collection; read returns full records in request order with explicit unavailable-ID reporting and no cross-scope payload. Do not introduce duplicate alias fields for these envelopes.

Writes return the resulting record ID and lifecycle view plus whether the request was replayed. Errors have stable machine-readable codes for invalid input, unknown/ambiguous scope, hint mismatch, inaccessible record, conflicting replay, invalid lifecycle, malformed store, and writer timeout. Hooks consume the context status/diagnostic envelope; other MCP operations surface actionable errors.

Search uses a 12,000-byte serialized core-envelope budget. Complete bodies of at most 1,024 UTF-8 bytes may remain in a listing; larger bodies are omitted entirely with explicit size/omission metadata and a record ID for full read. Source/provenance fields remain intact or the whole item is omitted. Count and byte restrictions report omissions deterministically. MCP may represent the envelope as both text and structured content, so the bound does not claim total wire size. Startup selection uses full canonical records independently of these compact listings, preserving whole-record character budgets.

### 3. Stable project registry and applicability

`registry.json` has `schema_version:1` and a `projects` list. Each entry has a stable `id`, explicit canonical `roots`, and `git_common_dirs`; the operator registers locations through the CLI. A Git common-directory binding may recognize linked worktrees of a registered repository only when the registered root is that repository's actual top level. Registering a nested subdirectory must not implicitly claim every checkout of its parent repository.

Resolve realpaths and directory ancestry. The most-specific explicit registered root owns a deliberately registered nested project. Equal-specificity or conflicting linked-worktree bindings fail closed. An unregistered independent Git repository nested below a registered ancestor must not inherit the ancestor's memory by path prefix when its Git common-directory identity differs. A same-named directory or remote URL does not establish identity. The worktree ID is a deterministic opaque fingerprint of its canonical worktree root (or the bound root for a non-Git project); it is a local applicability qualifier, not a portable project ID. Record branch and commit as provenance locators where available, not separate project identities.

Project records are eligible throughout the project; worktree records require the same worktree; task records require the same worktree and task. No task means no task-specific recall. Scope filtering precedes ranking and limits. `include_inactive` changes lifecycle visibility only, never the scope restriction. Unknown/unmapped contexts do not search another project or global corpus.

### 4. Markdown format and epistemic semantics

Every record is one UTF-8 Markdown file whose first block is a fenced `json` object, followed by a blank line and the human-readable body. Metadata contains `schema_version`, `id`, `project_id`, `kind`, `title`, `status`, `scope`, applicable `worktree_id`/`task_id`, `created_at`, `provenance`, `sources`, optional `expires_at`, optional `review`, `supersedes`, and operation identity/digest information needed for recovery. `schema_version` is 1. Unknown incompatible schema versions fail explicitly; malformed records are diagnosed and cannot silently be skipped if that could resurrect superseded knowledge.

Kinds are `observation`, `evidence`, `hypothesis`, `decision`, `experiment`, `result`, `invariant`, `bug/root-cause`, and `handoff`. Stored statuses are `candidate` and `active`; read views additionally expose `effective_status` of `expired` or `superseded`. Expiry uses timezone-aware UTC timestamps. An active hypothesis stays a hypothesis. Review marks applicability/acceptance for recall, not scientific proof.

Provenance preserves the originating harness, actor, session, normalized cwd, available Git revision/branch, and capture time. Promotion preserves that provenance and adds review provenance. An injected memory or repeated recollection is not new independent evidence. The workflow instructions require evidence-backed review by the main agent/designated consolidator and prohibit silently upgrading claim strength.

### 5. Lifecycle and atomic supersession

`propose` always creates a candidate. `promote` validates review evidence and atomically replaces that candidate's file with the active lifecycle state, preserving its ID and content. Accepted content is immutable through the interface; corrections use a new candidate. Replaying the same successful operation returns the prior result rather than another record or review.

`supersede` takes an existing candidate and atomically promotes only its file, adding `supersedes` links to previously active records with the same exact scope qualifiers. It must reject a cross-project/worktree/task edge, a self-edge, a cycle, or a target already superseded. The predecessor is not rewritten. Its effective superseded status derives from the complete canonical project set. Candidate links cannot suppress active knowledge.

Supersession is durable: expiry of a successor does not resurrect its predecessor. Compute lifecycle relationships before query matching, scope selection, ordering, or limits; otherwise a successor outside a search result could expose obsolete content. Preserve source and rejected/superseded reasoning for explicit scoped historical reads; the default recall includes active nonexpired nonsuperseded records only.

This single-file successor publication avoids a two-file transaction where one process crash could leave both versions active or neither readable. Arbitrary active-record editing and automatic record deletion are excluded from v1 tools.

### 6. Cooperating writers and recovery

Use a SQLite `BEGIN IMMEDIATE` transaction gate for registry/lifecycle writes on one Linux host/local filesystem. Bound writer wait time and report timeout. Readers requiring a coherent lifecycle snapshot take a compatible coordination gate while reading the canonical set. The coordination database holds operation receipts/keys/digests and minimal operational metadata, never record bodies or canonical factual content. It is not advertised as disposable cache.

Within the gate validate canonical state, detect replay/collision, write a temporary record in the destination filesystem, flush and fsync it, atomically replace/publish the target, and fsync the directory before completing the receipt. Same operation key plus same normalized input returns the existing result; same key plus different normalized input fails. Concurrent candidates get distinct IDs; ID/path collisions never overwrite unrelated content. Scope, operation type, and stable request content participate in replay identity.

SQLite and filesystem commits are not one transaction. Therefore canonical record metadata retains proposal and review operation keys/digests. After a crash following publication but before SQLite commit, reconcile the existing publication under the next gate and restore the receipt rather than duplicate the write. Interrupted unpublished temporary files are not canonical records. A database that is missing/inconsistent with an established store requires explicit diagnosis/reconciliation, not silent treatment as an empty new store. Tests exercise both sides of publication and key conflicts.

No mandatory `fcntl` layer is added. Noncooperating direct file edits and multi-host filesystems are outside the write-concurrency guarantee; operator edits require a quiescent store and subsequent validation. Paths and IDs are validated, symlink escapes rejected, and all writes remain within the selected data root.

### 7. Harness lifecycle and installation

The common CLI offers operator `init`, `register`, `doctor`, transport startup, and a `hook` entrypoint. The hook consumes native JSON on stdin, obtains actual session cwd/identity, calls core context, and emits the native response envelope. Host event names/envelopes are verified against installed source rather than copied from historical integrations. Supported native Codex hook output uses its additional-context mechanism; Pi uses its native extension/context mechanism and built-in MCP registration where supported by the installed version. The retained Claude adapter is an inactive prototype: this delivery neither reads nor writes actual Claude configuration and does not enable it.

Startup, resume, and post-compaction recall refresh the bounded view. Pi replaces its owned injected message. Codex registration contains one owned hook per supported lifecycle event and never writes generated memory into instruction files. Do not dedupe future deliveries by session plus record ID: promotion/content changes and compaction require fresh delivery. V1 uses no delivery ledger: each native context boundary receives one fresh bounded view. Codex native additionalContext is append-only; the adapter cannot erase prior messages or facts retained in a compacted summary. This limitation is documented rather than hidden behind a false no-duplication guarantee. Pi's owned-message replacement has a stronger no-stacking guarantee.

The local harnesses already share `/data/CoordExp/.codex/skills` through existing symlinks. Install exactly one `shared-memory` skill entry there pointing to the portable bundled skill. Do not create separate Claude or Pi copies or rewrite the existing sharing arrangement.

Adapters perform recall only. Meaningful decision/result/root-cause/handoff capture is an explicit MCP call under short shared workflow guidance. There are no transcript watchers or background model calls. Hooks fail open for unavailable memory service while scope resolution itself fails closed, so unavailable memory does not prevent ordinary coding and never substitutes unrelated memory.

The authorized proactive-guidance follow-up keeps the full operating procedure in the shared skill. A fixed source-owned reminder precedes the untrusted record wrapper in the common context text and is included in the existing total character budget. It directs relevant task/topic retrieval, navigation when needed, and explicit semantic capture; it does not derive instructions from records or raise their authority. MCP initialization and tool descriptions expose the same workflow entry and operation-specific triggers. A budget too small for the complete required view still returns empty text with diagnostics. Delegated workers use their own actual caller context; if unavailable, they return source-linked candidate content to the lead rather than inventing identity or copying the parent's context. Review roles remain workflow policy, not server-enforced access control. Current Claude qualification is owned by the separate `qualify-claude-haiku` change; its existing adapter receives the same common reminder without a new activation.

### 8. Validation and acceptance

Consumer tests cover metadata round-trip, source preservation, project/worktree/task separation, symlink and subdirectory resolution, project-hint mismatch, deterministic ranking, full-set expiry/supersession, character budgets, candidate promotion, explicit review, collision/replay conflicts, simultaneous writers, and interrupted publication recovery. Load-bearing negative cases must demonstrate rejection rather than only happy-path coverage.

Exercise the official SDK client against the actual stdio entrypoint, and native hook/extension parsing with source-backed envelopes. Before activation, run isolated Codex/Pi checks using temporary data/configuration and a disposable Git fixture with linked worktrees, including bounded real GPT-6-Luna sessions in both harnesses. Verify startup recall, six-tool availability, correct caller provenance, and explicit candidate promotion/read behavior. Model calls for these explicitly requested tests are distinct from prohibited background extraction calls. Then enable only owned Codex/Pi actual configuration entries, preserve unrelated settings, and verify fresh configured sessions. A transport/fixture/stub pass alone cannot establish real-model native acceptance. Report unavailable native execution honestly rather than weakening acceptance. Claude prototype tests do not gate the current two-harness release.

## Risks / Trade-offs

- Caller provenance is self-reported in a cooperating local tool environment → document this trust model; do not present actor fields as authenticated access control.
- Lexical recall can miss synonyms → keep explicit read/search and measurable scope; add an index only after demonstrated need.
- SQLite/file publication gap → canonical operation identities and recovery tests close replay/collision failure modes.
- Manual edits or malformed records can break lifecycle relationships → fail explicitly and run doctor before serving affected knowledge.
- Harness lifecycle changes → keep native adapters thin, source-backed, version-qualified, and tested at the installed entrypoint.
- Centralization does not imply universal applicability → apply worktree/task restrictions and preserve research evidence conditions.

## Migration Plan

Build and validate the isolated package/store first. Create the configured local data root and explicit project registry without importing native memories or old archived copies. Prepare exact owned entries and the single shared skill, then activate only actual Codex/Pi configurations under the user's authorization after isolated GPT-6-Luna acceptance. Actual Claude configuration remains untouched. Rollback removes/disables only owned entries and leaves the canonical Markdown store intact. A local source Git repository distinguishes this package from its parent project's Git binding; the user will create/publish the GitHub repository later, and this change performs no remote publication.
