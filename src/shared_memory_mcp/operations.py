"""One v0.3 public operation dispatch for MCP and CLI, using real per-call identity.

Public names, arguments, cursors, fences and envelopes live here; internal
functions keep their historical names and receive the caller as ``context``.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json

from .core import MemoryError, _decode, _digest, _fail, _json

ORDINARY = ('context', 'search', 'read', 'capture', 'approve', 'supersede', 'withdraw', 'annotate')
MANUAL = ('source_list', 'source_read', 'dream_start', 'dream_status', 'dream_materials', 'dream_draft',
          'dream_publish', 'dream_close', 'dream_takeover', 'overview', 'issue_open', 'issue_list', 'issue_close')
PUBLIC = (*ORDINARY, *MANUAL)
READ_ONLY = frozenset({'context', 'search', 'read', 'source_list', 'source_read', 'dream_status', 'overview', 'issue_list'})
RETIRED = {'create': 'capture', 'propose': 'capture', 'promote': 'approve', 'update': 'supersede',
           'delete': 'withdraw', 'curate': 'annotate', 'memory_audit': 'search', 'dream_catalog': 'source_list',
           'run_start': 'dream_start', 'run_observe': 'dream_status', 'run_changes': 'dream_status',
           'run_materials': 'dream_materials', 'run_takeover': 'dream_takeover', 'run_close': 'dream_close',
           'draft_submit': 'dream_draft', 'draft_read': 'dream_draft', 'draft_publish': 'dream_publish',
           'coverage_mark': 'dream_draft', 'overview_read': 'overview', 'issue_suggest': 'issue_open',
           'issue_search': 'issue_list', 'issue_resolve': 'issue_close'}
# Former argument names and their v0.3 replacement, named in shape diagnostics.
LEGACY_ARGS = {'context': 'caller', 'offset': 'cursor', 'page': 'cursor', 'generation': 'expected_revision',
               'revision': 'expected_revision', 'expected_content_digest': 'expected_revision', 'max_chars': 'max_bytes'}
CALLER_FIELDS = {'cwd', 'harness', 'session_id', 'actor', 'project_id', 'task_id', 'role', 'model', 'parent_session_id'}
# Ordinary operations pass the whole caller (core retains role/model/parent_session_id as provenance);
# Dreaming engines compare callers exactly across attempts, so they keep receiving only these fields.
CORE_CALLER_FIELDS = ('cwd', 'harness', 'session_id', 'actor', 'task_id', 'project_id')

_CALLER = {'cwd': '/absolute/project/path', 'harness': 'codex', 'session_id': 'CURRENT_SESSION_ID', 'actor': 'agent-name'}
_SOURCES = [{'uri': 'file:///absolute/project/path/owner.md', 'locator': 'L10-L20'}]
_REVIEW = {'reason': 'Checked the claim against the cited source', 'evidence': _SOURCES}
_ID = '0123456789abcdef0123456789abcdef'
EXAMPLES = {
    'context': {'caller': _CALLER, 'query': 'what to recall', 'task_mode': 'research'},
    'search': {'caller': _CALLER, 'query': 'topic words'},
    'read': {'caller': _CALLER, 'ids': [_ID]},
    'capture': {'caller': _CALLER, 'record': {'kind': 'observation', 'title': 'Short title', 'body': 'Source-linked finding',
                                              'scope': 'project', 'sources': _SOURCES}},
    'approve': {'caller': _CALLER, 'id': _ID, 'review': _REVIEW},
    'supersede': {'caller': _CALLER, 'id': _ID, 'old_ids': ['fedcba9876543210fedcba9876543210'], 'review': _REVIEW},
    'withdraw': {'caller': _CALLER, 'id': _ID, 'review': _REVIEW},
    'annotate': {'caller': _CALLER, 'id': _ID, 'review': _REVIEW, 'retired': True, 'expected_revision': 'REVISION_FROM_READ'},
    'source_list': {'caller': _CALLER},
    'source_read': {'caller': _CALLER, 'selection': {'grant_id': 'GRANT_ID', 'path': 'relative/file.jsonl'}},
    'dream_start': {'caller': _CALLER, 'review_objective': {'id': 'objective-id', 'question': 'What should be reviewed?'}},
    'dream_status': {'caller': _CALLER, 'run_id': _ID},
    'dream_materials': {'caller': _CALLER, 'run_id': _ID},
    'dream_draft': {'caller': _CALLER, 'run_id': _ID, 'expected_revision': 'REVISION_FROM_DREAM_STATUS',
                    'operations': [{'type': 'coverage', 'statuses': {'EVENT_KEY': 'no-signal'}}]},
    'dream_publish': {'caller': _CALLER, 'run_id': _ID, 'expected_revision': 'REVISION_FROM_DREAM_DRAFT'},
    'dream_close': {'caller': _CALLER, 'run_id': _ID, 'expected_revision': 'REVISION_FROM_DREAM_STATUS'},
    'dream_takeover': {'caller': _CALLER, 'run_id': _ID, 'expected_revision': 'REVISION_FROM_DREAM_STATUS'},
    'overview': {'caller': _CALLER, 'view': 'research', 'scenario': 'research'},
    'issue_open': {'caller': _CALLER, 'run_id': _ID, 'expected_revision': 'REVISION_FROM_DREAM_STATUS',
                   'topic': 'topic', 'relation': 'relation', 'note': 'note', 'observations': {}},
    'issue_list': {'caller': _CALLER},
    'issue_close': {'caller': _CALLER, 'id': 'ISSUE_ID', 'disposition': 'handled', 'reason': 'Why',
                    'expected_revision': 'REVISION_FROM_ISSUE_LIST'},
}
_WRITE_KEY = ('idempotency_key',)
OPTIONAL = {
    'context': ('query', 'limit', 'max_bytes', 'task_mode', 'mode_restriction', 'previous_revision', 'current_status'),
    'search': ('query', 'limit', 'collection', 'include_inactive', 'include_shared', 'domain', 'task_mode', 'mode_restriction',
               'statuses', 'scopes', 'cursor'),
    'read': ('collection', 'include_inactive', 'include_shared', 'audit', 'max_bytes', 'cursor'),
    'capture': ('review', 'details', 'collection', 'live_correction', 'source_review', *_WRITE_KEY),
    'approve': ('collection', *_WRITE_KEY),
    'supersede': ('collection', *_WRITE_KEY),
    'withdraw': ('collection', *_WRITE_KEY),
    'annotate': ('details', 'retired', 'expected_revision', 'collection', *_WRITE_KEY),
    'source_list': ('grant_id', 'relative_dir', 'cursor', 'limit'),
    'source_read': ('cursor', 'max_bytes', 'max_events'),
    'dream_start': ('review_objective', 'target_project', 'sources', 'reconsider'),
    'dream_status': ('max_bytes',),
    'dream_materials': ('source_id', 'event_key', 'cursor', 'max_bytes'),
    'dream_draft': ('reconsider_reason',),
    'dream_publish': (),
    'dream_close': ('abandon_reason', 'objective_outcome', 'accept_gaps'),
    'dream_takeover': (),
    'overview': ('target_project', 'max_bytes', 'historical', 'compact', 'unit_index', 'cursor'),
    'issue_open': ('semantic_reviewed',),
    'issue_list': ('query', 'include_resolved', 'limit', 'cursor'),
    'issue_close': _WRITE_KEY,
}
# Every example key is required except the ones shown only for illustration.
REQUIRED = {tool: tuple(k for k in EXAMPLES[tool] if k not in OPTIONAL[tool])
            for tool in PUBLIC}


def failure(code, message, tool=None, **extra):
    """Raise a MemoryError carrying the public diagnostic; shape errors include an example."""
    exc = MemoryError(code, message)
    exc.diagnostic = {'code': code, 'message': message, **extra,
                      **({'example': EXAMPLES[tool]} if tool in EXAMPLES else {})}
    raise exc


def retired_message(name):
    return f'`{name}` was retired; use `{RETIRED[name]}`'


def check_arguments(tool, arguments):
    """Reject wrong field names and missing required fields with a minimal correct example."""
    if tool in RETIRED:
        failure('unknown_tool', retired_message(tool) + '. Reconnect clients to load the v0.3 names.', RETIRED[tool])
    if tool not in PUBLIC:
        failure('unknown_tool', f'`{tool}` is not a shared-memory operation')
    if not isinstance(arguments, dict):
        failure('invalid_arguments', 'Arguments must be one JSON object', tool)
    allowed = set(REQUIRED[tool]) | set(OPTIONAL[tool])
    unknown = sorted(set(arguments) - allowed)
    if unknown:
        hints = '; '.join(f'`{name}` is now `{LEGACY_ARGS[name]}`' for name in unknown if name in LEGACY_ARGS)
        failure('invalid_arguments', f'Unknown argument(s) {unknown} for `{tool}`' + (f' ({hints})' if hints else ''),
                tool, fields=unknown)
    missing = [name for name in REQUIRED[tool] if arguments.get(name) is None]
    if missing:
        failure('invalid_arguments', f'Missing required argument(s) {missing} for `{tool}`', tool, fields=missing)
    caller = arguments['caller']
    if not isinstance(caller, dict) or not {'cwd', 'harness', 'session_id', 'actor'} <= caller.keys() or not caller.keys() <= CALLER_FIELDS:
        failure('invalid_arguments', 'caller requires cwd, harness, session_id and actor; it allows only '
                + ', '.join(sorted(CALLER_FIELDS)), tool, fields=['caller'])
    for name in ('role', 'model', 'parent_session_id'):
        if name in caller and (not isinstance(caller[name], str) or not caller[name].strip() or len(caller[name]) > 256):
            failure('invalid_arguments', f'caller.{name} must be a short nonempty string', tool, fields=['caller.' + name])
    if 'role' in caller and caller['role'] not in {'lead', 'worker'}:
        failure('invalid_arguments', 'caller.role must be lead or worker', tool, fields=['caller.role'])


# One opaque continuation/revision token: base64url JSON {kind, revision, position} plus a checksum.
def _check(kind, revision, position):
    return _digest([kind, revision, position])[:16]


def encode_cursor(kind, revision, position):
    body = {'kind': kind, 'revision': revision, 'position': position, 'check': _check(kind, revision, position)}
    return base64.urlsafe_b64encode(_json(body).encode('utf-8')).decode('ascii').rstrip('=')


def decode_cursor(token, kind, revision=None):
    """Return the position; reject malformed, tampered, foreign-kind or stale tokens."""
    try:
        if not isinstance(token, str) or not 0 < len(token) <= 4096:
            raise ValueError('cursor must be a bounded string')
        body = _decode(base64.urlsafe_b64decode(token + '=' * (-len(token) % 4)).decode('utf-8'))
        if not isinstance(body, dict) or set(body) != {'kind', 'revision', 'position', 'check'}:
            raise ValueError('cursor fields')
        if body['check'] != _check(body['kind'], body['revision'], body['position']):
            raise ValueError('cursor checksum')
    except (ValueError, TypeError, UnicodeDecodeError, binascii.Error, MemoryError):
        failure('invalid_cursor', 'Cursor is malformed or was modified; pass the exact next_cursor or restart without cursor')
    if body['kind'] != kind:
        failure('invalid_cursor', f'Cursor belongs to `{body["kind"]}`, not `{kind}`; restart without cursor')
    if revision is not None and body['revision'] != revision:
        failure('stale_cursor', 'The listed material changed since this cursor was issued; restart without cursor')
    return body['revision'], body['position']


def derive_key(caller, payload):
    """D3: sha256(session_id || canonical JSON payload); identical retries replay."""
    return hashlib.sha256((caller['session_id'] + _json(payload)).encode('utf-8')).hexdigest()


def size(value):
    return len(json.dumps(value, ensure_ascii=False, allow_nan=False).encode('utf-8'))


def envelope(result, body_key, body, *, revision, next_cursor=None, omitted=None, truncated=None,
             notices=(), limit_bytes=None, drop=(), next_step=False, **extra):
    """The uniform success envelope; tool-specific fields follow the standard ones."""
    result = dict(result or {})
    outcome = result.pop('status', 'ok')
    standard = {'status', 'scope', 'revision', 'item', 'items', 'next_cursor', 'omitted', 'truncated', 'notices',
                'budget', 'next', 'notice'}
    notices = list(notices) + ([result['notice']] if isinstance(result.get('notice'), str) else [])
    omitted = {k: v for k, v in (omitted or {}).items() if v}
    out = {'status': 'ok', 'scope': result.get('scope'), 'revision': revision, body_key: body,
           'next_cursor': next_cursor, 'omitted': omitted,
           'truncated': bool(next_cursor or omitted) if truncated is None else bool(truncated), 'notices': notices}
    if outcome not in ('ok', None):
        out['outcome'] = outcome
    if next_step is not False:
        out['next'] = next_step
    out.update({k: v for k, v in result.items() if k not in standard and k not in drop})
    out.update(extra)
    out['budget'] = {'limit_bytes': limit_bytes, 'used_bytes': 0}
    return _measure(out)


def _measure(out):
    for _ in range(3):
        out['budget']['used_bytes'] = size(out)
    return out


def _with_scope(store, context, out):
    """Manual results without their own scope report the caller's resolved scope."""
    if out.get('scope') is None:
        out['scope'] = store.resolve(context)
        _measure(out)
    return out


