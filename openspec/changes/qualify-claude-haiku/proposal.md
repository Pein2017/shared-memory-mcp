## Why

The user has reopened Claude support after the Codex/Pi release. Its existing recall adapter needs native Haiku qualification before joining the same central Markdown store.

## What Changes

- Qualify Claude Code startup injection, reviewed capture/read, fresh-session recall, and actual session provenance with the native Haiku model.
- Extend local installation with an explicit optional Claude directory; preserve existing Codex/Pi behavior and the one shared skill entry.
- Add only the owned Claude SessionStart hook and user-scoped MCP registration after isolated acceptance.
- Keep the canonical core, record schema, native memories, default Claude model, and unrelated settings unchanged.

## Capabilities

### New Capabilities

- `shared-memory-claude-integration`: Native Claude recall/capture qualification and narrow opt-in installation.

### Modified Capabilities

None; the original Codex/Pi acceptance remains historical evidence.

## Impact

Existing Python hook translation, the local installer, native qualification tests, and shared workflow documentation. No new dependency, daemon, schema migration, HarnessDock change, or background extraction. Two bounded real Haiku sessions are the qualification target; account/quota failures stop the packet without model substitution or automatic relaunch.
