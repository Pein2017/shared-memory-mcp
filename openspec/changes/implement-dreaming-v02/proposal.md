# Shared-memory Dreaming v0.2

## Why

Implement the user-approved `shared-memory-dreaming-v0.2-implementation-proposal.md` and the 2026-10-07 clarification: Dreaming is a harness-neutral consolidation process that any authorized Agent can perform. A model or client preference does not determine the mechanism, role or authority. Agents can maintain ordinary memory and also undertake local or global consolidation against the same source-linked canonical store.

## What Changes

- Separate operator-issued access grants from Agent-selected bounded DreamRuns, preserving monotonic Attempts, immutable drafts and effect-verifiable publication under the existing local writer gate.
- Keep executor identity separate from authorized targets. Preserve ordinary CRUD and v1 records. Add an explicitly versioned Pein collaboration collection.
- Add independently invalidated research/collaboration views, scoped dispositions, coverage checkpoints and stable review issues.
- Add authorized source discovery and paged public-history reading, full current/historical memory audit, and an Agent-facing CLI/MCP lifecycle for selecting and completing consolidation batches. Retain the fixed-Run endpoint as an optional delegated mode.
- Support multiple authorized projects and all canonical record scopes without falsifying executor cwd or collapsing scope qualifiers. Global consolidation consists of separate recoverable batches.

## Scope and Authority

Working root: `/data/CoordExp/codex-tools/shared-memory-mcp`, initial `main@00feffaf4949892d7dcddfeb6e068f6fb800e9f7`, clean. Runtime Project is `agent:coordexp-web-runner:shared-memory-mcp`; the real memory registry ID is `shared-memory-mcp`, not the Runtime ID. The CoordExp worktrees currently resolve to memory project `coordexp`.

The user authorized necessary architecture changes and implementation using GPT-6.1-Sol medium or Luna max. Design and source implementation plus disposable CPU/real-stdio qualification are in scope. Commits, pushes, deployment, service restarts, production-memory writes, shared harness configuration changes, model/provider calls and GPU experiments remain outside this implementation task. Native harness qualification and a real-data pilot are not implied by source tests.

Following source acceptance, the user separately authorized Pi/Codex installation and Git publication to remote `main`. The [acceptance record](acceptance.md) records that follow-up and the installed ordinary consumer checks. This does not enable a production Dreaming policy, automatic consolidation, a real-history pilot or model inference.

## Non-goals

No scheduler, daemon, model SDK, generic sandbox, leases, new vector store, full transcript mirror, automated research execution, instruction rewriting or whole-store rollback.
