"""One public operation dispatch for MCP and CLI, using real per-call identity."""
from __future__ import annotations

from .core import MemoryError, _fail

ORDINARY = ('context', 'search', 'read', 'create', 'approve', 'update', 'delete', 'capture', 'curate')
MANUAL = ('dream_catalog', 'memory_audit', 'source_list', 'source_read', 'run_start', 'run_observe',
          'run_takeover', 'run_materials', 'run_changes', 'draft_submit', 'draft_read', 'draft_publish',
          'coverage_mark', 'run_close', 'overview_read', 'issue_suggest', 'issue_search', 'issue_resolve')
PUBLIC = (*ORDINARY, *MANUAL)


def call(store, tool, arguments):
    if tool not in PUBLIC or not isinstance(arguments, dict):
        _fail('invalid_input', 'Expected a maintained public operation and JSON object arguments')
    args = dict(arguments)
    from .recall import public_projection
    if tool in ORDINARY:
        collection = args.pop('collection', 'project')
        if tool == 'context' and collection != 'project':
            _fail('invalid_collection', 'Common context is not a historical collection read')
        selected = store.for_collection(collection)
        audit = args.pop('audit', False) if tool == 'read' else False
        if type(audit) is not bool:
            _fail('invalid_input', 'audit must be boolean')
        max_bytes = args.pop('max_bytes', 12000) if tool == 'read' else None
        page = args.pop('page', None) if tool == 'read' else None
        method = {'create': 'propose', 'approve': 'promote', 'update': 'supersede'}.get(tool, tool)
        try:
            result = public_projection(tool, getattr(selected, method)(**args), audit)
        except TypeError as exc:
            raise MemoryError('invalid_input', 'Arguments do not match the public operation contract') from exc
        if tool == 'read':
            from .projection import bounded_read
            return bounded_read(result, max_bytes=max_bytes, page=page)
        return result
    context = args.pop('context', None)
    if not isinstance(context, dict):
        _fail('invalid_input', 'Every manual operation requires the actual current caller context')
    if tool == 'overview_read':
        from .configuration import ViewReader
        method = ViewReader(store, context).overview
    elif tool in {'issue_search', 'issue_resolve'}:
        from .issues import search, resolve
        method = lambda **kw: (search if tool == 'issue_search' else resolve)(store, context, **kw)
    else:
        from .configuration import configured_engine
        engine = configured_engine(store, context)
        methods = {'dream_catalog': 'catalog', 'memory_audit': 'audit', 'source_list': 'source_list',
                   'source_read': 'source_read', 'run_start': 'start', 'run_observe': 'inspect',
                   'run_takeover': 'takeover', 'run_materials': 'materials', 'run_changes': 'changes',
                   'draft_submit': 'freeze', 'draft_read': 'candidate_diff', 'draft_publish': 'publish',
                   'coverage_mark': 'mark_processed', 'run_close': 'close', 'issue_suggest': 'suggest_issue'}
        method = getattr(engine, methods[tool])
        if tool == 'run_start' and args.get('review_objective') is None:
            _fail('invalid_objective', 'A new manual review needs its bounded review_objective')
        if tool == 'run_takeover' and 'generation' in args:
            args['expected_generation'] = args.pop('generation')
    try:
        return method(**args)
    except TypeError as exc:
        raise MemoryError('invalid_input', 'Arguments do not match the manual operation contract') from exc
