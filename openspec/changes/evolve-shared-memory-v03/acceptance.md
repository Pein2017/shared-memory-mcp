# Acceptance notes (2026-10-12)

Baseline: HEAD `af4ffb7` plus the 2026-10-12 working tree (Claude reader allowlists, fork matcher). All work is uncommitted in the working tree; commit requires user authorization.

## Package evidence
- Full suite after all packages: `PYTHONPATH=src .venv/bin/python -m pytest -q` → 656 passed, 1 skipped (the skip needs `shared-memory-mcp` on PATH; it passes with the venv bin on PATH). Baseline before the change: 588 passed.
- New test files: `tests/test_interface_v03.py` (WP1), `tests/test_dream_v03_closure.py` and `tests/test_dream_production_shape.py` (WP2), `tests/test_lifecycle_v03.py` (WP3), `tests/test_extract.py` (WP4). RED/GREEN was demonstrated per package for: derived-key replay/conflict, stale cursor/fence, unserved-event coverage rejection, unaccepted permanent gap, positions never advancing past unserved material, role grants nothing, stale derivation without file rewrite, prune never touching canonical files, concurrent extraction claims, slow extractor not delaying the hook.
- Installed Pi SDK regression (`tests/test_pi_installed_adapter.py`, `tests/test_context_final_budget.py`): 4 passed. `PI_SDK_ROOT=... node tests/pi_adapters.mjs`: pass.
- Native startup probe (`tests/native_startup_probe.py --harness all`, local rejecting provider, zero model calls): pi pass, codex pass, claude `limit` (serialized request captured with sentinel, record id, workflow reminder and the v0.3 tool names; this is the designed boundary for Claude). Report: `outputs/native-startup-probe.json`.
- `openspec validate evolve-shared-memory-v03 --strict`: valid.

## Live qualification (user-authorized)
- Extraction (task 5.3): `outputs/extraction-qualification-20261012/receipt.json`. gpt-6-luna via `codex exec` on one idle Codex rollout (34 s, 23.7k in / 701 out tokens, 4 candidates) and Claude Haiku via `claude --print` on one idle Claude root transcript (51 s, $0.075, 5 candidates). Lineage, `assurance: model-extracted`, absence from startup context, journal fields and no change under native memory directories, live store or harness configs were verified (`mtimes.diff` empty). Quality: about 6 of 9 candidates durable, 2 borderline, 1 noise; prompt follow-ups noted in the receipt.
- Live installation (task 5.4): installer `--apply` with `--claude-dir`; backup `/data/CoordExp/.shared-memory/.state/config-backups/20261012T141452Z-1a5b9f86`. Claude `settings.json` now has the owned SessionStart (`startup|resume|clear|compact|fork`) and SubagentStart groups; Codex hook trusted; MCP registrations unchanged. Pi `toolExposure` updated to `context/search/read/capture` (backup `manual-20261012T141453Z/pi-mcp.json`). Editable install refreshed to 0.3.0.
- Live extraction config: `/data/CoordExp/.shared-memory/extraction.json` (enabled, preferred `codex` gpt-6-luna with the isolated `codex exec` flags, Haiku as the alternative, three history roots, idle 1 h, 2 per startup, 10-day window, 200 KB windows). First hook-spawned run: hook returned in 0.36 s; the detached extractor processed two sessions (one `skipped` as unmapped scope, one `no-output` from gpt-6-luna after 31 s), log at `.state/extraction.log`.
- Live SubagentStart dry run: 503-byte identity packet with `role: worker` and the parent session.
- Dreaming policy: two read-only document grants added to `coordexp-consolidate-20261008` (`codex-rollout-summaries`, `claude-auto-memory-coordexp`), policy revision `d9b81aaa…`; the source-grant cap was raised from 16 to 32 in `dream_catalog.py` to admit them.

## External follow-ups (user-owned, task 5.5)
- WebCodex: redeploy against v0.3 (`caller` argument, tool names); its gateway looks up `context` by name, which is unchanged.
- Background briefing records per project and `routing/<project>.json` `background_ids`: operator content, not created here.
- Pi subagent identity injection needs a pi-web change (`subagent-runtime.ts` already injects a caller_context without `role`/`parent_session_id`).
- Already connected Codex/Pi/Claude MCP processes keep the 0.2 tool snapshot until reconnected or restarted.

## Open contract questions (design.md)
- Claude transcripts discovered through history roots carry no selected leaf and always report `active_branch_unverified`; whether Claude should default to the last message (as Pi defaults to its saved resume branch) is a user decision.
- Extraction prompt tuning: ask for `hypothesis` on small-sample generalizations, exclude plain configuration changes, state output language.