def _core_caller(caller):
    return {k: caller[k] for k in CORE_CALLER_FIELDS if k in caller}


def _write_key(tool, args, caller):
    """Pop the caller key or derive it from the canonical payload (collection defaults to project)."""
    key = args.pop('idempotency_key', None)
    if key is None:
        payload = {'collection': 'project', **{k: v for k, v in args.items() if v is not None}}
        key = 'derived:' + derive_key(caller, {'tool': tool, **payload})
    return key


def _page_cursor(kind, page):
    return encode_cursor(kind, page['revision'], {'id': page['id'], 'offset': page['offset']}) if page else None


def _page_from(kind, cursor):
    revision, position = decode_cursor(cursor, kind)
    if not isinstance(position, dict) or set(position) != {'id', 'offset'}:
        failure('invalid_cursor', 'Cursor does not identify a detail page; restart without cursor')
    return {'id': position['id'], 'revision': revision, 'offset': position['offset']}


def _paged_detail(kind, result):
    """Replace internal detail_page/next_page dicts with opaque cursors."""
    items = [{**{k: v for k, v in item.items() if k != 'detail_page'},
              **({'cursor': _page_cursor(kind, item['detail_page'])} if isinstance(item.get('detail_page'), dict) else {})}
             for item in result.get('items', [])]
    page = result.get('detail_page')
    if isinstance(page, dict):
        page = {k: v for k, v in page.items() if k not in {'id', 'revision', 'offset', 'end_offset'}} | {'id': page['id']}
    next_cursor = _page_cursor(kind, result.get('next_page'))
    return items, page, next_cursor


