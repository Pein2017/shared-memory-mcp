## Context

See proposal.md. The existing context handler filters owned messages and appends
one snapshot at the tail. SDK context conversion restores its leading system
messages and converts the custom snapshot to user-level input. The same Web
runtime also has a separate official-compaction transport defect; neither a
source change nor an extension-disabled child proves the historical cache cause.

## Goals / Non-Goals

**Goals:** stable placement during ordinary continuation; unchanged lifecycle
freshness, identity, bounded output, failure clearing and native history.

**Non-Goals:** permanent snapshots, canonical writes, new recall schedules,
system/developer authority, provider-specific breakpoints or a promised hit rate.

## Decisions

Insert the one current snapshot before conversation messages, after any leading
system messages exposed by a caller. This deterministic position avoids a
separate anchor store and works across normal growth. Preserve owned filtering
so stale/duplicated snapshots cannot survive. Fresh refresh legitimately changes
the prefix; cache retention never overrides withdrawal or scoped freshness.

Keep the snapshot ephemeral and user-level. Persisting append-only snapshots
would change history and replacement semantics; adding cache markers would
depend on unsupported backend-specific request fields.

## Risks / Trade-offs

- A refresh changes the early prefix → preserve freshness and report cache cost.
- Other extensions or stateful transport may still break reuse → separate
  provider contrasts from this adapter regression.
- SDK context conversion varies by version → use installed Web 1.0.0 and managed
  terminal 1.0.3 retained callers for narrow deterministic qualification.

## Migration Plan

The existing runtime wrapper imports maintained source. Qualify the native
adapter before fresh Web/terminal activation; preserve source-based rollback.
Do not rewrite native transcripts or canonical records.
