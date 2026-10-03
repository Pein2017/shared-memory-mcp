## 1. Package and canonical store

- [x] 1.1 Create the self-contained Python >=3.11 package, CLI entrypoint, and official MCP dependency; verify import, CLI help, and an isolated packaging/install check without relying on CoordExp-specific source paths.
- [x] 1.2 Implement fenced-JSON Markdown record validation and provenance-preserving round-trip; verify all nine kinds, metadata/body fidelity, invalid schemas, invalid IDs, malformed lifecycle fields, and source validation with consumer tests.
- [x] 1.3 Implement operator initialization, stable project registration, and scope resolution; verify symlink/subdirectory aliases, linked worktrees, explicitly nested registered projects, unregistered independent nested repositories, ambiguous mappings, and project-hint mismatch.

## 2. Lifecycle, concurrency, and recall

- [x] 2.1 Implement candidate proposal and explicit reviewed promotion with accepted-content preservation; verify candidates stay out of default recall and evidence-free promotion fails without mutation.
- [x] 2.2 Implement atomic successor-based supersession and explicit expiry; verify same-scope restrictions, cycles/self-edges, already superseded targets, full-set lifecycle resolution before retrieval limits, and no predecessor resurrection after successor expiry.
- [x] 2.3 Implement the SQLite local-writer gate, operation-key conflict checks, contained atomic file publication, and receipt recovery; verify simultaneous writers, duplicate replay, conflicting replay, ID/path collision, symlink escape, bounded lock wait, and failures before/after publication with falsifying tests.
- [x] 2.4 Implement scoped search/read/context using deterministic lexical recall and frozen response envelopes; verify filtering before limits, unavailable out-of-scope IDs, exact total output character budgets including the current caller-context header, correct native session provenance, omissions, inactive visibility, and read-only recall.
- [x] 2.5 Implement doctor diagnostics and document operational-state recovery/support bounds; verify malformed canonical state, missing/inconsistent coordination state, and unpublished temporary files are handled explicitly without silent data loss.

## 3. MCP and native adapters

- [x] 3.1 Expose the six core operations through the official SDK stdio transport and CLI; verify an actual SDK client can initialize, list tools, propose/promote, and recall from the same isolated store.
- [x] 3.2 Implement the supported Codex native hook adapter using installed event envelopes and actual session cwd; verify startup/resume/clear/compact behavior, empty diagnostic responses for unmapped scope, bounded additionalContext, and no capture/instruction-file writes. Retained Claude code is an inactive prototype, outside supported-harness acceptance and actual configuration access.
- [x] 3.3 Implement the Pi native extension/MCP adapter with actual session cwd and owned-message replacement; verify native extension startup/compaction and repeated context conversion include at most one current owned message without model calls.
- [x] 3.4 Supply shared semantic capture/promotion guidance and Codex/Pi configuration generation; verify examples cover candidate review, evidence provenance, meaningful handoffs, one shared `.codex/skills/shared-memory` entry, and the documented append-only Codex context limitation without promising historical erasure.

## 4. Acceptance and authorized activation

- [x] 4.1 Run isolated integration checks across Codex/Pi installed native paths and the SDK transport over a disposable registered Git project with linked worktrees, including real GPT-6-Luna sessions in both harnesses after live-catalog model resolution; retain command exits and evidence for startup recall, shared IDs/tools, actual session provenance, project isolation, and native-memory preservation. Distinguish explicitly authorized validation model calls from prohibited background extraction.
- [x] 4.2 Prepare and apply narrow idempotent actual Codex/Pi configuration changes, one shared skill entry, and central store/project bindings only after isolated real-model acceptance; verify repeated installation preserves unrelated settings, creates no duplicate owned registrations or skill copies, and leaves actual Claude configuration untouched.
- [x] 4.3 Verify fresh actual configured Codex/Pi sessions consume the bounded shared-memory view and support shared read/write; report any unsupported or unmeasured supported native path explicitly rather than substituting a mock pass. Do not claim Claude support from retained prototype evidence.
- [x] 4.4 Complete user-facing setup, record format, lifecycle, portability, concurrency, troubleshooting, and rollback documentation; verify OpenSpec strict validation and a final owned-change inventory, then report package evidence for lead acceptance without self-granting it.

## Completion evidence and limits

- Package consumer/SDK suite: 47 passed, exit 0. Independent lead counterexamples confirmed collision rejection, subdirectory isolation, and bounded large-body search.
- Installed Codex/Pi CPU startup consumers: pass with no model inference. Actual configurations expose the same six-tool server and correct current session provenance. Codex's configured Responses Lite/code-mode path uses native deferred discovery.
- Three isolated real GPT-6-Luna sessions verified startup recall and bidirectional reviewed capture/read. Later optional Git provenance and compact-search changes were verified with focused consumer/SDK tests and current native CPU consumers; the paid sessions were not rerun.
- Actual activation preserved unrelated/native memory configuration. Repeated installation preserved configuration/adapter bytes, one shared skill entry, and zero canonical production records. Historical/native stores were not imported.
- Current wheel installed outside the checkout and exercised the standard-library core with MCP import blocked. OpenSpec strict validation and explicit source inventory complete the local acceptance record.
- Native resume/compaction event contracts are covered by fixtures and same-version source; additional real-model resume/compaction sessions were not exercised. Codex cannot erase memory from prior history/compacted summaries. Claude remains excluded.
- Raw local qualification receipts are retained under ignored `outputs/`; they are implementation evidence, not research records or portable source assets.