def call(store, tool, arguments):
    check_arguments(tool, arguments)
    args = {k: v for k, v in arguments.items() if v is not None}
    caller = args.pop('caller')
    context = _core_caller(caller)
    if tool in ORDINARY:
        return _ordinary(store, tool, args, caller, dict(caller))
    return _manual(store, tool, args, caller, context)


def _ordinary(store, tool, args, caller, context):
    from .recall import public_projection
    collection = args.pop('collection', 'project')
    if tool == 'context':
        if collection != 'project':
            _fail('invalid_collection', 'Common context is not a historical collection read')
        # The startup packet keeps its own budgeted shape (packet_version 1) for hooks and Pi.
        return public_projection('context', store.context(context, **args))
    selected = store.for_collection(collection)
    if tool == 'search':
        return _search(store, selected, collection, args, caller, context)
    if tool == 'read':
        return _read(selected, args, context)
    key = _write_key(tool, {**args, 'collection': collection}, caller)
    args.pop('idempotency_key', None)
    try:
        if tool == 'capture':
            result = selected.capture(context, idempotency_key=key, **args)
        elif tool == 'approve':
            result = selected.promote(context, idempotency_key=key, **args)
        elif tool == 'supersede':
            result = selected.supersede(context, idempotency_key=key, **args)
        elif tool == 'withdraw':
            result = selected.delete(context, idempotency_key=key, **args)
        else:  # a record's revision is its curation revision; content of an ID never changes
            result = selected.curate(context, idempotency_key=key, **args)
    except TypeError:
        failure('invalid_arguments', 'Arguments do not match the public operation contract', tool)
    except MemoryError as exc:
        if exc.code in {'stale_record', 'stale_curation'} and tool == 'annotate':
            current = _record_revision(selected, context, args['id'])
            failure(exc.code, str(exc) + '; read the record again', tool, current_revision=current)
        raise
    result = public_projection(tool, result)
    record = result.get('record')
    item = record if isinstance(record, dict) else {k: v for k, v in result.items() if k not in {'status', 'replayed', 'notices'}}
    revision = item.get('curation_revision') or _digest(item)
    return _with_scope(store, context, envelope(result, 'item', item, revision=revision, drop=('record', 'curation_revision'),
                                                notices=result.get('notices', ()),
                                                idempotency_key=key, replayed=bool(result.get('replayed'))))


