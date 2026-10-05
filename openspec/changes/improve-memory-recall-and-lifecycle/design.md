## Context

See proposal.md for motivation. Source is the independent repository at `/data/CoordExp/codex-tools/shared-memory-mcp`; the live store is `/data/CoordExp/.shared-memory`. Initial baseline HEAD was `00fb7bcdbf97c771e8080975380e94e2bf258f39`. During planning, the separately owned Pi prefix changes were committed by the other workflow at `7625f088113abd660390b575b8e6de1d0f71cbd5`; their source and tests remain the preserved implementation baseline. The parent and two canonical worktrees were verified. Four older native MCP processes remain running; no service restart is authorized.

The main OpenSpec inventory is empty. Existing in-flight specs and tests define the retained core, public names and adapters. Historical model-qualification language in config does not authorize new model experiments in this task.

## Goals / Non-Goals

**Goals:** navigation to existing evidence owners, low-noise lexical retrieval, cheap useful tool results, independently meaningful uncertainty/status/applicability, reviewed autonomous curation and safe staged adoption.

**Non-Goals:** a second research authority, hard retrieval KPIs, embedding/index service, enforced ontology, per-topic synthesis, new native memory, replacing handoff, or measuring provider cache improvement with new paid calls.

## Decisions

1. Keep version-1 Markdown as the immutable captured-content surface. Store optional curation in `curation/<project>/<record-id>.json` as a small content-digest-bound operation journal. Fold it at read time. This avoids changing existing record bytes or making four old readers reject live migrated files. The journal is retrieval metadata/history, not independent scientific evidence. Old processes ignore it until reconnected; no claim of hot-swapped schemas. Do not use native memories as a second writer or copy full transcripts. New WebCodex provenance is supported by new readers; live migration uses curation of existing records, not incompatible new Markdown provenance.

2. Use `routing/<project>.json` for short description and topic entries (title, aliases, when-to-read, original owner/source references, optional memory IDs). Empty context resolves caller and routing without corpus bodies or activity counters. Routing links existing sources, so a missing local memory ID does not destroy navigation. Keep per-topic synthesis optional and normally absent. A separate local `sharing.json` holds directional engineering-only allowlist entries; it is not inferred from filesystem nesting.

3. A focused retrieval module tokenizes words/identifiers and CJK terms, uses aliases to discover topic routes and expands only explicit curated search_terms (topic co-membership is not synonymy), ranks meaningful matches using field weights and BM25-style term rarity/length normalization, and returns match explanations. Domain preference is a small soft bias after lexical admission. No time decay, popularity boost or automatic contradiction winner. Corpus membership and curation changes contribute to a returned revision. Offset continuation is explicitly revision-bound in the response rather than advertised as a durable cursor.

4. Search cards include optional standalone summary/conditions or a clearly incomplete preview, epistemic kind, source-project attribution, bounded source pointers and full-read path. Drop repeated proposal/review receipts from cards, not from storage. Oversized results still expose an ID/read pointer and advance pagination. Full reads retain provenance; detailed audit is opt-in at the MCP boundary. `context` over MCP avoids echoing both a rendered text and the same cards; adapters still consume the rendered text. Retain the SDK's interoperable structured/text fallback and measure both, rather than claiming every harness deduplicates them.

5. Keep the existing seven operation names and add two coherent operations: `capture` for optional one-call reviewed publication, and `curate` for reviewed metadata and retirement. Existing explicit candidate/approve/update/delete flows remain. Capture first binds the full request digest in an atomic `capture/<project>/<key-digest>.json` receipt under the existing writer gate, then performs replayable candidate, curation and approval stages. A crash may leave only the binding or a candidate, never an unreviewed active claim. The binding rejects changed review/metadata even after the first candidate write. Completed pre-repair captures recover their digest from curation; legacy partial candidates without a complete binding fail with `incomplete_capture` rather than inventing the original request. Curation shares the existing local write gate and atomic publication mechanism. No generic transaction framework or roles-as-proof system.

6. Foreign recall requires published project scope, `domain=engineering`, explicit record `share_with`, and a matching directional allowlist edge. Read results keep original project identity; mutations always use the caller's resolved original project, never imported visibility. Worktree identity remains physical path, while version applicability lives in conditions. Source-role metadata separates owner, evidence, derivative and origin; optional source-linked relations preserve derivation/conflict without a graph engine.

7. Preserve Pi's stable early snapshot and timestamp behavior. Keep static MCP schema ordering/descriptions and accurate annotations. Default task-time recall is a skill behavior for nontrivial tasks, not a mandatory tool gate or per-turn automatic injection. Codex/Claude append-only boundaries remain; neither can erase already-injected history. Add a bounded CLI public-operation bridge for WebCodex's actual Workflow Session because the current WebCodex local-MCP registry is empty; do not edit Runner service configuration or pretend its separate memory bootstrap is this store.

## Risks / Trade-offs

- Older running clients ignore new curation and continue legacy recall until reconnected. Preserve their current canonical inputs; explicitly report the refresh boundary, and never restart other sessions automatically.
- Text summaries may omit conditions. Keep conditions explicit, label legacy previews, and make consequential use return to the full record and owner.
- Metadata can be stale, conflicting or based on derivative material. Bind it to content, disclose source roles and verification scope, and retain history. Availability is not validity.
- Full local scans remain bounded and currently inexpensive. Do not add a cache without evidence of a real latency bottleneck.
- MCP annotations are hints, not authorization. Source validation verifies structure/identity and caller-supplied review, not truth or external permission.
- Compact search changes presentation assertions. Preserve identity/scope/replay/integrity tests and replace only expectations intentionally changed by these specs.

## Migration Plan

