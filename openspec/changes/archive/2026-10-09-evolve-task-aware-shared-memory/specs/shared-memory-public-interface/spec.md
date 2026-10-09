## MODIFIED Requirements

### Requirement: Direct scoped operation names

The unified MCP server SHALL retain the ordinary operations `context`, `search`, `read`, `create`, `approve`, `update`, `delete`, `capture`, and `curate`. Create SHALL produce candidates, approve SHALL require explicit review, and update SHALL publish a reviewed successor candidate using exact-scope predecessor links without rewriting predecessor contents. Capture and curate SHALL follow shared-memory-curation. The historical propose/promote/supersede public aliases SHALL remain retired.

#### Scenario: Fresh client discovers direct names
- **WHEN** a client initializes and lists tools
- **THEN** it receives the nine retained ordinary names plus the unified manual operations with applicable caller schemas and clear descriptions of successor and predecessor IDs

The same owned integration SHALL expose the bounded manual consolidation operations. A fixed total tool count MUST NOT exclude Dreaming or require another registration. Calls SHALL retain real caller context; project/source permissions SHALL come from stable configuration rather than caller-provided dated profiles or publisher switches.

#### Scenario: Manual Dreaming uses the existing connection
- **WHEN** an authorized Agent starts a requested consolidation task
- **THEN** the same connection supplies its ordinary operations and bounded batch operations without reinstalling another publisher
