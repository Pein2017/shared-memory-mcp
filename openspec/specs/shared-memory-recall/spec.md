# shared-memory-recall Specification

## Purpose

Help agents discover applicable prior work and its original owners without injecting unrelated history, treating recall as evidence, or breaking harness context stability.
## Requirements
### Requirement: Meaningful lexical admission and explainable ranking
Search SHALL admit meaningful word, identifier, CJK or explicitly curated alias matches. Latin character-bigram overlap alone SHALL NOT admit a result. Ranking SHALL distinguish fields, account for common terms and document length, and disclose match reasons. Record age and retrieval frequency SHALL NOT establish validity or retire evidence.

#### Scenario: Unrelated letter fragments
- **WHEN** a query for pytest encounters a record sharing only es, st or te
- **THEN** the record is not returned unless another meaningful query or alias term matches

#### Scenario: Curated multilingual route
- **WHEN** a task uses a configured alias for a topic
- **THEN** search can discover that route and related records while reporting the alias expansion

### Requirement: Bounded cards with recoverable full material
Search SHALL return relevance cards rather than full audit envelopes. Cards SHALL retain identity, epistemic kind, applicable conditions when available, source pointers and explicit disclosure limits. Missing summaries SHALL be presented as previews, not complete claims. Pagination SHALL report omissions and a continuation that makes progress, including oversized records. Full reads SHALL retain original content and provenance; audit detail SHALL remain requestable.

#### Scenario: Long conditional record
- **WHEN** a record cannot fit complete text in a search card
- **THEN** it remains discoverable with a marked preview or compact read pointer, and a full read recovers every original qualifier and source

#### Scenario: Many results or changing corpus
- **WHEN** the caller continues a bounded search
- **THEN** the response exposes the corpus revision and offset so a changed corpus is not silently presented as the same snapshot

### Requirement: Deliberate cross-project engineering reuse
Imported recall SHALL require both an explicit directional project allowlist and an explicit record-level share declaration with engineering domain and project scope. The system SHALL preserve source-project attribution and SHALL NOT allow imported read access to authorize mutation. Research, candidate, retired, worktree and task records SHALL NOT be implicitly imported.

#### Scenario: Both permissions are present
- **WHEN** a published project engineering record is shared to an allowlisted target
- **THEN** task-time search and full read in the target can retrieve it with its original project identity

#### Scenario: One permission is absent
- **WHEN** either project permission or record-level sharing is absent
- **THEN** the foreign record is not returned, even with historical visibility enabled

### Requirement: Harness-friendly MCP contract
The MCP SHALL keep stable tool order and static descriptions, declare read/write effects accurately, preserve actual caller scope, and bound both its structured projection and serialized text fallback. Startup adapters SHALL retain their existing identity/failure semantics and the separately implemented stable early Pi prefix. Task-time results SHALL NOT rewrite prior conversation history or tool definitions.

#### Scenario: Ordinary Pi conversation growth
- **WHEN** the recalled navigation is unchanged and ordinary messages are added
- **THEN** the prior converted provider-message prefix remains unchanged under the retained installed-SDK regression

#### Scenario: WebCodex uses the local bridge
- **WHEN** a WebCodex Workflow Session invokes supported memory operations through the CLI
- **THEN** its real harness and session identity are retained rather than impersonating a native Codex session

### Requirement: Content-bearing scoped startup
The system SHALL provide applicable reviewed preferences and stable project background at startup when eligible content exists, together with compact navigation. It MUST resolve the real caller's scope before selecting content and MUST NOT require a task query to deliver generally applicable background.

#### Scenario: Registered project has eligible background
- **WHEN** an authorized new session requests startup context without a task query
- **THEN** it receives bounded preference/background content and source pointers rather than only a reminder to search

#### Scenario: Unknown project or absent eligible knowledge
- **WHEN** the caller scope is unknown, ambiguous, or has no eligible content
- **THEN** the response distinguishes that condition without inventing a profile or exposing another project's knowledge

### Requirement: Foreground task-mode selection
The system SHALL support `research` and `general` as selection modes. The foreground Agent SHALL select a mode from the first substantive task, honor an explicit user choice and support later switching. Before that input the mode SHALL remain unbound. Mode selection MUST NOT require a separate model call or change access permissions.

For knowledge, mode SHALL default to a ranking/presentation preference, not exclude authorized relevant evidence from the other mode. Corrections, necessary limitations and counterevidence MUST NOT be dropped solely for a mode mismatch. Hard mode filtering SHALL require an explicit user restriction with a visible disclosure boundary. Scoped preference applicability SHALL remain strict and independent of knowledge ranking.

#### Scenario: Task changes within a mixed session
- **WHEN** a research session changes to an engineering task and the Agent switches its mode
- **THEN** task context is recomposed for the new mode while applicable shared preferences and the actual caller scope remain intact

#### Scenario: Cross-mode lookup
- **WHEN** an Agent requests relevant material from the other mode
- **THEN** authorized material remains discoverable without silently changing the session binding or creating another knowledge store

#### Scenario: Engineering evidence qualifies a research claim
- **WHEN** a research task matches a general-mode record describing a necessary implementation constraint
- **THEN** default retrieval can include that constraint without an explicit cross-mode retry while still excluding inapplicable personal preferences

### Requirement: Coherent task context with evidence bounds
Task context SHALL combine relevant background, the reasoning and turning points behind the current direction, applicable findings and their conditions, and usable original-source pointers. Corrections and necessary counterevidence MUST remain attached to the claims they qualify. Related evidence SHALL retain its relation direction and source scope.