Stage 0: freeze hashes of existing Pi modifications, record current registry/store distribution and validate the native-free baseline; create this change.

Stage 1: implement routing/ranking/cards/explicit full reads and retain stable-prefix tests. Validate isolated temporary stores and real stdio MCP clients without model calls.

Stage 2: add curation/capture/sharing and a source-fenced migration plan. Read all selected handoffs; reuse existing results or original owners; retain uncertain candidates. Curate durable summaries separately from transient job/release state. Apply through the gateway, preserve all Markdown hashes, and retain per-item receipts under `.state/migrations/`.

Stage 3: align owned skill/README and local routing/sharing, add a real-WebCodex CLI route, run compatibility/security/replay/pagination/stdio/native-SDK checks and a few real task walkthroughs. Leave unrelated native settings, Pi files, handoff skill and native memory unchanged. Do not commit/push or archive the change as user-accepted automatically.

Dreaming later reuses these IDs, source relations, replay keys and curation operations. No organizer scheduling or transcript crawl is included now.

## Mechanism references

- MCP tool schema, structured/text compatibility and state-handle guidance: https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/docs/specification/2026-07-28/server/tools.mdx
- OpenAI tool search guidance on stable cached definitions and eager/deferred trade-offs: https://developers.openai.com/api/docs/guides/tools-tool-search
- OpenAI MCP tool-effect annotations (not authorization): https://developers.openai.com/plugins/build/mcp-server

These are public interface references, not evidence about this deployment's provider cache rate. The installed Python SDK and retained harness consumers govern local compatibility.

## Implementation and local acceptance (2026-10-05)

Stages 0–3 are implemented against preserved HEAD `7625f088113abd660390b575b8e6de1d0f71cbd5`. No commit, push, service restart, native-memory write, GPU/model call or dreaming job was performed. Pi adapter and its ordinary-growth regression remain byte-identical to that baseline; the real-CLI probe only updates the navigation reminder and nine-tool catalog assertions.

The full suite reports **123 passed, zero failures/errors** in `outputs/memory-recall-20261005/validation/tests.xml`. `native-sdk-final.json` records four passing installed Pi Web/CLI SDK 1.0.3 checks plus OpenSpec strict validation, skill validation and whitespace checks. Both actual CLI/MCP consumers preserve the previous converted request prefix under ordinary growth with one user-level snapshot, no native-history mutation and zero model/provider calls. Provider cache-hit and task-quality improvement remain unmeasured.

Live migration is recorded under `/data/CoordExp/.shared-memory/.state/migrations/20261005-recall-curation/` as plan.json, operations.jsonl, receipt.json and verification.json. The plan binds 114 original Markdown hashes and 19 source-owner fences. It retires 26 read handoffs plus the dated initialization topic map, and curates two already-published engineering lessons with conditions and explicit sharing. No new raw record or duplicate research synthesis was needed. All 114 original Markdown files and eight protected adapter/config/handoff files remain unchanged; all 29 curation operations replay without changing journal bytes. Of the 27 retirement marks, only four records were previously effective-active; others were already candidates or superseded. Effective active count changes from 67 to 63, not by 27.

Real task walkthroughs find pytest, CPU thread reduction and N4/QP sources; the two marked engineering records are readable from the independent tool project with original attribution, while its N4 query returns no imported research. The local startup navigation contains seven routes at 3145/3199 characters in main/research-probes and three routes at 2038 characters in the tool project, all without record bodies. These are bounded observations, not retrieval KPIs or a benchmark.

Routing and sharing are installed locally, not automatically staged in Git. Raw records, curation journals and local receipts remain untracked. Selective routing version control remains optional. WebCodex uses the tested same-projection CLI bridge with its real session and process cwd; no Runner MCP provider registration was fabricated. Already-running native MCP processes require reconnection before they see new schemas and curation; old canonical input remains readable and no sessions were interrupted. This change is implemented locally and left unarchived for user acceptance.

## Independent acceptance and recovery repair (2026-10-06 Asia/Shanghai)

The receiving lead independently checked the WebCodex candidate against the actual local dirty tree, not a remote branch or conversation summary. Its 123-test baseline passed, all recorded closeout source hashes matched, and all 114 original Markdown records matched the migration plan. A fresh installed Pi SDK/CLI/stdio-MCP fixture passed with nine tools, one stable user-level snapshot and zero model calls. These unchanged adapter/migration checks remain applicable after the following isolated repair.

Fault injection found that interruption after the first candidate publication, before curation, let a retry change review/details under the same capture key. Three RED checks exposed the missing first-write binding. The capture receipt described in decision 5 repairs that boundary; 24 focused checks passed, including exact-payload recovery, conflicting replay, concurrency, corrupted bindings and completed-versus-unbound legacy recovery. The final full suite passed **131 tests**, with strict OpenSpec validation and whitespace checks passing. This candidate is technically accepted by the receiving lead; user acceptance, Git commit/publication and change archival are separate and were not performed.

Evidence remains separate from the original receipts: `outputs/memory-recall-20261005/independent-acceptance-capture/receipt.json` records RED/GREEN and repair source hashes; `outputs/memory-recall-20261005/independent-acceptance-20261006T0147/{binding.json,native.json,final.json,tests-final.xml}` records independent checks. The latter directory label is not an execution timestamp; use the timestamps inside the receipts. Original migration and remote closeout receipts were not rewritten to admit the repaired source.

An existing native MCP reader rejected current routing `search_terms`, while the fresh CLI returned a valid search. Thus a stale intermediate process can fail recall rather than merely ignore curation. Reconnection or a fresh public CLI invocation is required for that consumer; no active session was restarted and routing was not weakened. No provider cache-rate or end-task quality gain is claimed from these CPU checks.
