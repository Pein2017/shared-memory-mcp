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
