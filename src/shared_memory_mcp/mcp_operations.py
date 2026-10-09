"""Thin single-entrypoint MCP schemas; all behavior belongs to public operations."""
from __future__ import annotations

import json
from typing import Literal, TypedDict

from mcp.types import CallToolResult, TextContent

from .operations import call
from .server import CallContext, Record, Details, Review, Source

Collection = Literal['project', 'collaboration', 'history']
Mode = Literal['research', 'general']


class CollaborationRecord(TypedDict):
    __pydantic_config__ = {'extra': 'forbid'}
    claim: dict
    scope: Literal['project', 'worktree', 'task']
    sources: list[Source]


class EpisodeRecord(TypedDict):
    __pydantic_config__ = {'extra': 'forbid'}
    kind: Literal['episode']
    title: str
    body: str
    scope: Literal['project', 'worktree', 'task']
    sources: list[Source]
    episode: dict


class LiveCorrection(TypedDict):
    __pydantic_config__ = {'extra': 'forbid'}
    kind: Literal['direct-current-user']
    excerpt: str
    original_locator: Source | None
    history_gap: str
    review_method: str


class ReviewObjective(TypedDict):
    __pydantic_config__ = {'extra': 'forbid'}
    id: str
    question: str


class ModeRestriction(TypedDict):
    __pydantic_config__ = {'extra': 'forbid'}
    mode: Mode
    basis: Literal['explicit-user-restriction']


class DetailPage(TypedDict):
    __pydantic_config__ = {'extra': 'forbid'}
    id: str
    revision: str
    offset: int


PublicRecord = Record | CollaborationRecord | EpisodeRecord


