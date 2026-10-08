## Context

See proposal.md. The core and hook envelope already support Claude; only Codex/Pi were enabled in the initial release. Current native metadata resolves `haiku` to `claude-haiku-4-5-20251001`; effort capability fields are absent.

## Goals / Non-Goals

**Goals:** Prove actual Haiku consumption of startup context, use of the existing six-tool API, reviewed persistence, and fresh-session recall before opt-in deployment.

**Non-Goals:** Changing canonical schemas, default models, native memories, HarnessDock routing, or background extraction. Additional paid compaction/resume tests and automatic historical import are excluded.

## Decisions

- Use the native Claude CLI with the exact discovered Haiku ID and no effort/fallback flags. Zero-prompt SDK initialization supplies metadata but does not prove hooks execute.
- First qualify the installed startup consumer against a rejecting local provider. Then use two real sessions in an isolated registered Git project/store. Seed records with explicit synthetic Codex/Pi fixture provenance; validate Claude's publication through independent SDK clients for both caller harnesses. Do not describe those fixture clients as new paid Codex/Pi sessions.
- Use a temporary `CLAUDE_CONFIG_DIR`, explicit settings/MCP files, no transcript persistence, and disabled native auto-memory only in the fixture. Existing unexpired access credentials travel in the child's environment, without a copied refresh token. Never print credential contents.
- Add explicit `--claude-dir` to the current installer. Back up and preserve its `settings.json` and `.claude.json`, add one owned hook, and use native user-scoped MCP registration. Identical reinstallation skips duplicate registration; conflicting ownership fails before mutation. Existing Codex/Pi defaults and the single shared skill stay intact.

## Risks / Trade-offs

- Account/quota or unavailable model: stop without retry, fallback, or actual activation; retain completed evidence.
- Hooks append context: fresh recall cannot erase earlier conversation/compacted knowledge. Keep the existing limit explicit.
- Native configuration may change during validation: compare current owned/unowned state before application and verify native registration afterward.
- Access-token expiry: check current metadata before launch; do not duplicate refresh credentials or change account state.

## Migration Plan

After isolated qualification, add only owned Claude entries targeting the existing central root. Verify fresh actual configured startup with no provider inference and repeat installation for idempotency. Rollback removes those exact entries while retaining records and unrelated settings. The initial Codex/Pi evidence and production records remain intact.
