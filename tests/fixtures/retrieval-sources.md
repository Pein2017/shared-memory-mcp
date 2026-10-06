# Retrieval qualification evidence boundary

The JSON corpus contains synthesized task examples, not copied production memory,
new research results, or labels declaring matching words to be relevant. Each
original source is a checked symbol at package baseline
`7963ccaa59abf8a27a1f86f4e517da124019fd5b`. The cases condition usefulness on the
task's entity, query mode, source validity, or visibility. The source pointers
remain pinned when current onboarding and handoff admission changes.

Seven classes are bounded here: identifier versus split entity; version or query
condition; relevant negative result; long versus concise query; CJK curated alias
and unknown paraphrase; derivative versus original; retired handoff and foreign
scope. They are examples from this package's actual scope, capture, curation and
recall task classes. They are not representative production-quality statistics.
The unknown Chinese paraphrase intentionally has no supplied route expansion.
Zero results are a limitation to report, not a reason to tune ranking.

Run `python scripts/qualify-retrieval.py` from an environment with this package
installed. It constructs one temporary isolated store, seeds historical version-1
fixture bytes (including a legacy handoff), exercises actual search/read/curation,
prints JSON and removes the store. It never seeds or queries a configured live
store. No provider/model calls occur. All complete match ranks are observed via
revision-fenced pagination. First-page omission and incomplete preview are
separate from a complete lexical miss. Expected useful targets are read to verify
the complete pointers; the runner does not certify source truth.

## Derivative example

This deliberately synthesized summary repeats the package computation:
`projected_records` preserves the canonical `lifecycle_status`, applies validated
curation `recall_retired`, and maps an active retired record's `effective_status`
to retired. This document is a derivative explanation. The original implementation
in `src/shared_memory_mcp/curation.py` is the decision-bearing source; retrieving
this summary alongside it does not provide independent corroboration.

## Read-only live-task walkthrough for the lead

A worker without its own native caller identity must not impersonate the lead.
Use the lead's actual `caller_context` to query the central store, follow the
returned revision-fenced pages, full-read useful IDs, and inspect original owners.
Record zero results or applicability mismatches honestly. Suggested bounded tasks:

| Task question | Concise query | Original expected owner to inspect |
| --- | --- | --- |
| Which capture recovery condition requires identical payload and which legacy candidate must fail closed? | `capture idempotency incomplete_capture` | Package `src/shared_memory_mcp/curation.py`, `capture`, baseline above; the relevant original interruption acceptance receipt if returned |
| Do historical handoff creation counts describe current ordinary recall? | `retirement handoff lifecycle` | Package `src/shared_memory_mcp/curation.py`, `projected_records`; original store migration receipt named by a returned source, including its actual time/conditions |
| Can a server cwd resolve an independent nested caller repository? | `shared-memory-mcp scope nested repository` | Package `src/shared_memory_mcp/core.py`, `MemoryStore._resolve`; actual onboarding change owner for new behavior |

These expected source owners are navigation targets, not a promise that an
already-captured memory exists. A live walkthrough supports this task only;
neither it nor the synthesized corpus establishes global recall precision or
token/latency savings.

## Lifecycle report

`python scripts/report-memory-lifecycle.py --root /path/to/store --since
2026-10-04T00:00:00Z --until 2026-10-05T00:00:00Z` prints JSON only. Creation
selection is inclusive since and exclusive until. Optional `--project` and
`--harness` restrict project and origin harness. Current projection counts cover
all selected retained records and separately the creation cohort. Retirement,
candidate, supersession, withdrawal and expiry use existing validated projection
under the coordination gate. There is no complete historical as-of reconstruction
or tool invocation meter. Retain previous receipts and append any correction.
