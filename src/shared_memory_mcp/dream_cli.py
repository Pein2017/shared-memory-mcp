"""Trusted-launcher CLI for the separately capability-bound Dreaming endpoint."""
from __future__ import annotations

import sys

from .core import MemoryError, _decode
from .dreaming import Dreaming, add_disposition, configure_policy


def add_parser(commands):
    from .cli import _add_context
    parser = commands.add_parser('dream', help='Operator-bound DreamRun and dedicated advisory MCP tools')
    actions = parser.add_subparsers(dest='dream_action', required=True)
    config = actions.add_parser('configure', help='Read an explicitly authorized bounded policy JSON from stdin')
    config.add_argument('--expected-revision', default='absent')
    actions.add_parser('capabilities')
    for name in ('start', 'inspect', 'materials', 'freeze', 'diff', 'mark', 'takeover', 'publish',
                 'overview', 'close', 'issue', 'disposition', 'serve', 'catalog', 'audit', 'source-list', 'source-read'):
        command = actions.add_parser(name)
        command.add_argument('--profile', required=True)
        _add_context(command)
        if name not in {'start', 'overview', 'disposition', 'serve', 'catalog', 'audit', 'source-list', 'source-read'}:
            command.add_argument('--run-id', required=True)
        if name in {'freeze', 'mark', 'takeover', 'publish', 'close', 'issue'}:
            command.add_argument('--generation', required=True, type=int)
        if name in {'diff', 'publish'}:
            command.add_argument('--revision', required=True)
        if name == 'start':
            command.add_argument('--reconsider')
            command.add_argument('--target-project')
            selectors = command.add_mutually_exclusive_group()
            selectors.add_argument('--sources', help='JSON list of authorized source selections')
            selectors.add_argument('--selectors-stdin', action='store_true', help='Read target_project, sources, reconsider selectors as JSON from stdin')
        if name == 'materials':
            command.add_argument('--source-id', required=True)
        if name == 'freeze':
            command.add_argument('--reconsider-reason')
        if name == 'close':
            command.add_argument('--abandon-reason')
        if name in {'overview', 'audit', 'disposition'}:
            command.add_argument('--target-project')
        if name == 'catalog':
            command.add_argument('--cursor')
            command.add_argument('--limit', type=int, default=50)
        if name == 'audit':
            command.add_argument('--filters-stdin', action='store_true')
        if name == 'source-list':
            command.add_argument('--grant-id', required=True)
            command.add_argument('--relative-dir', default='')
            command.add_argument('--cursor')
            command.add_argument('--limit', type=int, default=50)
        if name == 'source-read':
            command.add_argument('--cursor')
            command.add_argument('--max-bytes', type=int, default=262144)
            command.add_argument('--max-events', type=int, default=128)
        if name == 'overview':
            command.add_argument('--view', required=True, choices=['research', 'collaboration'])
            command.add_argument('--scenario', required=True)
            command.add_argument('--max-chars', type=int)
            command.add_argument('--max-bytes', type=int)
            command.add_argument('--historical')
        if name == 'serve':
            command.add_argument('--run-id')
            command.add_argument('--generation', type=int)
            command.add_argument('--enable-publisher', action='store_true',
                                 help='Trusted launcher opt-in only; not native harness qualification or OS isolation')
    return parser


def _input():
    data = sys.stdin.buffer.read(1048577) if hasattr(sys.stdin, 'buffer') else sys.stdin.read(1048577)
    if len(data) > 1048576:
        raise MemoryError('invalid_input', 'Dream command input exceeds one MiB')
    try:
        return _decode(data)
    except (ValueError, UnicodeDecodeError) as exc:
        raise MemoryError('invalid_input', 'Dream command input must be valid finite JSON') from exc


