"""Thin single-entrypoint MCP schemas for the v0.3 surface; all behavior belongs to public operations."""
from __future__ import annotations

import json
from typing import Literal, Required, TypedDict

from mcp.types import CallToolResult, TextContent

from .core import MemoryError
from .operations import PUBLIC, call, check_arguments, failure
from .server import Caller, Record, Details, Review, Source

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


class ReviewObjective(TypedDict, total=False):
    __pydantic_config__ = {'extra': 'forbid'}
    id: Required[str]
    question: Required[str]
    reread: list[dict]


class ModeRestriction(TypedDict):
    __pydantic_config__ = {'extra': 'forbid'}
    mode: Mode
    basis: Literal['explicit-user-restriction']


PublicRecord = Record | CollaborationRecord | EpisodeRecord


def _text(payload, error=False):
    # FastMCP's native CallToolResult bypasses automatic structured/text duplication.
    return CallToolResult(content=[TextContent(type='text', text=json.dumps(payload, ensure_ascii=False, allow_nan=False))],
                          isError=error)


def error_result(exc):
    diagnostic = getattr(exc, 'diagnostic', None) or {'code': exc.code, 'message': str(exc)}
    return _text({'status': 'error', 'diagnostic': diagnostic}, error=True)


def register(server, store, *, icons, readonly, append, revise):
    def invoke(name, **arguments):
        try:
            return _text(call(store, name, arguments))
        except MemoryError as exc:
            return error_result(exc)

    @server.tool(title='Recall shared context', icons=icons, annotations=readonly)
    def context(caller: Caller, query: str = '', limit: int = 8, max_bytes: int = 8000,
                task_mode: Mode | None = None, mode_restriction: ModeRestriction | None = None,
                previous_revision: str | None = None, current_status: bool = False) -> CallToolResult:
        """Get dated background, then bind a task mode/query. Modes are soft preferences; current judgments need current-owner checks. One combined serialized budget; previous_revision returns an unchanged receipt."""
        return invoke('context', caller=caller, query=query, limit=limit, max_bytes=max_bytes, task_mode=task_mode,
                      mode_restriction=mode_restriction, previous_revision=previous_revision, current_status=current_status)

    @server.tool(title='Search scoped memory', icons=icons, annotations=readonly)
    def search(caller: Caller, query: str = '', limit: int = 20, collection: Collection = 'project',
               include_inactive: bool = False, include_shared: bool = True, domain: str | None = None,
               task_mode: Mode | None = None, mode_restriction: ModeRestriction | None = None,
               statuses: list[str] | None = None, scopes: list[str] | None = None,
               cursor: str | None = None) -> CallToolResult:
        """Find knowledge, preferences or explicitly selected history; continue with next_cursor. statuses/scopes list effective lifecycle status (candidate, stale, superseded, expired, withdrawn, retired) without making records recall-eligible."""
        return invoke('search', caller=caller, query=query, limit=limit, collection=collection,
                      include_inactive=include_inactive, include_shared=include_shared, domain=domain,
                      task_mode=task_mode, mode_restriction=mode_restriction, statuses=statuses, scopes=scopes, cursor=cursor)

    @server.tool(title='Read source-linked detail', icons=icons, annotations=readonly)
    def read(caller: Caller, ids: list[str], collection: Collection = 'project', include_inactive: bool = False,
             include_shared: bool = True, audit: bool = False, max_bytes: int = 12000,
             cursor: str | None = None) -> CallToolResult:
        """Read original retained fields and each record's revision; audit adds review receipts. Oversized items return a cursor for exact JSON-fragment continuation; reassemble fragments before using claims."""
        return invoke('read', caller=caller, ids=ids, collection=collection, include_inactive=include_inactive,
                      include_shared=include_shared, audit=audit, max_bytes=max_bytes, cursor=cursor)

    @server.tool(title='Capture a record', icons=icons, annotations=append)
    def capture(caller: Caller, record: PublicRecord, review: Review | None = None, details: Details | None = None,
                collection: Collection = 'project', live_correction: LiveCorrection | None = None,
                source_review: list[dict] | None = None, idempotency_key: str | None = None) -> CallToolResult:
        """Capture a source-linked record. Without review it stays an unpublished candidate; with review it publishes. live_correction is ONLY an authorized direct current unquoted user correction, never human authentication. History uses kind=episode. Omitted idempotency_key is derived and returned."""
        return invoke('capture', caller=caller, record=record, review=review, details=details, collection=collection,
                      live_correction=live_correction, source_review=source_review, idempotency_key=idempotency_key)

    @server.tool(title='Approve reviewed knowledge', icons=icons, annotations=revise)
    def approve(caller: Caller, id: str, review: Review, collection: Collection = 'project',
                idempotency_key: str | None = None) -> CallToolResult:
        """Publish the unchanged scoped candidate after source review. Inferred preferences remain labeled inferred; active is not scientific proof."""
        return invoke('approve', caller=caller, id=id, review=review, collection=collection, idempotency_key=idempotency_key)

    @server.tool(title='Publish an exact-scope successor', icons=icons, annotations=revise)
    def supersede(caller: Caller, id: str, old_ids: list[str], review: Review, collection: Collection = 'project',
                  idempotency_key: str | None = None) -> CallToolResult:
        """Publish successor candidate id and retire the exact-scope predecessor old_ids without rewriting them. Withdrawing the successor never revives predecessors."""
        return invoke('supersede', caller=caller, id=id, old_ids=old_ids, review=review, collection=collection,
                      idempotency_key=idempotency_key)

    @server.tool(title='Withdraw scoped memory', icons=icons, annotations=revise)
    def withdraw(caller: Caller, id: str, review: Review, collection: Collection = 'project',
                 idempotency_key: str | None = None) -> CallToolResult:
        """Auditable logical withdrawal with retained provenance. No physical erasure, source edit or permission to execute a remembered plan."""
        return invoke('withdraw', caller=caller, id=id, review=review, collection=collection, idempotency_key=idempotency_key)

    @server.tool(title='Annotate or retire a memory', icons=icons, annotations=revise)
    def annotate(caller: Caller, id: str, review: Review, details: Details | None = None, retired: bool | None = None,
                 expected_revision: str | None = None, collection: Collection = 'project',
                 idempotency_key: str | None = None) -> CallToolResult:
        """Reviewed metadata/retirement fenced by the revision from read. Correct assertions with supersede, not metadata edits; retired does not mean false."""
        return invoke('annotate', caller=caller, id=id, review=review, details=details, retired=retired,
                      expected_revision=expected_revision, collection=collection, idempotency_key=idempotency_key)

    @server.tool(title='List grants and sources', icons=icons, annotations=readonly)
    def source_list(caller: Caller, grant_id: str | None = None, relative_dir: str = '', cursor: str | None = None,
                    limit: int = 50) -> CallToolResult:
        """Without grant_id: configured source/target grants and active runs. With grant_id: list that granted root without escaping or inventing source identities."""
        return invoke('source_list', caller=caller, grant_id=grant_id, relative_dir=relative_dir, cursor=cursor, limit=limit)

    @server.tool(title='Read a source page', icons=icons, annotations=readonly)
    def source_read(caller: Caller, selection: dict, cursor: str | None = None,
                    max_bytes: int = 262144, max_events: int = 128) -> CallToolResult:
        """Read one bounded original public page, preserving branch, version, exclusions and exact continuation."""
        return invoke('source_read', caller=caller, selection=selection, cursor=cursor, max_bytes=max_bytes, max_events=max_events)

    @server.tool(title='Start bounded review', icons=icons, annotations=append)
    def dream_start(caller: Caller, review_objective: ReviewObjective | None = None, target_project: str | None = None,
                    sources: list[dict] | None = None, reconsider: str | None = None) -> CallToolResult:
        """Start a manually requested bounded review objective, or omit it for the default memory-triage objective. Check existing lanes first; a new question cannot bypass a live run or source prohibitions. Follow `next`."""
        return invoke('dream_start', caller=caller, review_objective=review_objective, target_project=target_project,
                      sources=sources, reconsider=reconsider)

    @server.tool(title='Observe review status', icons=icons, annotations=readonly)
    def dream_status(caller: Caller, run_id: str, max_bytes: int = 12000) -> CallToolResult:
        """Run state, objective progress, pending review, unresolved effects and bounded changes against the consumed baseline, with the run revision and `next`."""
        return invoke('dream_status', caller=caller, run_id=run_id, max_bytes=max_bytes)

    @server.tool(title='Read frozen materials', icons=icons, annotations=append)
    def dream_materials(caller: Caller, run_id: str, source_id: str | None = None, event_key: str | None = None,
                        cursor: str | None = None, max_bytes: int | None = None) -> CallToolResult:
        """Read admitted frozen material; long events page with cursor. Records which material was served; reading does not mark review complete."""
        return invoke('dream_materials', caller=caller, run_id=run_id, source_id=source_id, event_key=event_key,
                      cursor=cursor, max_bytes=max_bytes)

    @server.tool(title='Freeze reviewed draft', icons=icons, annotations=append)
    def dream_draft(caller: Caller, run_id: str, expected_revision: str, operations: list[dict],
                    reconsider_reason: str | None = None) -> CallToolResult:
        """Freeze reviewed source-linked operations against the run revision and return the frozen draft. {"type":"coverage","statuses":{event_key: processed|excluded|no-signal|pending-review}} records coverage."""
        return invoke('dream_draft', caller=caller, run_id=run_id, expected_revision=expected_revision,
                      operations=operations, reconsider_reason=reconsider_reason)

    @server.tool(title='Publish reviewed draft', icons=icons, annotations=revise)
    def dream_publish(caller: Caller, run_id: str, expected_revision: str) -> CallToolResult:
        """Publish exactly the frozen permitted operations of this run revision, reconciling prior effects. No caller-selected publisher privilege."""
        return invoke('dream_publish', caller=caller, run_id=run_id, expected_revision=expected_revision)

    @server.tool(title='Close review batch', icons=icons, annotations=append)
    def dream_close(caller: Caller, run_id: str, expected_revision: str, abandon_reason: str | None = None,
                    objective_outcome: Literal['reviewed', 'disposed'] | None = None,
                    accept_gaps: list[dict] | None = None) -> CallToolResult:
        """Reconcile effects and close a batch. Pending review stays actionable even with unchanged source bytes. accept_gaps names permanent source gaps ({source_id, reason, note}) to advance past."""
        return invoke('dream_close', caller=caller, run_id=run_id, expected_revision=expected_revision,
                      abandon_reason=abandon_reason, objective_outcome=objective_outcome, accept_gaps=accept_gaps)

    @server.tool(title='Take over exact review', icons=icons, annotations=revise)
    def dream_takeover(caller: Caller, run_id: str, expected_revision: str) -> CallToolResult:
        """Explicitly take over an authorized attempt; invalidate the old attempt, never impersonate its caller."""
        return invoke('dream_takeover', caller=caller, run_id=run_id, expected_revision=expected_revision)

    @server.tool(title='Read scoped overview', icons=icons, annotations=readonly)
    def overview(caller: Caller, view: Literal['research', 'collaboration'], scenario: str,
                 target_project: str | None = None, max_bytes: int = 8000, historical: str | None = None,
                 compact: bool = True, unit_index: int | None = None, cursor: str | None = None) -> CallToolResult:
        """Read qualified dated units without execution-profile membership. Compact text is reviewed; revoked content stays hidden even in history."""
        return invoke('overview', caller=caller, view=view, scenario=scenario, target_project=target_project,
                      max_bytes=max_bytes, historical=historical, compact=compact, unit_index=unit_index, cursor=cursor)

    @server.tool(title='Open owner improvement issue', icons=icons, annotations=append)
    def issue_open(caller: Caller, run_id: str, expected_revision: str, topic: str, relation: str, note: str,
                   observations: dict, semantic_reviewed: bool = False) -> CallToolResult:
        """Retain a source-linked inference/owner-improvement proposal, never execute it or rewrite formal owners."""
        return invoke('issue_open', caller=caller, run_id=run_id, expected_revision=expected_revision, topic=topic,
                      relation=relation, note=note, observations=observations, semantic_reviewed=semantic_reviewed)

    @server.tool(title='List review issues', icons=icons, annotations=readonly)
    def issue_list(caller: Caller, query: str = '', include_resolved: bool = False, limit: int = 8,
                   cursor: str | None = None) -> CallToolResult:
        """Find scoped unresolved issues and their source pointers; they remain advisory under the current task authority."""
        return invoke('issue_list', caller=caller, query=query, include_resolved=include_resolved, limit=limit, cursor=cursor)

    @server.tool(title='Close review issue', icons=icons, annotations=revise)
    def issue_close(caller: Caller, id: str, disposition: Literal['accepted', 'rejected', 'handled', 'deferred'],
                    reason: str, expected_revision: str, idempotency_key: str | None = None) -> CallToolResult:
        """Record a reviewed issue disposition. Handled notes do not repeatedly reappear as unresolved."""
        return invoke('issue_close', caller=caller, id=id, disposition=disposition, reason=reason,
                      expected_revision=expected_revision, idempotency_key=idempotency_key)

    manager = server._tool_manager
    for tool in manager.list_tools():
        model = tool.fn_metadata.arg_model
        model.model_config['extra'] = 'forbid'
        model.model_rebuild(force=True)
        tool.parameters = model.model_json_schema()
    assert tuple(tool.name for tool in manager.list_tools()) == PUBLIC

    original = manager.call_tool

    async def call_tool(name, arguments, context=None, convert_result=False):
        """Shape errors and retired names become JSON diagnostics with a minimal correct example."""
        try:
            check_arguments(name, arguments)
            manager.get_tool(name).fn_metadata.arg_model.model_validate(arguments)
        except MemoryError as exc:
            return error_result(exc)
        except Exception as exc:  # pydantic type/shape validation
            try:
                failure('invalid_arguments', f'Arguments do not match `{name}`: {exc}'[:2000], name)
            except MemoryError as shaped:
                return error_result(shaped)
        return await original(name, arguments, context=context, convert_result=convert_result)

    manager.call_tool = call_tool
