"""Read-only project discovery using the existing registry and Git identities."""
from __future__ import annotations

import hashlib
from pathlib import Path
import re
import shlex

from .core import MemoryError, _fail, _git_info, _within

SCOPE_ERRORS = {'unmapped_scope', 'ambiguous_scope', 'scope_hint_mismatch'}
PREFIX = 'Shared-memory onboarding diagnostic:'


def discovery(store, cwd, project_id=None):
    if not isinstance(cwd, str) or not Path(cwd).is_absolute() or '\x00' in cwd:
        _fail('invalid_input', 'Project cwd must be an absolute existing directory')
    path = Path(cwd).resolve()
    if not path.is_dir():
        _fail('unmapped_scope', 'Project cwd must exist')
    registry = store._registry()  # Corruption always fails closed, even on unknown cwd.
    git_root, common = _git_info(path)
    context = {'cwd': str(path), 'harness': 'codex', 'session_id': 'project-discovery', 'actor': 'project-discovery'}
    if project_id is not None:
        context['project_id'] = project_id
    result = {'status': 'ok', 'cwd': str(path), 'git_root': git_root, 'git_common_dir': common,
              'project_id': None, 'suggested_project_id': None, 'registration': None}
    try:
        result['project_id'] = store._resolve_scope(context)['project_id']
        return result
    except MemoryError as exc:
        if exc.code not in SCOPE_ERRORS:
            raise
        result.update(status='unmapped' if exc.code == 'unmapped_scope' else
                      'ambiguous' if exc.code == 'ambiguous_scope' else 'invalid',
                      diagnostic={'code': exc.code, 'message': str(exc)})
        if exc.code != 'unmapped_scope' or project_id is not None or not git_root:
            return result
    # Deliberately registered subdirectories cannot authorize the entire repo.
    restricted = any(_within(Path(root), Path(git_root)) and root != git_root
                     for entry in registry['projects'] for root in entry['roots'])
    if restricted:
        result['diagnostic'] = {'code': 'restricted_scope',
                                'message': 'This Git repository has narrower registered subtrees; no broader registration is suggested.'}
        return result
    # A known common identity must never receive a second suggested project ID.
    if any(common in entry['git_common_dirs'] for entry in registry['projects']):
        return result
    name = re.sub(r'[^a-zA-Z0-9_.-]+', '-', Path(git_root).name).strip('_.-')[:96] or 'project'
    ids = {entry['id'] for entry in registry['projects']}
    if name in ids:
        stem = name
        identity = hashlib.sha256(common.encode()).hexdigest()
        for length in (8, 16, 32, 64):
            name = stem[:63] + '-' + identity[:length]
            if name not in ids:
                break
        else:
            return result
    argv = ['shared-memory', '--root', str(store.root), 'register', '--project-id', name,
            '--project-root', git_root]
    command = shlex.join(argv)
    # Native context has a fixed budget. Keep oversized paths CLI-only.
    if len(command) <= 4096:
        result['suggested_project_id'] = name
        result['registration'] = {'argv': argv, 'command': command}
    return result


def diagnostic_text(project):
    code = project.get('diagnostic', {}).get('code')
    if code == 'restricted_scope':
        return PREFIX + ' cwd is outside the permitted registered subtree. Use a registered subtree; do not broaden the binding.'
    if code == 'scope_hint_mismatch':
        return PREFIX + ' the project_id hint disagrees with actual cwd. Check the caller identity; do not rescope the request.'
    if code == 'ambiguous_scope':
        return PREFIX + ' cwd has ambiguous project bindings. Resolve the registry conflict before recall or registration.'
    registration = project.get('registration')
    if code == 'unmapped_scope' and registration:
        return (PREFIX + ' this independent Git repository is unregistered. For the authorized task repository, '
                'use the existing explicit registration command, then retry recall:\n' + registration['command'])
    return None
