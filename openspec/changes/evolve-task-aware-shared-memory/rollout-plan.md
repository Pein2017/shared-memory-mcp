# Reviewable rollout and historical-first-batch plan

**Status:** scoped local Codex/Pi activation completed on 2026-10-09 under the user's subsequent repair-and-enable request; see [acceptance.md](acceptance.md#repair-and-local-activation-receipt-2026-10-09). The historical batch below remains a proposal. This document grants no additional authority for ingestion, canonical-memory publication, model calls, server deployment, restart, commit or push.

## Source and deployment boundary

- Source checkout: `/data/CoordExp/codex-tools/shared-memory-mcp`; conditional WebCodex server integration: `/data/CoordExp/codex-tools/web-codex`. Resolve realpaths, registered Projects, Git HEAD and dirty changes **again** immediately before any future installation.
- Store: `/data/CoordExp/.shared-memory/` is **production**. Never use it as a test fixture. Source-qualified tests use disposable roots, no paid-model calls and never promote fixture conclusions into research.
- Existing `shared-memory` registration is retained. Only an exact owned `shared-memory-dreaming` registration may be removed. `scripts/install-local.py` verifies executable, exact `--root`, `dream gateway --profile` arguments and a profile that exists in the current policy. Unknown similarly named entries stop the cutover.
- The scoped Codex/Pi `--apply` is complete; additional harness deployment requires its own scope. Existing active sessions, native memories, archived receipt bytes, other MCP registrations and unrelated settings are never cleanup targets.

## Installation procedure and completed scope

1. Establish scoped authorization and the selected harness owners. The subsequent user request covered Codex and Pi Web; Claude and WebCodex deployment were not selected. Inspect active sessions and apply configuration only where current turns are not interrupted; no blanket restart or cross-owner process kill.
2. Inspect the current `registry.json`, `dreaming/policy.json`, `routing/<project>.json`, `config.toml`, Codex `hooks.json`, Pi `mcp.json`/`settings.json` and only explicitly selected Claude settings. Preserve exact existing bytes and hashes in an operator-private backup. Configuration files are not research data.
3. Run `python scripts/install-local.py --root <store> --cli <installed-cli> --codex-home <home> --pi-dir <pi-dir> --cwd <registered-project>` **without** `--apply`; add `--claude-dir <owned-directory>` only if that harness was explicitly approved. Inspect `owned_legacy` and reject any unowned/colliding record or changed policy/CLI path.
4. With explicit authorization, apply the reviewed exact plan at a boundary that preserves active turns. Common provider must be present before removing the old independently configured Dreaming provider. Only the precise owned entries are edited. Codex removal uses its native `mcp remove`; Claude (if opted in) uses native user-scope `mcp remove`; Pi uses guarded JSON projection. Record native tool discovery and the post-write single-provider state.
5. Qualify a **fresh** or safe-to-resume consumer against an isolated disposable store first, then scoped **read-only** production context within the authorized verification scope. Recheck the full resolved session ID, caller cwd, restrictions, selected useful compact units, omissions and byte counts. Existing sessions may retain the older schema; do not force-reload them.
6. Codex/Pi local configuration, backups, policy/routing migration and production readback are completed in the linked receipt. Claude and WebCodex deployment remain outside this activation. Expand one harness at a time only within authorized scope. Record required native/server boundaries and unobserved host internals. Do not claim a model quality or cache-hit benefit from CPU/native-only tests.

## Consumer acceptance and rollback fences

| Surface | Required safe read-path proof | Explicit non-claim |
|---|---|---|
| Codex | Native SessionStart/resume/compact hook for the actual cwd/session; intercepted serialized request and actual unified tool exposure | Cannot erase previously appended history, enforce model adoption or prove paid-model benefit |
| Claude | Owned user-scope hook/MCP registration, intercept actual startup request with a local rejecting provider; native auto-memory settings unchanged | No new paid Haiku authority; no claim of arbitrary fork/long-running compaction behavior |
| Pi/Pi Web | Installed SDK + configured MCP, stable bootstrap, replaceable task packet, failure removal, session isolation, native history unchanged | No real-provider cache-hit/performance experiment |
| WebCodex | Automatic successful `work_on_project` / exact-session resume public serialized result with real `wc_sess_*`, scope, refresh and envelope budget | No pre-first-tool injection or verified ChatGPT Host final model-request inclusion |

Failure to satisfy a required server/native boundary means **hold that consumer**, not "retry with a new Session" or use a second memory provider. Roll back **only** the owned new registration/hook/extension from the exact saved configuration snapshot, after fencing for subsequent unrelated edits. Preserve canonical records, source-use bans, historical receipts and native memories. Older binaries cannot safely be pointed at unsupported new collection formats; do not relabel a format downgrade as rollback.

## First historical batch proposal (deferred, not performed)

Proposed initial owner **selection**, from the current read-only CoordExp example manifest:

- `/data/CoordExp/.worktrees/research-probes/research/index.md`: current research navigation and branch boundaries.
- `/data/CoordExp/.worktrees/research-probes/research/questions/greedy-compilation.md`: question/metric definition, not a result.
- `/data/CoordExp/.worktrees/research-probes/research/experiments/2026-10-08-short-continuation-panel/results.md`: dated result/limitations, not a replacement for current status.

These are **candidates, not admitted DreamRun inputs**. At later authorization, independently recheck existence, current source grants, source size/version, current research owner and Git revision. Do not presume a historical as-of state from the 2026-10-08 filename. Resolve the canonical `research-probes` Git identity and any current branch/commit then; do not guess an old SHA.

The matching Codex/Pi native session selections are **deliberately unresolved** until the approved batch inventory identifies actual file/branch/leaf and exact event ranges. Use public bounded readers and real provenance; exclude quoted/delegated messages from live correction and require historical attribution evidence. Do not interpret this unresolved selector as full historical coverage.

Initial optional review envelope, subject to explicit future authorization: at most **3 exact document owners + 2 selected native task segments**, `source_bytes <= 256 KiB`, `events <= 32`, `operations <= 8`, `drafts <= 2`, **0 paid model calls** unless separately authorized later; one active lane, fixed review objective and review checkpoint; output under a new operator-reviewed evidence owner. This proposed envelope may be reduced, not silently expanded, after real file sizes are checked.

**Stop rules:** stop on changed/missing/revoked grants, unknown or duplicate native event identity, unproven Pi ancestry, unreviewed attribution, crossing a branch/owner boundary, an active lane/takeover conflict, exhausted budget, incomplete pagination or unresolved effects. A technical reading failure is `pending-review`, **not** scientific null. Before any publication, search active/inactive candidate and disposition records, reconcile exact source identities, preserve counterevidence and avoid duplicate or revived claims. A no-signal source may legitimately generate no memory. Do not run across `external/`, model weights, datasets, bulk `outputs/`, credentials or all session histories.

After a successful first batch, the next **separately approved** batches may inspect independent `codex-tools/` projects and eventually root `/data/CoordExp` mixed sessions, keeping their project identity and review objective distinct. Neither the above proposal nor the technical implementation includes executing that bootstrap.

## Later WebCodex activation

The separately requested local WebCodex update was installed and externally verified on 2026-10-09; see the later acceptance section. The user will initiate Dreaming from ChatGPT web. The historical proposal above was not executed, and no DreamRun was created by deployment acceptance.