def _record_revision(selected, context, id):
    try:
        items = selected.read(context, [id], True)['items']
        return items[0].get('curation_revision') if items else None
    except MemoryError:
        return None


def _search(store, selected, collection, args, caller, context):
    cursor = args.pop('cursor', None)
    statuses, scopes = args.pop('statuses', None), args.pop('scopes', None)
    if statuses is not None or scopes is not None:
        # Status audit is ordinary search over every visible canonical state; no Dreaming profile is needed.
        if collection == 'history':
            _fail('invalid_collection', 'Status search covers the project and collaboration collections')
        extra = sorted({'domain', 'task_mode', 'mode_restriction'} & args.keys())
        if extra:
            failure('invalid_arguments', f'Status search does not take {extra}', 'search', fields=extra)
        args.update({k: v for k, v in (('statuses', statuses), ('scopes', scopes)) if v is not None})
    offset, expected = 0, None
    if cursor is not None:
        expected, position = decode_cursor(cursor, 'search')
        if not isinstance(position, dict) or set(position) != {'offset'} or type(position['offset']) is not int:
            failure('invalid_cursor', 'Cursor does not continue a search; restart without cursor')
        offset = position['offset']
    query = args.pop('query', '')
    try:
        result = selected.search(context, query, offset=offset, expected_revision=expected, **args)
    except MemoryError as exc:
        if exc.code == 'stale_search':
            failure('stale_cursor', 'The corpus or query changed since this cursor was issued; restart without cursor', 'search')
        raise
    except TypeError:
        failure('invalid_arguments', 'Arguments do not match the public operation contract', 'search')
    revision = result.get('corpus_revision')
    end = result.get('next_offset')
    omitted = {'matches': max(0, result.get('omitted', 0)) if isinstance(result.get('omitted'), int) else 0,
               'filtered_inactive': result.get('filtered_inactive', 0), 'routes': result.get('routes_omitted', 0),
               'bodies': result.get('body_omitted_count', 0)}
    return envelope(result, 'items', result['items'], revision=revision,
                    next_cursor=encode_cursor('search', revision, {'offset': end}) if end is not None else None,
                    omitted=omitted, truncated=result.get('truncated'),
                    limit_bytes=result.get('response_budget_bytes'),
                    drop=('corpus_revision', 'offset', 'next_offset', 'filtered_inactive', 'routes_omitted',
                          'body_omitted_count', 'response_budget_bytes'))


