# shared-memory-public-interface Specification

## Purpose

Provide direct scoped memory operations with auditable withdrawal and portable invocation branding across the three registered harnesses.
## Requirements
### Requirement: Direct scoped operation names

The unified MCP server SHALL retain the ordinary operations `context`, `search`, `read`, `create`, `approve`, `update`, `delete`, `capture`, and `curate`. Create SHALL produce candidates, approve SHALL require explicit review, and update SHALL publish a reviewed successor candidate using exact-scope predecessor links without rewriting predecessor contents. Capture and curate SHALL follow shared-memory-curation. The historical propose/promote/supersede public aliases SHALL remain retired.

#### Scenario: Fresh client discovers direct names
- **WHEN** a client initializes and lists tools
- **THEN** it receives the nine retained ordinary names plus the unified manual operations with applicable caller schemas and clear descriptions of successor and predecessor IDs

The same owned integration SHALL expose the bounded manual consolidation operations. A fixed total tool count MUST NOT exclude Dreaming or require another registration. Calls SHALL retain real caller context; project/source permissions SHALL come from stable configuration rather than caller-provided dated profiles or publisher switches.

#### Scenario: Manual Dreaming uses the existing connection
- **WHEN** an authorized Agent starts a requested consolidation task
- **THEN** the same connection supplies its ordinary operations and bounded batch operations without reinstalling another publisher

### Requirement: Auditable withdrawal

Delete SHALL atomically append one reviewed exact-scope marker referencing an existing visible target. It SHALL preserve original target bytes, review/source provenance and operation replay identity. Both the withdrawn target and marker SHALL be excluded from default recall and available through explicit historical visibility. Markers SHALL NOT expire, supersede records or themselves be withdrawal targets. Unknown, duplicate or scope-invalid withdrawal edges SHALL fail closed.

#### Scenario: Active knowledge is withdrawn
- **WHEN** a reviewed delete of an active record succeeds
- **THEN** ordinary recall excludes both target and marker, historical reads retain them, and the original file is unchanged

#### Scenario: Withdrawn candidate cannot be published
- **WHEN** a candidate is withdrawn and approval or successor publication is attempted
- **THEN** publication fails without restoring the candidate

#### Scenario: Successor withdrawal preserves predecessor retirement
- **WHEN** B supersedes A and B is withdrawn
- **THEN** neither A nor B is active, including after expiry of B

#### Scenario: Retry after publication interruption
- **WHEN** deletion is interrupted after marker publication and the same request/key is retried
- **THEN** the original marker is returned without another publication

### Requirement: Portable invocation branding

The server and tools SHALL provide supported MCP icon/title metadata from self-contained packaged assets. The standalone skill SHALL provide local icon metadata without network requests or additional runtime dependencies. Client-specific rendering SHALL NOT be required for functional acceptance.

#### Scenario: Installed package outside source checkout
- **WHEN** the wheel is installed and initialized from another directory
- **THEN** server/tool icon metadata is available and the skill asset matches the packaged logo