#### Scenario: Research overview includes global and local context
- **WHEN** a relevant research branch is selected
- **THEN** its packet connects the long-term objective and route-wide milestones to that branch's turning points, outcome and remaining question

#### Scenario: A qualifier does not fit
- **WHEN** a claim fits the remaining budget but its necessary limitation or correction does not
- **THEN** the system omits the whole affected unit and supplies a bounded read pointer rather than emitting an unqualified conclusion

### Requirement: Reviewed compact narrative units
Default background SHALL use a small number of stable scoped narrative units with reviewed compact text, source dependencies, review time and explicit correction/replacement relations. Longer detail SHALL share the same unit identity and evidence boundaries. The core MUST NOT invent an unreviewed compression. A populated default-context qualification SHALL deliver useful compact content with necessary limitations inside the normal budget; an empty budget diagnostic alone MUST NOT pass it.

#### Scenario: Long reviewed branch account
- **WHEN** a branch account's full text exceeds the default budget
- **THEN** context can deliver its reviewed compact rendition and original-detail pointer without changing its evidence level or dropping its decisive limitation

#### Scenario: Correction affects a source-only overview
- **WHEN** a new scoped pause decision replaces a current-plan assertion in a view whose original owner bytes have not changed and which has no canonical-record dependency
- **THEN** default context resolves the unit's explicit correction relation, stops treating the old active-plan assertion as valid, and retains independently identified historical results and reasons

### Requirement: One serialized context budget
The default active shared-memory payload SHALL target 2,000 model tokens and MUST be bounded to 8,000 UTF-8 bytes after the actual consumer serialization, including bootstrap and task content together, wrappers and reference metadata. An available qualified tokenizer SHALL enforce the token cap; otherwise token counts SHALL be explicitly estimated or unavailable. Core and adapters MUST use the same effective budget contract, honor smaller caller caps and count any duplicated model-visible representations.

#### Scenario: Default publisher and consumer budgets differ
- **WHEN** a published synopsis is larger than a requested consumer cap
- **THEN** the consumer returns whole units that fit or an explicit budget-limited diagnostic with a read/continuation route, never a successful-looking unexplained empty body

#### Scenario: CJK and transport expansion
- **WHEN** content contains CJK text, long source identifiers or escaped transport fields
- **THEN** enforcement uses the delivered UTF-8 representation rather than treating character counts as exact tokens or omitting envelope overhead

#### Scenario: Whole background would exclude the matching task evidence
- **WHEN** an individually eligible background and ranked query evidence cannot fit together under the normal combined cap
- **THEN** current-owner checks and ranked task evidence take precedence, related qualifiers remain indivisible, and the omitted unit has an exact continuation inside the delivered packet part; query-empty startup may still deliver the whole background if it fits

#### Scenario: Reviewed compact background fits with the task
- **WHEN** an existing reviewed compact rendition and the task evidence fit together
- **THEN** both are delivered with unchanged background position and identity, without core-generated compression

### Requirement: Dependency-scoped freshness
The system SHALL retain source-linked project understanding with its review time and source version. Ordinary permitted source updates SHALL mark affected units for checking without erasing the usable as-of account or declaring historical findings false. Remembered current-state claims MUST NOT be presented as freshly verified. Current access, withdrawal, supersession and source-use restrictions SHALL remain enforced independently of freshness, including historical reads.

#### Scenario: Active research note changes
- **WHEN** an ordinary active-note update affects a remembered current-state unit
- **THEN** the dated account and unrelated milestones remain available, the affected state is marked as needing a current-owner check, and an authorized source route is supplied

#### Scenario: Source changes during refresh
- **WHEN** the selected owner changes again before a refresh can be safely published
- **THEN** the Agent retains the useful dated understanding, reports the current-state gap or partial result, and stops within its bound rather than claiming freshness or retrying indefinitely

#### Scenario: Source access is revoked
- **WHEN** the current access policy or source-use disposition forbids a dependency
- **THEN** neither current nor historical context returns the affected content; an as-of label does not bypass the restriction

### Requirement: Foreground refresh for current judgments
Before answering a current-status question or making a consequential current-state judgment or recommendation, the foreground Agent SHALL inspect the relevant current owners and reconcile its remembered understanding. It SHALL do this within the task without asking the user to arrange synchronization. General background recall MUST NOT require exhaustive source rereading or a separate model call. An unresolved current fact SHALL remain explicitly unknown while useful dated background remains available.

#### Scenario: User asks where the research stands now
- **WHEN** the remembered branch summary predates a source update and the user asks for current progress
- **THEN** the Agent reads the relevant current owner, distinguishes the change from retained historical results, and answers with the checked state or a stated gap

#### Scenario: Only historical background is needed
- **WHEN** an Agent uses a permitted dated milestone to understand the project without asserting current status
- **THEN** it can use that as-of account without rereading the entire research tree or launching synthesis

### Requirement: Latest explicit scoped decision
The system SHALL distinguish a current explicit user decision from historical plans, quotations, delegated messages and scientific observations. For the same scope, the latest established user decision SHALL govern the remembered current plan even when an older owner document has not been synchronized. Memory MUST NOT convert that precedence into new execution permission or revised experimental facts.

#### Scenario: User pauses a route before its document is updated
- **WHEN** a sourced explicit user decision pauses a route whose older document still calls it active
- **THEN** context reports the pause and the document discrepancy while retaining the original experimental outcomes unchanged
