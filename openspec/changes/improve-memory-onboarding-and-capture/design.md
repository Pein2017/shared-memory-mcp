## Context

See proposal.md. Baseline is clean HEAD `7963ccaa59abf8a27a1f86f4e517da124019fd5b`. Current adapters reduce scope diagnostics to generic failure codes. The existing `register` CLI already preserves Git common identity and serializes registry publication. The core shares one record validator between new writes and legacy decoding, so removing handoff from the global kind set would corrupt legacy reads. The curation journal already distinguishes retirement from lifecycle status.

The prior audit receipt is `outputs/usage-audit-20261006T141822Z.json`. Its historical creation counts are retained as evidence, but its raw lifecycle classification did not fold curation and must not be presented as default recall status. Source-reviewed migration at 2026-10-05T17:06:13Z retired all 26 handoffs; all 20 handoffs created in the audit window predate that migration.

## Goals / Non-Goals

**Goals:** actionable autonomous onboarding of the task's verified repository; source-reviewed low-cost capture; durable write admission without corrupting history; reproducible retrieval cases and retirement-aware reporting.

**Non-Goals:** silent registration inside a read-only operation, automatic project sharing, source rewrites, semantic progress classification, a new organizer/registry framework, ranked-retrieval tuning without counterexamples, provider/model calls or stopping sessions.

## Decisions

1. Add a bounded read-only CLI project-discovery surface using the existing Git/scope helpers. Return the real Git root/common identity, resolved or suggested project ID, rejection code and shell-safe existing-register arguments when onboarding is unambiguous. Hints are diagnostics, not memory. Preserve the diagnostics in native hooks/Pi without echoing raw events or secrets. The skill authorizes agent-driven registration of the current task's verified first-party repo under the user's grant, followed by retry with the resolved identity. Existing manual non-Git registration stays available, but no non-Git/ambiguous binding is automatically invented. New independent repo IDs use readable names and avoid merging name collisions; linked worktrees reuse common identity. Do not widen deliberate subdirectory bindings to sibling paths. Search/context remain read-only and unknown scopes return no project knowledge.

2. Keep legacy shape validation, canonical decoding and content digests unchanged. Apply the handoff ban only at new proposal/capture/publication admission after checking exact completed retries. Validate a rejected handoff before publishing a capture binding or any candidate. Completed legacy operations retain same-key/same-payload replay and changed-key/payload conflict checks. An unfinished legacy handoff capture or candidate cannot continue into a new publication; its existing files remain unchanged and the error explains the policy. Retiring/withdrawing or explicitly reading legacy history remains possible. Public write schemas no longer advertise handoff as a new record kind; the transport must still admit completed legacy replay requests, so runtime validation carries the policy if schema rejection would prevent replay.

3. Keep the nine MCP operations. Prefer capture with source-checked review and compact optional conditions/summary; use a candidate when interpretation is unresolved. Preserve stable source-event keys and exact uncertain-operation replay. Local handoff documents remain an independent transport. These rules belong to the shared skill; substantial examples can live in one focused reference.

4. Freeze `recall.rank`, tokenization, weights, query expansion and domain behavior. Build a bounded case corpus from actual observed task classes and checked owners with explicit targets, nearest distractors and applicability/epistemic explanations. Compare original and concise query forms without declaring token overlap to be relevance. Include entity/version differences, relevant negative results, CJK/aliases, derivative sources, retirement and project isolation. Report misses honestly; only a demonstrated recurring discriminator justifies a later explicit constraint.

5. A small read-only lifecycle report folds canonical status with existing curation and separates created-in-window events from current recall eligibility. It exposes bounded counts and preserves retired history; it is not a server invocation/latency meter. Preserve the original audit receipt and append a correction receipt rather than rewriting its historical evidence.

## Risks / Trade-offs

- Older loaded processes retain older admission/recall behavior → qualify fresh installed consumers and document reconnect; do not force-restart sessions.
- Scope-name collisions or subdirectory trust boundaries → prefer known Git identity and fail clearly instead of merging or widening.
- Metadata/summary is not proof → keep original source conditions and interpretation boundaries; no automatic contradiction winner or age-based truth decay.
- A record can disguise progress under another kind → clear skill guidance and source review; no speculative classifier.
- Broad lexical candidates may remain → report decisive target/distractor cases, not a vanity average score or unsupported precision claim.

## Migration Plan

Implement and qualify isolated CLI/MCP and native adapter consumers. Reuse the editable installation and one shared skill; preserve actual config entries. Register only the verified WebCodex Git top level with the existing CLI and validate fresh caller scope/empty independent recall. Keep all old record/curation bytes and sharing policy unchanged. Record exact test and consumer receipts, retirement-aware correction and remaining retrieval limits at this change. No record migration, publication or archival is required.