def register(server, store, *, icons, readonly, append, revise):
    def invoke(name, **arguments):
        payload = call(store, name, arguments)
        # FastMCP's native CallToolResult bypasses automatic structured/text duplication.
        return CallToolResult(content=[TextContent(type='text', text=json.dumps(payload, ensure_ascii=False, allow_nan=False))])

    @server.tool(title='Recall shared context', icons=icons, annotations=readonly)
    def context(context: CallContext, query: str = '', limit: int = 8, max_chars: int = 6000,
                task_mode: Mode | None = None, max_bytes: int = 8000,
                mode_restriction: ModeRestriction | None = None, previous_revision: str | None = None,
                current_status: bool = False) -> CallToolResult:
        """Get dated background, then bind a task mode/query. Modes are soft preferences; current judgments need current-owner checks. One combined serialized budget."""
        return invoke('context', context=context, query=query, limit=limit, max_chars=max_chars,
                      task_mode=task_mode, max_bytes=max_bytes, mode_restriction=mode_restriction, previous_revision=previous_revision, current_status=current_status)

    @server.tool(title='Search scoped memory', icons=icons, annotations=readonly)
    def search(context: CallContext, query: str, limit: int = 20, include_inactive: bool = False,
               collection: Collection = 'project', domain: str | None = None, offset: int = 0,
               include_shared: bool = True, expected_revision: str | None = None,
               task_mode: Mode | None = None, mode_restriction: ModeRestriction | None = None) -> CallToolResult:
        """Find knowledge, preferences or explicitly selected history. Continue with expected_revision. Cross-mode evidence remains eligible unless the user explicitly restricts it."""
        return invoke('search', context=context, query=query, limit=limit, include_inactive=include_inactive,
                      collection=collection, domain=domain, offset=offset, include_shared=include_shared,
                      expected_revision=expected_revision, task_mode=task_mode, mode_restriction=mode_restriction)

    @server.tool(title='Read source-linked detail', icons=icons, annotations=readonly)
    def read(context: CallContext, ids: list[str], include_inactive: bool = False, audit: bool = False,
             include_shared: bool = True, collection: Collection = 'project', max_bytes: int = 12000,
             page: DetailPage | None = None) -> CallToolResult:
        """Read original retained fields; audit adds review receipts. Oversized items return exact revision-fenced JSON-fragment continuation. Reassemble fragments before using claims."""
        return invoke('read', context=context, ids=ids, include_inactive=include_inactive, audit=audit,
                      include_shared=include_shared, collection=collection, max_bytes=max_bytes, page=page)

    @server.tool(title='Create a scoped candidate', icons=icons, annotations=append)
    def create(context: CallContext, record: PublicRecord, idempotency_key: str,
               collection: Collection = 'project') -> CallToolResult:
        """Capture an unpublished candidate in its explicit collection. History uses kind=episode and original ranges; it never becomes startup knowledge."""
        return invoke('create', context=context, record=record, idempotency_key=idempotency_key, collection=collection)

    @server.tool(title='Approve reviewed knowledge', icons=icons, annotations=revise)
    def approve(context: CallContext, id: str, review: Review, idempotency_key: str,
                collection: Collection = 'project') -> CallToolResult:
        """Publish the unchanged scoped candidate after source review. Inferred preferences remain labeled inferred; active is not scientific proof."""
        return invoke('approve', context=context, id=id, review=review, idempotency_key=idempotency_key, collection=collection)

    @server.tool(title='Publish an exact-scope successor', icons=icons, annotations=revise)
    def update(context: CallContext, id: str, old_ids: list[str], review: Review, idempotency_key: str,
               collection: Collection = 'project') -> CallToolResult:
        """Publish successor candidate id and retire exact-scope old_ids. Withdrawing the successor never revives predecessors."""
        return invoke('update', context=context, id=id, old_ids=old_ids, review=review, idempotency_key=idempotency_key, collection=collection)

    @server.tool(title='Withdraw scoped memory', icons=icons, annotations=revise)
    def delete(context: CallContext, id: str, review: Review, idempotency_key: str,
               collection: Collection = 'project') -> CallToolResult:
        """Logical withdrawal with retained provenance. No physical erasure, source edit or permission to execute a remembered plan."""
        return invoke('delete', context=context, id=id, review=review, idempotency_key=idempotency_key, collection=collection)

    @server.tool(title='Capture reviewed contribution', icons=icons, annotations=append)
    def capture(context: CallContext, record: PublicRecord, idempotency_key: str,
                review: Review | None = None, details: Details | None = None,
                collection: Collection = 'project', live_correction: LiveCorrection | None = None,
                source_review: list[dict] | None = None) -> CallToolResult:
        """Ordinary one-call capture. live_correction is ONLY an authorized direct current unquoted user correction with bounded excerpt and disclosed missing locator, never human authentication. Historical collaboration needs granted source_review."""
        args = dict(context=context, record=record, idempotency_key=idempotency_key, review=review,
                    details=details, collection=collection, live_correction=live_correction)
        if source_review is not None:
            args['source_review'] = source_review
        return invoke('capture', **args)

    @server.tool(title='Curate or retire a memory', icons=icons, annotations=revise)
    def curate(context: CallContext, id: str, review: Review, idempotency_key: str,
               details: Details | None = None, retired: bool | None = None,
               expected_content_digest: str | None = None, expected_revision: str | None = None,
               collection: Collection = 'project') -> CallToolResult:
        """Reviewed metadata/retirement with exact revision fences. Correct assertions with successors, not metadata edits; retired does not mean false."""
        return invoke('curate', context=context, id=id, review=review, idempotency_key=idempotency_key,
                      details=details, retired=retired, expected_content_digest=expected_content_digest,
                      expected_revision=expected_revision, collection=collection)

    @server.tool(title='Discover consolidation grants', icons=icons, annotations=readonly)
    def dream_catalog(context: CallContext, cursor: str | None = None, limit: int = 50) -> CallToolResult:
        """Discover stable configured source/target grants and existing work before manually requested consolidation."""
        return invoke('dream_catalog', context=context, cursor=cursor, limit=limit)

    @server.tool(title='Audit retained memory', icons=icons, annotations=readonly)
    def memory_audit(context: CallContext, target_project: str | None = None, collection: str = 'research',
                     ids: list[str] | None = None, query: str = '', statuses: list[str] | None = None,
                     scopes: list[str] | None = None, cursor: str | None = None,
                     limit: int = 20, max_chars: int = 16000) -> CallToolResult:
        """Audit retained canonical history under current grants; delivery is not semantic review."""
        return invoke('memory_audit', context=context, target_project=target_project, collection=collection,
                      ids=ids, query=query, statuses=statuses, scopes=scopes, cursor=cursor, limit=limit, max_chars=max_chars)

    @server.tool(title='List granted sources', icons=icons, annotations=readonly)
    def source_list(context: CallContext, grant_id: str, relative_dir: str = '', cursor: str | None = None,
                    limit: int = 50) -> CallToolResult:
        """List a granted source root without escaping or inventing source identities."""
        return invoke('source_list', context=context, grant_id=grant_id, relative_dir=relative_dir, cursor=cursor, limit=limit)

    @server.tool(title='Read a source page', icons=icons, annotations=readonly)
    def source_read(context: CallContext, selection: dict, cursor: str | None = None,
                    max_bytes: int = 262144, max_events: int = 128) -> CallToolResult:
        """Read one bounded original public page, preserving branch, version, exclusions and exact continuation."""
        return invoke('source_read', context=context, selection=selection, cursor=cursor, max_bytes=max_bytes, max_events=max_events)

    @server.tool(title='Start bounded review', icons=icons, annotations=append)
    def run_start(context: CallContext, review_objective: ReviewObjective, target_project: str | None = None,
                  sources: list[dict] | None = None, reconsider: str | None = None) -> CallToolResult:
        """Start a manually requested bounded review objective. Check existing lane first; a new question cannot bypass a live Run or source prohibitions."""
        return invoke('run_start', context=context, review_objective=review_objective,
                      target_project=target_project, sources=sources, reconsider=reconsider)

    @server.tool(title='Observe review status', icons=icons, annotations=readonly)
    def run_observe(context: CallContext, run_id: str) -> CallToolResult:
        """Observe source changes, objective completion, pending review and unresolved effects separately."""
        return invoke('run_observe', context=context, run_id=run_id)

    @server.tool(title='Take over exact review', icons=icons, annotations=revise)
    def run_takeover(context: CallContext, run_id: str, generation: int) -> CallToolResult:
        """Explicitly take over an authorized attempt; invalidate the old generation, never impersonate its caller."""
        return invoke('run_takeover', context=context, run_id=run_id, generation=generation)

    @server.tool(title='Read frozen materials', icons=icons, annotations=readonly)
    def run_materials(context: CallContext, run_id: str, source_id: str | None = None,
                      event_key: str | None = None, cursor: str | None = None, max_chars: int = 4096) -> CallToolResult:
        """Read admitted frozen material; long-event pages preserve original identity, but reading does not mark review complete."""
        return invoke('run_materials', context=context, run_id=run_id, source_id=source_id,
                      event_key=event_key, cursor=cursor, max_chars=max_chars)

    @server.tool(title='Read review changes', icons=icons, annotations=readonly)
    def run_changes(context: CallContext, run_id: str, max_bytes: int = 12000) -> CallToolResult:
        """Read bounded changes against the consumed objective baseline, retaining missing sources and pending work."""
        return invoke('run_changes', context=context, run_id=run_id, max_bytes=max_bytes)

    @server.tool(title='Freeze reviewed draft', icons=icons, annotations=append)
    def draft_submit(context: CallContext, run_id: str, generation: int, operations: list[dict],
                     reconsider_reason: str | None = None) -> CallToolResult:
        """Freeze reviewed source-linked operations against the current attempt and exact basis."""
        return invoke('draft_submit', context=context, run_id=run_id, generation=generation,
                      operations=operations, reconsider_reason=reconsider_reason)

    @server.tool(title='Read frozen draft', icons=icons, annotations=readonly)
    def draft_read(context: CallContext, run_id: str, revision: str) -> CallToolResult:
        """Read the immutable candidate diff before publishing; current source restrictions still apply."""
        return invoke('draft_read', context=context, run_id=run_id, revision=revision)

    @server.tool(title='Publish reviewed draft', icons=icons, annotations=revise)
    def draft_publish(context: CallContext, run_id: str, generation: int, revision: str) -> CallToolResult:
        """Publish exactly the frozen permitted operations, reconciling prior effects. No caller-selected publisher privilege."""
        return invoke('draft_publish', context=context, run_id=run_id, generation=generation, revision=revision)

    @server.tool(title='Mark reviewed coverage', icons=icons, annotations=append)
    def coverage_mark(context: CallContext, run_id: str, generation: int, statuses: dict[str, str]) -> CallToolResult:
        """Mark frozen events processed/excluded/no-signal/pending-review, not whole-history or objective completion."""
        return invoke('coverage_mark', context=context, run_id=run_id, generation=generation, statuses=statuses)

    @server.tool(title='Close review batch', icons=icons, annotations=append)
    def run_close(context: CallContext, run_id: str, generation: int, abandon_reason: str | None = None,
                  objective_outcome: Literal['reviewed', 'disposed'] | None = None) -> CallToolResult:
        """Reconcile effects and close a batch. Pending review stays actionable even with unchanged source bytes."""
        return invoke('run_close', context=context, run_id=run_id, generation=generation,
                      abandon_reason=abandon_reason, objective_outcome=objective_outcome)

    @server.tool(title='Read scoped overview', icons=icons, annotations=readonly)
    def overview_read(context: CallContext, view: Literal['research', 'collaboration'], scenario: str,
                      target_project: str | None = None, max_chars: int = 8000, max_bytes: int = 8000,
                      historical: str | None = None, compact: bool = True,
                      unit_index: int | None = None, page: DetailPage | None = None) -> CallToolResult:
        """Read qualified dated units without execution-profile membership. Compact text is reviewed; revoked content stays hidden even in history."""
        return invoke('overview_read', context=context, view=view, scenario=scenario, target_project=target_project,
                      max_chars=max_chars, max_bytes=max_bytes, historical=historical, compact=compact,
                      unit_index=unit_index, page=page)

    @server.tool(title='Suggest owner improvement', icons=icons, annotations=append)
    def issue_suggest(context: CallContext, run_id: str, generation: int, topic: str, relation: str, note: str,
                      observations: dict, semantic_reviewed: bool = False) -> CallToolResult:
        """Retain a source-linked inference/owner-improvement proposal, never execute it or rewrite formal owners."""
        return invoke('issue_suggest', context=context, run_id=run_id, generation=generation, topic=topic,
                      relation=relation, note=note, observations=observations, semantic_reviewed=semantic_reviewed)

    @server.tool(title='Search review proposals', icons=icons, annotations=readonly)
    def issue_search(context: CallContext, query: str = '', include_resolved: bool = False, limit: int = 8) -> CallToolResult:
        """Find scoped unresolved proposals and their source pointers; they remain advisory under the current task authority."""
        return invoke('issue_search', context=context, query=query, include_resolved=include_resolved, limit=limit)

    @server.tool(title='Resolve review proposal', icons=icons, annotations=revise)
    def issue_resolve(context: CallContext, id: str, disposition: Literal['accepted', 'rejected', 'handled', 'deferred'],
                      reason: str, expected_revision: str, idempotency_key: str) -> CallToolResult:
        """Record a reviewed proposal disposition. Handled notes do not repeatedly reappear as unresolved."""
        return invoke('issue_resolve', context=context, id=id, disposition=disposition, reason=reason,
                      expected_revision=expected_revision, idempotency_key=idempotency_key)

    for tool in server._tool_manager.list_tools():
        model = tool.fn_metadata.arg_model
        model.model_config['extra'] = 'forbid'
        model.model_rebuild(force=True)
        tool.parameters = model.model_json_schema()
