## Why

Agents and users need recognizable branding and direct operation names when invoking shared memory. Withdrawal also needs an explicit auditable operation instead of a correction disguised as deletion.

## What Changes

- **BREAKING**: Replace the six `memory_*` MCP names with `context`, `search`, `read`, `create`, `approve`, and `update`; add `delete` for logical withdrawal. Core proposal/review/supersession semantics remain.
- Add packaged self-contained vector branding to MCP server/tool metadata and the shared skill UI.
- Add append-only reviewed withdrawal markers; hide both target and marker from normal recall while retaining historical reads.
- Update current guidance and native probes, verify existing three-harness registrations, and publish the independent source repository to the user-authorized public GitHub repository.

## Capabilities

### New Capabilities

- `shared-memory-public-interface`: Simple MCP operations, auditable withdrawal, and portable icon metadata. Existing core and harness contracts live in their unarchived owning changes; no duplicate replacement specifications are introduced.

### Modified Capabilities

None in the main specification inventory.

## Impact

MCP clients must reconnect to discover renamed tools. Withdrawal markers extend the canonical v1 variant without migrating existing records; older readers fail closed on unfamiliar metadata. Markdown/native stores, working directories, provider settings and scoped caller identity stay independent. Existing qualified activation is retained; this change uses CPU/native offline acceptance and no paid model calls. Only source, tests, documentation and assets are published; runtime records, receipts and credentials stay local.