def _fit(build, max_bytes, floor=512):
    """Fit internally with growing headroom for opaque cursors and envelope fields."""
    out = None
    for reserve in (192, 320, 512, 768, 1024):
        if max_bytes - reserve < floor:
            break
        out = build(max_bytes - reserve)
        if out['budget']['used_bytes'] <= max_bytes:
            return out
    return out or build(floor)


def _read(selected, args, context):
    from .projection import bounded_read
    from .recall import public_projection
    audit = args.pop('audit', False)
    if type(audit) is not bool:
        _fail('invalid_input', 'audit must be boolean')
    max_bytes = args.pop('max_bytes', 12000)
    if type(max_bytes) is not int or not 1024 <= max_bytes <= 12000:
        failure('response_budget', 'read max_bytes must be between 1024 and 12000', 'read')
    cursor = args.pop('cursor', None)
    page = _page_from('read', cursor) if cursor is not None else None
    ids = args.pop('ids')
    raw = selected.read(context, ids, **args)
    revisions = {r['id']: r.get('curation_revision') for r in raw.get('items', [])}
    result = public_projection('read', raw, audit)
    result = {**result, 'items': [{**r, 'revision': revisions.get(r['id'])} for r in result['items']]}

    def build(internal):
        try:
            bounded = bounded_read(result, max_bytes=internal, page=page)
        except MemoryError as exc:
            if exc.code == 'stale_read':
                failure('stale_cursor', 'The record changed since this cursor was issued; restart without cursor', 'read')
            raise
        items, detail, next_cursor = _paged_detail('read', bounded)
        extra = {'detail_page': detail} if detail else {}
        return envelope(bounded, 'items', items, revision=_digest(items if not detail else detail),
                        next_cursor=next_cursor, omitted={'ids': len(bounded.get('omitted_ids', []) or []),
                                                          'missing_ids': len(bounded.get('missing_ids', []) or []),
                                                          'filtered_inactive': bounded.get('filtered_inactive', 0)},
                        limit_bytes=max_bytes, drop=('detail_page', 'next_page', 'filtered_inactive'), **extra)
    return _fit(build, max_bytes)


# --- Manual consolidation ---------------------------------------------------

def _run_revision(engine, run_id):
    state = engine.inspect(run_id)
    return encode_cursor('run', run_id, {'generation': state['generation'], 'draft': state.get('current_draft')}), state


