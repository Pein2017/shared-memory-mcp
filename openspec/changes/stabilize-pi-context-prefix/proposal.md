## Why

The Pi adapter moves an unchanged recalled snapshot to the end of every provider
request. This changes the previous complete request prefix even during ordinary
continuation. Low Pi Web cache usage motivates correcting this concrete prefix
instability while separately diagnosing the official compaction plugin.

## What Changes

- Place the one ephemeral, user-level recalled snapshot at a stable early
  conversation position; keep lifecycle freshness and closed scope unchanged.
- Add a retained native-caller regression proving ordinary context growth
  preserves the earlier converted message prefix.
- Preserve failure clearing, caller identity, size bounds and native history.
- Record measured cache behavior separately from CPU prefix qualification.

## Capabilities

### New Capabilities

- `shared-memory-harness-integration`: add a stable-prefix requirement to the
  existing integration capability defined by the in-flight build change. The
  repository has no archived main specs; reuse its established capability path.

### Modified Capabilities

None.

## Impact

Pi adapter, installed-SDK integration tests and adapter documentation. No change
to canonical records, MCP operations, Codex/Claude injection, persistent session
history or recall scheduling. Official compaction transport fixes remain owned
by their plugin source and are not part of this package change.
