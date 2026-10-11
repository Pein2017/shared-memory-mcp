## ADDED Requirements

### Requirement: Deterministic empty-query browsing
Empty or normalized-whitespace search SHALL return a bounded deterministic browse of eligible records ordered by normalized title, project identity and record identity. Selecting a task mode MUST NOT require or fabricate lexical scores for that browse, change its ordering, widen eligibility or implicitly filter other modes. Explicit user-requested mode restrictions SHALL still apply. Continuation SHALL retain the existing corpus revision fence and stable page order.

#### Scenario: Browse with either task mode
- **WHEN** an authorized caller searches with an empty or whitespace-only query and `research` or `general` mode
- **THEN** search succeeds through the ordinary interface with the same browse order as unbound mode, no fabricated lexical match reasons and candidates excluded by default

#### Scenario: Restricted browse
- **WHEN** the caller supplies an explicit user mode restriction with an empty query
- **THEN** only eligible records satisfying that restriction are returned without inventing lexical matches

#### Scenario: Continued browse changes underneath the caller
- **WHEN** a caller continues an empty-query page with an earlier corpus revision after a record change
- **THEN** the continuation fails with the existing stale-search condition instead of mixing snapshots

### Requirement: Task-driven successive reading
Reader guidance SHALL encourage successive relevant batches without a cumulative record, session, source, page or round quota. Per-response budgets, backend protections, visibility and revision fences SHALL remain in force. Readers SHALL follow supported continuations when task-required evidence remains incomplete, preserve decisive conditions and counterevidence, and distinguish selected context, previews, complete detail and original sources. They SHALL stop based on the task's evidence needs or report a concrete unresolved gap, rather than treating a count, page delivery or first-page ranking as completion. This guidance MUST NOT require exhaustive unrelated-history reading for an ordinary task or grant additional source access.

#### Scenario: Necessary evidence occurs after the first batch
- **WHEN** a relevant search, audit or source page has a supported continuation and the task still needs unseen evidence
- **THEN** the reader continues with the returned cursor or offset/revision under the same selection, without stopping at a fixed number of pages or items

#### Scenario: Context is selected and detail is fragmented
- **WHEN** context omits knowledge or a detail response contains preview pointers, omitted IDs or JSON fragments
- **THEN** the reader uses targeted search/read or original-source routes, reads needed omitted IDs in further batches and reassembles exact fragments before interpreting the claim; repeating context is not pagination

#### Scenario: The evidence need is satisfied or access remains blocked
- **WHEN** required task evidence and decisive qualifiers have been reviewed, or a concrete access, version, structure or backend limit prevents the remaining dependent read
- **THEN** the reader can stop with the scoped conclusion or explicit unresolved gap, without claiming broader coverage or consuming unrelated material merely to exhaust a cursor