def _resolve_run(tool, run_id, token):
    """One caller-visible fence: the run revision resolves to generation and frozen draft."""
    if not isinstance(token, str) or not token:
        failure('invalid_arguments', 'expected_revision must be the revision returned by dream_status or dream_draft', tool)
    _, position = decode_cursor(token, 'run', run_id)
    if not isinstance(position, dict) or set(position) != {'generation', 'draft'}:
        failure('invalid_cursor', 'expected_revision does not identify a run revision', tool)
    return position['generation'], position['draft']


def _next(tool, caller, **args):
    return {'tool': tool, 'args': {'caller': caller, **args}}


def _step(engine, caller, run_id, state, revision):
    """Server-computed continuation from the engine's model-free hint; following it is optional."""
    if state.get('phase') == 'closed':
        return None
    if state.get('current_draft') and state.get('phase') == 'draft-ready':
        return _next('dream_publish', caller, run_id=run_id, expected_revision=revision)
    hint = engine.next_hint(run_id)
    if hint['listing_first']:
        return _next('dream_materials', caller, run_id=run_id)
    if hint['suggested_event_key']:
        return _next('dream_materials', caller, run_id=run_id, event_key=hint['suggested_event_key'],
                     **({'source_id': hint['suggested_source_id']} if hint['suggested_source_id'] else {}))
    if hint['markable']:
        # The statuses are a template: `fill` asks the executor to record its own review decision.
        return {**_next('dream_draft', caller, run_id=run_id, expected_revision=revision,
                        operations=[{'type': 'coverage', 'statuses': {key: 'no-signal' for key in hint['markable']}}]),
                'fill': ['operations']}
    step = _next('dream_close', caller, run_id=run_id, expected_revision=revision)
    if hint['gaps']:
        step['optional'] = {'accept_gaps': [{**gap, 'note': 'WHY_THIS_PERMANENT_GAP_IS_ACCEPTABLE'} for gap in hint['gaps']]}
    return step


def _manual(store, tool, args, caller, context):
    if tool == 'overview':
        return _with_scope(store, context, _overview(store, args, context, caller))
    if tool in {'issue_list', 'issue_close'}:
        return _with_scope(store, context, _issues(store, tool, args, caller, context))
    from .configuration import configured_engine
    engine = configured_engine(store, context)
    run_id = args.get('run_id')
    try:
        return _with_scope(store, context, _dream(engine, tool, args, caller))
    except TypeError:
        failure('invalid_arguments', 'Arguments do not match the manual operation contract', tool)
    except MemoryError as exc:
        if exc.code in {'stale_attempt', 'stale_draft'} and run_id:
            try:
                current, _ = _run_revision(engine, run_id)
            except MemoryError:
                current = None
            failure(exc.code, str(exc), tool, current_revision=current)
        raise


