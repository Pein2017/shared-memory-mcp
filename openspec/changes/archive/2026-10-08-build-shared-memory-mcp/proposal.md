## Why

Codex CLI and Pi need auditable shared continuation and research knowledge without replacing native memory or coupling the knowledge store to one harness. A centralized Markdown store with explicit provenance, scoped recall, and validated candidate promotion supplies that capability while preserving a future path to other harnesses.

## What Changes

- Add a portable Python core and official-SDK stdio MCP interface with context, search, read, propose, promote, and supersede operations.
- Store one canonical Markdown record per ID under a configurable centralized root, with fenced JSON metadata, stable project bindings, worktree/task applicability, and evidence provenance.
- Serialize cooperating local writers through SQLite and publish record changes atomically, preserving idempotency and recoverability.
- Add supported bounded startup/resume recall adapters for Codex CLI and Pi; capture happens explicitly at meaningful workflow transitions. Retain already written Claude adapter code only as an inactive prototype, outside current support and activation claims.
- Supply operator registration, diagnostics, configuration generation, tests, and usage documentation. Verify isolated real GPT-6-Luna sessions in Codex and Pi before enabling only those actual harness configurations using narrow reversible edits. Install one shared skill entry through the existing shared `.codex/skills` directory.
- Strengthen proactive agent guidance through one shared skill, a fixed budgeted startup reminder outside recalled records, operation-specific MCP triggers, and explicit delegation/caller-context guidance. This follow-up changes instructions, not the record schema, adapter interfaces, authorization model, or capture lifecycle.

## Capabilities

### New Capabilities

- `shared-memory-core`: Canonical records, scope resolution, lifecycle, concurrent writes, and bounded recall.
- `shared-memory-harness-integration`: Common MCP/CLI interfaces and verified Codex/Pi startup integration.

### Modified Capabilities

None; this is a new standalone package with no existing capability specifications.

## Impact

Source is isolated to this package; runtime data initially lives under `/data/CoordExp/.shared-memory/` and remains configurable. Python >=3.11 and the official MCP Python SDK are required for the MCP transport; the core uses the standard library. Current Linux local filesystems are the persistence support target. Existing native memories, formal research records, historical memory archives, and unrelated harness configuration are preserved. Actual Claude configuration is outside the current read/write/activation scope. Local source Git initialization establishes an independent project identity; remote repository creation/publication, automatic Git commits, and legacy-skill removal are outside this change.
