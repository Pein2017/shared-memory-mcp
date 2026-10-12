## MODIFIED Requirements

### Requirement: Direct scoped operation names

The unified MCP server SHALL expose exactly twenty-one operations without compatibility aliases. Ordinary operations SHALL be `context`, `search`, `read`, `capture`, `approve`, `supersede`, `withdraw` and `annotate`. Manual Dreaming operations SHALL be `source_list`, `source_read`, `dream_start`, `dream_status`, `dream_materials`, `dream_draft`, `dream_publish`, `dream_close`, `dream_takeover`, `overview`, `issue_open`, `issue_list` and `issue_close`. Capture without review SHALL produce a candidate and with review SHALL publish; approve SHALL require explicit review; supersede SHALL publish a reviewed successor using exact-scope predecessor links without rewriting predecessor contents; withdraw SHALL perform the auditable withdrawal below; annotate SHALL perform reviewed metadata and retirement changes under shared-memory-curation. The retired names `create`, `update`, `delete`, `curate`, `memory_audit`, `dream_catalog`, `run_*`, `draft_*`, `coverage_mark`, `overview_read`, `issue_suggest`, `issue_search`, `issue_resolve` and the historical propose/promote/supersede aliases of version 0.1 SHALL NOT be served.

#### Scenario: Fresh client discovers direct names
- **WHEN** a client initializes and lists tools
- **THEN** it receives exactly the twenty-one names above with applicable caller schemas, read/write annotations and descriptions naming successor and predecessor IDs

#### Scenario: Retired name is called
- **WHEN** a client calls `create`, `update`, `delete`, `curate`, `memory_audit`, `dream_catalog` or any `run_`/`draft_`/`coverage_` name
- **THEN** the server reports an unknown tool whose diagnostic names the replacing operation, and performs no effect

The same owned integration SHALL expose the bounded manual consolidation operations. A fixed total tool count MUST NOT exclude Dreaming or require another registration. Calls SHALL retain real caller context; project/source permissions SHALL come from stable configuration rather than caller-provided dated profiles or publisher switches.

#### Scenario: Manual Dreaming uses the existing connection
- **WHEN** an authorized Agent starts a requested consolidation task
- **THEN** the same connection supplies its ordinary operations and bounded batch operations without reinstalling another publisher

### Requirement: Auditable withdrawal

Withdraw SHALL atomically append one reviewed exact-scope marker referencing an existing visible target. It SHALL preserve original target bytes, review/source provenance and operation replay identity. Both the withdrawn target and marker SHALL be excluded from default recall and available through explicit historical visibility. Markers SHALL NOT expire, supersede records or themselves be withdrawal targets. Unknown, duplicate or scope-invalid withdrawal edges SHALL fail closed. No operation SHALL physically delete a canonical record.

#### Scenario: Active knowledge is withdrawn
- **WHEN** a reviewed withdraw of an active record succeeds
- **THEN** ordinary recall excludes both target and marker, historical reads retain them, and the original file is unchanged

#### Scenario: Withdrawn candidate cannot be published
- **WHEN** a candidate is withdrawn and approval or successor publication is attempted
- **THEN** publication fails without restoring the candidate

#### Scenario: Successor withdrawal preserves predecessor retirement
- **WHEN** B supersedes A and B is withdrawn
- **THEN** neither A nor B is active, including after expiry of B

#### Scenario: Retry after publication interruption
- **WHEN** withdrawal is interrupted after marker publication and the same request/key is retried
- **THEN** the original marker is returned without another publication

## ADDED Requirements

### Requirement: Uniform caller, continuation, fence and budget arguments

Every operation SHALL take the caller identity as the `caller` argument with fields `cwd`, `harness`, `session_id`, `actor` and optional `project_id`, `task_id`, `role`, `model`, `parent_session_id`. Every paginated operation SHALL accept one opaque `cursor` string and return `next_cursor` (null when complete); offset, page objects and separate revision arguments SHALL NOT be accepted. Every mutating operation that depends on previously read state SHALL accept one `expected_revision` string equal to the `revision` returned by the prior read of that object; run generations, content digests and curation revisions SHALL NOT be separate caller-visible arguments. Size arguments SHALL be `limit` (item count) and `max_bytes` (serialized size); `max_events` SHALL exist only on `source_read`. `idempotency_key` SHALL be optional on every write; when omitted the server SHALL derive a deterministic key from the caller session and the canonical payload so that an identical retry replays and a changed retry fails.

#### Scenario: Continuation with an opaque cursor
- **WHEN** a caller passes the `next_cursor` from a previous `search`, `read`, `source_list`, `source_read`, `dream_materials`, `overview` or `issue_list` response
- **THEN** the next page continues the same snapshot, and a cursor whose corpus or source changed is rejected with a diagnostic naming a fresh start

#### Scenario: Stale fence
- **WHEN** a write supplies an `expected_revision` older than the current revision of its object
- **THEN** the write is rejected without effect and the response carries the current revision

#### Scenario: Omitted idempotency key
- **WHEN** a caller omits `idempotency_key` on `capture` and retries the identical payload after a transport failure
- **THEN** the second call replays the first result and reports the same derived key; reusing that reported key with changed content is rejected, while a changed payload without a key is a new write

### Requirement: Uniform response envelope

Every successful response SHALL contain `status: "ok"`, `scope`, `revision`, either `items` or `item`, `next_cursor`, `omitted` as an object with named counts, `truncated` and `notices`. Every error SHALL contain `status: "error"` and `diagnostic` with `code`, `message` and, for argument-shape errors, `example` holding a minimal correct payload. Dreaming responses SHALL additionally contain `next` with the suggested tool name and complete arguments, including every opaque token the caller would otherwise copy by hand. Serialized bounds SHALL be reported in `budget` with `limit_bytes` and `used_bytes`.

#### Scenario: Argument-shape error
- **WHEN** a caller uses a wrong field name or omits a required argument
- **THEN** the diagnostic names the field and includes an example payload that would succeed

#### Scenario: Dreaming step hint
- **WHEN** `dream_start`, `dream_status`, `dream_materials`, `dream_draft` or `dream_publish` succeeds
- **THEN** the response's `next` contains the following tool and arguments with the exact run id, revision and cursors already filled in