def _dream(engine, tool, args, caller):
    if tool == 'source_list':
        return _source_list(engine, args, caller)
    if tool == 'source_read':
        cursor = args.pop('cursor', None)
        internal = None
        if cursor is not None:
            _, position = decode_cursor(cursor, 'source_read')
            if not isinstance(position, dict) or position.get('selection') != args['selection']:
                failure('invalid_cursor', 'Cursor belongs to another selection; restart without cursor', tool)
            internal = position['cursor']
        result = engine.source_read(args.pop('selection'), cursor=internal, **args)
        token = encode_cursor('source_read', _digest(result.get('selection')),
                              {'selection': result.get('selection'), 'cursor': result['next_cursor']}) \
            if result.get('next_cursor') else None
        return envelope(result, 'item', {k: v for k, v in result.items() if k != 'next_cursor'},
                        revision=_digest(result.get('selection')), next_cursor=token, limit_bytes=args.get('max_bytes', 262144),
                        drop=tuple(k for k in result if k != 'scope'),
                        next_step=_next('source_read', caller, selection=result.get('selection'), cursor=token) if token else None)
    if tool == 'dream_start':
        if args.get('review_objective') is None:
            args.pop('review_objective', None)
            args['default_objective'] = True  # Memory triage inventory; reads no native history.
        result = engine.start(**args)
        run_id = result.get('run_id')
        if not run_id:
            return envelope(result, 'item', result, revision=_digest(result), drop=tuple(result), next_step=None)
        revision, state = _run_revision(engine, run_id)
        step = (_next('dream_status', caller, run_id=run_id) if result.get('status') == 'resume-required'
                else _step(engine, caller, run_id, state, revision))
        return envelope(result, 'item', {k: v for k, v in result.items() if k not in {'status', 'generation'}},
                        revision=revision, drop=tuple(result), next_step=step)
    run_id = args.pop('run_id')
    if tool == 'dream_status':
        max_bytes = args.pop('max_bytes', 12000)
        revision, state = _run_revision(engine, run_id)
        item = {k: v for k, v in state.items() if k != 'generation'}
        notices = []
        try:
            item['changes'] = engine.changes(run_id, max_bytes=max_bytes)
        except MemoryError as exc:
            item['changes'] = None
            notices.append(f'changes unavailable: {exc.code}')
        return envelope({}, 'item', item, revision=revision, notices=notices, limit_bytes=max_bytes,
                        next_step=_step(engine, caller, run_id, state, revision))
    if tool == 'dream_materials':
        return _materials(engine, run_id, args, caller)
    if tool == 'dream_takeover':
        generation, _ = _resolve_run(tool, run_id, args.pop('expected_revision'))
        result = engine.takeover(run_id, generation)
        revision, state = _run_revision(engine, run_id)
        return envelope(result, 'item', {'run_id': run_id, 'phase': state['phase']}, revision=revision,
                        drop=tuple(result), next_step=_next('dream_status', caller, run_id=run_id))
    generation, draft = _resolve_run(tool, run_id, args.pop('expected_revision'))
    if tool == 'dream_draft':
        operations = args.pop('operations')
        if not isinstance(operations, list):
            failure('invalid_arguments', 'operations must be a list', tool, fields=['operations'])
        coverage, rest = {}, []
        for op in operations:
            if isinstance(op, dict) and op.get('type') == 'coverage':
                if set(op) != {'type', 'statuses'} or not isinstance(op['statuses'], dict):
                    failure('invalid_arguments', 'A coverage operation is {"type":"coverage","statuses":{event_key: status}}', tool)
                coverage.update(op['statuses'])
            else:
                rest.append(op)
        if not coverage and not rest:
            failure('invalid_arguments', 'dream_draft needs at least one operation', tool, fields=['operations'])
        # Coverage marks are verified against served material and applied atomically at dream_publish.
        frozen = engine.freeze(run_id, generation, rest, coverage=coverage or None, **args)
        item = {'draft': engine.candidate_diff(run_id, frozen['draft_revision'])}
        item['draft']['operations_summary'] = frozen['operations']
        if coverage:
            item['coverage'] = frozen['coverage']
        revision, state = _run_revision(engine, run_id)
        return envelope({}, 'item', item, revision=revision, next_step=_step(engine, caller, run_id, state, revision))
    if tool == 'dream_publish':
        if not draft:
            failure('no_draft', 'This run revision has no frozen draft; call dream_draft first', tool)
        result = engine.publish(run_id, generation, draft)
        revision, state = _run_revision(engine, run_id)
        return envelope(result, 'item', {k: v for k, v in result.items() if k != 'status'}, revision=revision,
                        drop=tuple(result), next_step=_step(engine, caller, run_id, state, revision))
    if tool == 'dream_close':
        result = engine.close(run_id, generation, **args)
        revision, _ = _run_revision(engine, run_id)
        return envelope(result, 'item', {k: v for k, v in result.items() if k != 'status'}, revision=revision,
                        drop=tuple(result), next_step=None)
    if tool == 'issue_open':
        result = engine.suggest_issue(run_id, generation, **args)
        revision, state = _run_revision(engine, run_id)
        return envelope(result, 'item', {k: v for k, v in result.items() if k != 'status'}, revision=revision,
                        drop=tuple(result), next_step=_step(engine, caller, run_id, state, revision))
    failure('unknown_tool', f'`{tool}` is not a shared-memory operation')


def _source_list(engine, args, caller):
    grant_id = args.pop('grant_id', None)
    cursor = args.pop('cursor', None)
    binding = {'grant_id': grant_id, 'relative_dir': args.get('relative_dir', '')}
    internal = None
    if cursor is not None:
        _, position = decode_cursor(cursor, 'source_list')
        if not isinstance(position, dict) or position.get('binding') != binding:
            failure('invalid_cursor', 'Cursor belongs to another listing; restart without cursor', 'source_list')
        internal = position['cursor']
    if grant_id is None:
        if args.get('relative_dir'):
            failure('invalid_arguments', 'relative_dir needs grant_id', 'source_list', fields=['relative_dir'])
        result = engine.catalog(cursor=internal, limit=args.get('limit', 50))
        items = result.get('source_grants', [])
        revision = result.get('revision')
        drop = ('source_grants', 'next_cursor', 'revision')
    else:
        result = engine.source_list(grant_id, cursor=internal, **args)
        items = result.get('items', [])
        revision = _digest([binding, items])
        drop = ('items', 'next_cursor')
    token = encode_cursor('source_list', revision, {'binding': binding, 'cursor': result['next_cursor']}) \
        if result.get('next_cursor') else None
    return envelope(result, 'items', items, revision=revision, next_cursor=token, drop=drop,
                    next_step=_next('source_list', caller, **{k: v for k, v in binding.items() if v}, cursor=token) if token else None)


