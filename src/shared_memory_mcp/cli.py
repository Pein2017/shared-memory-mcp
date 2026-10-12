"""Operator and recall CLI; diagnostics are JSON and stderr, never MCP stdout."""
from __future__ import annotations
import argparse
import json
import os
import sys
from .core import MemoryStore, MemoryError, _decode


def default_root(root=None):
    value = root or os.environ.get('SHARED_MEMORY_ROOT')
    if not value:
        raise MemoryError('uninitialized','Provide --root or SHARED_MEMORY_ROOT')
    return value


def _add_context(parser):
    parser.add_argument('--cwd',required=True)
    parser.add_argument('--harness',required=True,choices=['claude','codex','pi','webcodex'])
    parser.add_argument('--session-id',required=True)
    parser.add_argument('--actor',required=True)
    parser.add_argument('--task-id')
    parser.add_argument('--project-id')


def call_operation(store, tool, arguments):
    """The exact same public dispatcher is used by the single MCP entrypoint."""
    from .operations import call
    return call(store, tool, arguments)


def main(argv=None):
    parser = argparse.ArgumentParser(prog='shared-memory')
    parser.add_argument('--root')
    commands = parser.add_subparsers(dest='command',required=True)
    from .dream_cli import add_parser as add_dream_parser
    add_dream_parser(commands)
    commands.add_parser('init')
    registration = commands.add_parser('register')
    registration.add_argument('--project-id',required=True)
    registration.add_argument('--project-root',action='append',required=True)
    project = commands.add_parser('project', help='Read-only cwd/Git project discovery and existing registration hints')
    project.add_argument('--cwd', required=True)
    project.add_argument('--project-id')
    doctor = commands.add_parser('doctor')
    doctor.add_argument('--prune', action='store_true', help='List removable derived state (dry run unless --apply)')
    doctor.add_argument('--apply', action='store_true', help='With --prune, remove exactly the listed paths')
    doctor.add_argument('--sources', action='store_true', help='List records whose file:// sources are missing')
    recall = commands.add_parser('context')
    _add_context(recall)
    recall.add_argument('--query',default='')
    recall.add_argument('--limit',type=int,default=8)
    recall.add_argument('--max-chars',type=int,default=6000)
    recall.add_argument('--max-bytes',type=int,default=8000)
    recall.add_argument('--task-mode', choices=['research', 'general'])
    recall.add_argument('--previous-revision')
    recall.add_argument('--current-status', action='store_true')
    hook = commands.add_parser('hook')
    hook.add_argument('--harness',required=True,choices=['claude','codex'])
    extract = commands.add_parser('extract', help='Leased cheap-model extraction of idle sessions into candidates')
    extract.add_argument('--max', type=int, help='Sessions to claim (default: max_sessions_per_startup)')
    extract.add_argument('--transcript', help='Extract this transcript under a configured history root')
    extract.add_argument('--force', action='store_true', help='Re-extract even if unchanged since the last extraction')
    extract.add_argument('--status', action='store_true', help='List per-transcript extraction state and journal')
    extract.add_argument('--startup', action='store_true', help=argparse.SUPPRESS)
    extract.add_argument('--spawn', action='store_true', help='Start a detached startup extraction when enabled')
    call = commands.add_parser('call')
    from .operations import PUBLIC
    call.add_argument('--tool', required=True, choices=PUBLIC)
    server = commands.add_parser('serve')
    args = parser.parse_args(argv)
    try:
        store = MemoryStore(default_root(args.root))
        if args.command == 'init':
            result = store.init()
        elif args.command == 'register':
            result = store.register(args.project_id,args.project_root)
        elif args.command == 'project':
            result = store.project(args.cwd, args.project_id)
        elif args.command == 'doctor':
            if args.apply and not args.prune:
                raise MemoryError('invalid_input', '--apply requires --prune')
            result = store.doctor()
            from .maintenance import missing_sources, prune
            if args.prune:
                result['prune'] = prune(store, apply=args.apply)
            if args.sources:
                result['sources'] = missing_sources(store)
        elif args.command == 'context':
            context = {key:getattr(args,key) for key in ('cwd','harness','session_id','actor','task_id','project_id') if getattr(args,key) is not None}
            result = store.context(context,args.query,args.limit,args.max_chars, task_mode=args.task_mode,
                                   max_bytes=args.max_bytes, previous_revision=args.previous_revision,
                                    current_status=args.current_status)
        elif args.command == 'call':
            raw = sys.stdin.read(1048577)
            if len(raw) > 1048576:
                raise MemoryError('invalid_input', 'Operation arguments exceed the input bound')
            try:
                arguments = _decode(raw)
            except (ValueError, MemoryError) as exc:
                raise MemoryError('invalid_input', 'Operation arguments must be valid JSON') from exc
            result = call_operation(store, args.tool, arguments)
        elif args.command == 'dream':
            from .dream_cli import handle as handle_dream
            result = handle_dream(store, args)
            if result is None:
                return 0
        elif args.command == 'extract':
            from . import extract as extraction
            if args.status:
                result = extraction.status(store)
            elif args.spawn:
                result = extraction.spawn(store)
            else:
                result = extraction.run(store, limit=args.max, transcript=args.transcript,
                                        force=args.force, startup=args.startup)
        elif args.command == 'hook':
            from .adapters import hook_main
            return hook_main(store,args.harness)
        else:
            from .server import serve
            serve(store)
            return 0
        print(json.dumps(result,ensure_ascii=False))
        if (args.command in ('context','project') or args.command == 'call' and args.tool == 'context') and result.get('status') != 'ok':
            print('shared-memory: '+result['diagnostic']['code'],file=sys.stderr)
            return 2
        if args.command == 'dream' and result.get('status') in {'partial', 'blocked'}:
            return 3
        return 0
    except MemoryError as exc:
        diagnostic = getattr(exc, 'diagnostic', {'code':exc.code,'message':str(exc)})
        if args.command == 'context':
            status = 'unmapped' if exc.code in ('unmapped_scope','uninitialized') else 'ambiguous' if exc.code == 'ambiguous_scope' else 'invalid'
            print(json.dumps({'status':status,'scope':None,'items':[],'text':'','omitted':0,'truncated':False,'diagnostic':diagnostic},ensure_ascii=False))
        elif args.command != 'serve':
            print(json.dumps({'status':'error','diagnostic':diagnostic},ensure_ascii=False))
        print(f'shared-memory: {exc.code}: {exc}',file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
