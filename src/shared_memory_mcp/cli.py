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
    """Fixed public operation bridge for real callers without a native MCP route."""
    operations = {'context': store.context, 'search': store.search, 'read': store.read,
                  'create': store.propose, 'approve': store.promote, 'update': store.supersede,
                  'delete': store.delete, 'capture': store.capture, 'curate': store.curate}
    if tool not in operations or not isinstance(arguments, dict):
        raise MemoryError('invalid_input', 'Expected a public operation and JSON object arguments')
    from .recall import public_projection
    arguments = dict(arguments)
    audit = arguments.pop('audit', False) if tool == 'read' else False
    if not isinstance(audit, bool):
        raise MemoryError('invalid_input', 'audit must be boolean')
    try:
        return public_projection(tool, operations[tool](**arguments), audit)
    except TypeError as exc:
        raise MemoryError('invalid_input', 'Arguments do not match the public operation contract') from exc


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
    commands.add_parser('doctor')
    recall = commands.add_parser('context')
    _add_context(recall)
    recall.add_argument('--query',default='')
    recall.add_argument('--limit',type=int,default=8)
    recall.add_argument('--max-chars',type=int,default=6000)
    recall.add_argument('--dream-profile')
    recall.add_argument('--dream-scenario', default='general')
    hook = commands.add_parser('hook')
    hook.add_argument('--harness',required=True,choices=['claude','codex'])
    hook.add_argument('--dream-profile')
    hook.add_argument('--dream-scenario', default='general')
    call = commands.add_parser('call')
    call.add_argument('--tool', required=True, choices=['context','search','read','create','approve','update','delete','capture','curate'])
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
            result = store.doctor()
        elif args.command == 'context':
            context = {key:getattr(args,key) for key in ('cwd','harness','session_id','actor','task_id','project_id') if getattr(args,key) is not None}
            result = store.context(context,args.query,args.limit,args.max_chars)
            if args.dream_profile:
                from .dream_transport import append_startup_collaboration
                result = append_startup_collaboration(store, context, result, args.dream_profile,
                                                       args.dream_scenario, max_chars=args.max_chars)
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
        elif args.command == 'hook':
            from .adapters import hook_main
            return hook_main(store,args.harness, dream_profile=args.dream_profile, dream_scenario=args.dream_scenario)
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