def _materials(engine, run_id, args, caller):
    """Always paged: a summary page without event_key, bounded text pages with it."""
    cursor = args.pop('cursor', None)
    max_bytes = args.pop('max_bytes', None)
    event_key, source_id = args.pop('event_key', None), args.pop('source_id', None)
    limit = 16384 if max_bytes is None else max_bytes
    if type(limit) is not int or not 2048 <= limit <= 262144:
        failure('response_budget', 'dream_materials max_bytes must be between 2048 and 262144', 'dream_materials')
    # `next` repeats the caller and the opaque tokens; reserve them so one response honours max_bytes.
    reserve = 1536 + 2 * size(caller)
    internal = None
    if cursor is not None:
        _, position = decode_cursor(cursor, 'dream_materials')
        if (not isinstance(position, dict) or position.get('event_key') != event_key
                or position.get('source_id') != source_id):
            failure('invalid_cursor', 'Cursor belongs to another listing or event; restart without cursor', 'dream_materials')
        internal = position['cursor']
    if event_key is None:
        result = engine.material_summary(run_id, source_id, cursor=internal, max_bytes=max(1024, limit - reserve))
        page_cursor = result.pop('next_cursor')
    else:
        result = engine.materials(run_id, source_id, event_key=event_key, cursor=internal,
                                  max_chars=max(1, min(16000, (limit - reserve) // 4)))
        page = result.get('page') or {}
        page_cursor = page.get('next_cursor')
        if page:
            result['page'] = {k: v for k, v in page.items() if k != 'next_cursor'}
    token = encode_cursor('dream_materials', run_id, {'source_id': source_id, 'event_key': event_key,
                                                      'cursor': page_cursor}) if page_cursor else None
    revision, state = _run_revision(engine, run_id)
    selection = {k: v for k, v in {'source_id': source_id, 'event_key': event_key, 'max_bytes': max_bytes}.items() if v is not None}
    step = (_next('dream_materials', caller, run_id=run_id, **selection, cursor=token) if token
            else _step(engine, caller, run_id, state, revision))
    return envelope(result, 'item', {k: v for k, v in result.items() if k != 'scope'}, revision=revision,
                    next_cursor=token, limit_bytes=limit, drop=tuple(result), next_step=step)


def _overview(store, args, context, caller):
    from .configuration import ViewReader
    cursor = args.pop('cursor', None)
    max_bytes = args.pop('max_bytes', 8000)
    page = _page_from('overview', cursor) if cursor is not None else None
    if type(max_bytes) is not int or not 1024 <= max_bytes <= 100000:
        failure('response_budget', 'overview max_bytes must be between 1024 and 100000', 'overview')

    def build(internal):
        # max_chars stays internal: the character cap follows the byte budget.
        result = ViewReader(store, context).overview(max_bytes=internal, max_chars=internal, page=page, **args)
        items, detail, next_cursor = _paged_detail('overview', result)
        extra = {'detail_page': detail} if detail else {}
        return envelope(result, 'items', items, revision=result.get('revision') or _digest(items if not detail else detail),
                        next_cursor=next_cursor, limit_bytes=max_bytes, drop=('detail_page', 'next_page', 'revision'),
                        next_step=None, **extra)
    return _fit(build, max_bytes)


def _issues(store, tool, args, caller, context):
    from .issues import search, resolve
    if tool == 'issue_list':
        cursor = args.pop('cursor', None)
        if cursor is not None:
            decode_cursor(cursor, 'issue_list')
        result = search(store, context, **args)
        # shortcut: issue inventories fit one bounded page today, so next_cursor is always null; page when they do not.
        return envelope(result, 'items', result['items'], revision=_digest(result['items']),
                        omitted={'issues': result.get('omitted', 0)}, drop=('items', 'omitted'), next_step=None)
    key = _write_key(tool, args, caller)
    result = resolve(store, context, idempotency_key=key, **args)
    return envelope(result, 'item', {k: v for k, v in result.items() if k not in {'status', 'replayed', 'revision'}},
                    revision=result.get('revision') or args['expected_revision'], drop=tuple(result), next_step=None,
                    idempotency_key=key, replayed=bool(result.get('replayed')))
