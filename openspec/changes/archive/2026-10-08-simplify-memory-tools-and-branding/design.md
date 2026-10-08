## Context

The existing core has a cooperating SQLite writer gate, atomic single-record Markdown publication, immutable accepted contents, replay identities, exact-scope supersession and bounded active recall. All three clients use the same installed source with harness-specific startup adapters.

## Goals / Non-Goals

Provide seven direct operation names and recognizable packaged metadata without adding dependencies. Make delete useful and auditable while preserving candidate review, provenance, isolation and recovery. No physical deletion, automated consolidation, index changes, background inference, historical receipt rewrites or new harness activation qualification.

## Decisions

Expose `context/search/read/create/approve/update/delete` only. `create` delegates to propose, `approve` to promote, `update` to supersede. Update's `id` is the successor candidate and `old_ids` are predecessors; require the existing explicit source review. Retain existing internal operation digests for replay compatibility. Rename live guidance and probes, preserving historical OpenSpec acceptance text.

`delete(context,id,review,idempotency_key)` appends one reviewed `decision` marker with `withdraws` pointing to exactly one visible target, copying exact scope qualifiers. The marker has review/promotion provenance, no fabricated proposal, expiry or supersession. Include the withdrawal link in the content digest. Reuse reviewed-operation receipt namespace with an explicit delete digest discriminator. Identical replay returns the original marker; conflicting payload/key or repeated new-key withdrawal fails. Target bytes stay unchanged.

Validate markers and their edges from the full corpus before selection. Derive marker status `withdrawal` and target status `withdrawn`, ahead of expiry/supersession. Both are absent from active-only recall. Targets can be candidates, active, expired or superseded records, but never markers. Unique, existing, exact-scope target relations are required. Approval accepts only effective candidates; update only effective active predecessors. Deleting a successor cannot reactivate predecessors. Restore via a fresh reviewed candidate.

Bundle one SVG in package data and copy it into the standalone skill; XML/equality checks protect these two delivery locations. MCP server and tools use supported SDK icon metadata with embedded data URIs; title metadata labels operations. Skill UI references its local icon. Client rendering is conditional on native support; no terminal wrapper or injected image/text decoration is added.

## Risks / Trade-offs

Tool renaming is intentionally breaking for old tool snapshots. Fresh sessions/reconnections are required; do not stop user sessions. Older code cannot read new markers and must fail closed. Public source history includes historical local-path examples, but excludes production stores and account data. Public repository creation and push are explicitly requested by the user.

## Validation

Use pre-change failures for the new catalog and withdrawal invariants, then core/SDK tests covering hiding/history, immutable target bytes, withdrawn-candidate rejection, predecessor non-resurrection, exact scopes, malformed edges, operation collisions, concurrent deletion and crash replay. Inspect icon metadata and wheel assets from outside the checkout. Run the existing three-native offline startup probe once after integration. Inspect actual owned configuration projections, installer plan/idempotence, staged publication paths and final remote revision/visibility.
