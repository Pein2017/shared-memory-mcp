## MODIFIED Requirements

### Requirement: Explicit expiry and progressive recall
Default record recall SHALL include only applicable active, nonexpired, nonsuperseded records. Empty-query startup SHALL deliver eligible preferences and project understanding under shared-memory-recall; task-known search SHALL retain bounded cards before full reads. Context SHALL use that capability's one combined serialized budget, preserve whole qualified units, report omissions and provide detail continuation. Memory SHALL be presented as contextual data, not instructions overriding user or project authority.

#### Scenario: Budget includes metadata
- **WHEN** a context request sets a small supported serialized budget
- **THEN** the complete emitted text including wrapper and source/status information remains within it, or the operation returns an explicit bounded budget diagnostic without misleading empty-success content

#### Scenario: Large search matches remain bounded
- **WHEN** matching records contain large bodies or extensive source/provenance metadata
- **THEN** search keeps its serialized core response within 12,000 bytes, reports omitted bodies/items and preview limits explicitly, and supplies IDs for full scoped reads preserving original metadata

#### Scenario: Expired active record
- **WHEN** an active record's explicit expiry has passed
- **THEN** default recall excludes it and an explicit scoped historical read identifies it as expired