def handle(store, args):
    action = args.dream_action
    if action == 'configure':
        return configure_policy(store, _input(), expected_revision=args.expected_revision)
    if action == 'capabilities':
        from .dream_transport import capabilities
        return capabilities()
    caller = {key: getattr(args, key) for key in ('cwd', 'harness', 'session_id', 'actor', 'task_id', 'project_id')
              if getattr(args, key, None) is not None}
    # A CLI process is an operator boundary. Model-facing MCP tools cannot pick
    # another profile/caller, enable publication or invoke any operator command.
    engine = Dreaming(store, args.profile, caller,
                      publisher=action == 'publish' or action == 'serve' and args.enable_publisher)
    if action == 'start':
        selectors = _input() if args.selectors_stdin else {}
        if not isinstance(selectors, dict) or set(selectors) - {'target_project', 'sources', 'reconsider'}:
            raise MemoryError('invalid_input', 'Start selectors accept only target_project, sources and reconsider')
        if args.sources is not None:
            try:
                selectors['sources'] = _decode(args.sources)
            except (ValueError, UnicodeDecodeError) as exc:
                raise MemoryError('invalid_input', 'Sources must be finite JSON') from exc
        for key in ('target_project', 'reconsider'):
            value = getattr(args, key)
            if value is not None:
                if key in selectors:
                    raise MemoryError('invalid_input', 'Duplicate start selector')
                selectors[key] = value
        return engine.start(**selectors)
    if action == 'catalog':
        return engine.catalog(cursor=args.cursor, limit=args.limit)
    if action == 'source-list':
        return engine.source_list(args.grant_id, relative_dir=args.relative_dir, cursor=args.cursor, limit=args.limit)
    if action == 'source-read':
        return engine.source_read(_input(), cursor=args.cursor, max_bytes=args.max_bytes, max_events=args.max_events)
    if action == 'audit':
        filters = _input() if args.filters_stdin else {}
        allowed = {'collection', 'ids', 'query', 'statuses', 'scopes', 'cursor', 'limit', 'max_chars'}
        if not isinstance(filters, dict) or set(filters) - allowed:
            raise MemoryError('invalid_input', 'Audit filters cannot change caller or target bindings')
        return engine.audit(target_project=args.target_project, **filters)
    if action == 'inspect':
        return engine.inspect(args.run_id)
    if action == 'materials':
        return engine.materials(args.run_id, args.source_id)
    if action == 'freeze':
        return engine.freeze(args.run_id, args.generation, _input(), reconsider_reason=args.reconsider_reason)
    if action == 'diff':
        return engine.candidate_diff(args.run_id, args.revision)
    if action == 'mark':
        return engine.mark_processed(args.run_id, args.generation, _input())
    if action == 'takeover':
        return engine.takeover(args.run_id, args.generation)
    if action == 'publish':
        return engine.publish(args.run_id, args.generation, args.revision)
    if action == 'overview':
        return engine.overview(args.view, scenario=args.scenario, max_chars=args.max_chars,
                               max_bytes=args.max_bytes, historical=args.historical, target_project=args.target_project)
    if action == 'close':
        return engine.close(args.run_id, args.generation, abandon_reason=args.abandon_reason)
    if action == 'issue':
        return engine.suggest_issue(args.run_id, args.generation, **_input())
    if action == 'disposition':
        _, profile = engine._policy()
        payload = _input()
        if not isinstance(payload, dict) or 'target' in payload or 'context' in payload:
            raise MemoryError('invalid_input', 'Disposition target/caller are bound by the operator profile')
        target = engine._target(profile, args.target_project)
        return add_disposition(store, caller, target=target, **payload)
    if action == 'serve':
        from .dream_transport import make_dream_server
        if (args.run_id is None) != (args.generation is None):
            raise MemoryError('invalid_input', 'Fixed-Run serving requires both run-id and generation')
        make_dream_server(engine, args.run_id, args.generation).run(transport='stdio')
        return None
    raise MemoryError('invalid_input', 'Unknown Dream command')
