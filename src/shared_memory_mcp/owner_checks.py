"""Bounded foreground verification of configured source owners, not memory synthesis.

A caller selects current_status on a specific task. Only operator-configured
grant selectors can be opened; the packet carries original excerpts and exact
source identity, never an assertion that model/scientific truth was verified.
"""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import re

from .core import SAFE_ID, MemoryError, _digest, _fail, _keys
from .dream_sources import SECRET
from .narrative import ROLES

MAX_OWNERS = 16
MAX_SELECTED = 3
MAX_FILE_BYTES = 32768
MAX_EXCERPT_CHARS = 1200
VALID_ROLES = {'index', 'question', 'result'}


def validate_owners(owners, topics):
    if not isinstance(owners, list) or len(owners) > MAX_OWNERS:
        _fail('invalid_routing', 'Owner selectors must be a bounded list')
    identifiers, topic_ids = set(), {topic['id'] for topic in topics}
    for entry in owners:
        if not isinstance(entry, dict):
            _fail('invalid_routing', 'Owner selector must be an object')
        _keys(entry, {'id', 'topic_ids', 'grant_id', 'role'},
              {'id', 'topic_ids', 'grant_id', 'role', 'relative_path', 'priority'}, 'owner selector')
        if (not isinstance(entry['id'], str) or not SAFE_ID.fullmatch(entry['id'])
                or entry['id'] in identifiers or entry['role'] not in VALID_ROLES
                or not isinstance(entry['grant_id'], str) or not SAFE_ID.fullmatch(entry['grant_id'])):
            _fail('invalid_routing', 'Owner selector has invalid identity, grant or role')
        identifiers.add(entry['id'])
        if type(entry.get('priority', 0)) is not int or not 0 <= entry.get('priority', 0) <= 100:
            _fail('invalid_routing', 'Owner priority must be a bounded integer')
        chosen = entry['topic_ids']
        if (not isinstance(chosen, list) or not chosen or len(chosen) > 16
                or any(not isinstance(x, str) or x not in topic_ids for x in chosen)
                or len(set(chosen)) != len(chosen)):
            _fail('invalid_routing', 'Owner selector topic IDs must refer to real routes')
        relative = entry.get('relative_path', '')
        if (not isinstance(relative, str) or len(relative) > 512 or
                relative.startswith('/') or '\\' in relative or
                '..' in Path(relative).parts or '\x00' in relative):
            _fail('unsafe_source', 'Owner relative path may not escape its configured grant')
    return owners


def _task_terms(query):
    from .recall import tokens
    return set(tokens(query)) - {'research', 'status', 'current', 'today', 'now'}


def _excerpt(text, query):
    """Extract literal source lines with bounded context; not a new semantic claim."""
    lines = text.splitlines()
    if not lines:
        return '', []
    from .recall import tokens
    terms = _task_terms(query)
    scored = []
    for i, line in enumerate(lines):
        local = set(tokens(line))
        score = len(terms & local)
        if i < 12:
            score += 0.5
        if 'current' in line.casefold() or 'decision' in line.casefold():
            score += 1
        if 'closed' in line.casefold() or 'hold' in line.casefold():
            score += 0.5
        scored.append((score, i))
    priority = [0, *[i for _, i in sorted(scored, reverse=True)[:10]]]
    chosen, consumed = [], 0
    for center in priority:
        for i in range(max(0, center-1), min(len(lines), center+2)):
            if i in chosen:
                continue
            candidate = f'L{i+1}: {lines[i]}'
            if consumed + len(candidate) + 1 > MAX_EXCERPT_CHARS:
                continue
            chosen.append(i)
            consumed += len(candidate)+1
        if consumed > MAX_EXCERPT_CHARS * 0.85:
            break
    indices = sorted(chosen)
    return '\n'.join(f'L{i+1}: {lines[i]}' for i in indices), [i+1 for i in indices]


def check(store, context, scope, routing, query):
    """Read only authorized, relevant current source owners for a foreground task."""
    from .configuration import ViewReader
    from .dreaming import dispositions, _source_keys
    from .dream_sources import _open_source
    from .recall import route_matches, tokens
    status = {'status': 'gap', 'items': [], 'gaps': [], 'notice': (
        'Current-state source excerpts are checked at read time, not independently '
        'certified scientific conclusions; use original owner for consequential detail.')}
    owners = routing.get('context', {}).get('owners', [])
    if not query.strip():
        status['gaps'].append({'reason': 'current_question_required'})
        return [], status
    if not owners:
        status['gaps'].append({'reason': 'current_owners_not_configured'})
        return [], status
    route_hits, _ = route_matches(routing, query)
    matched = {topic['id'] for topic in route_hits}
    # The index is a project-wide owner; narrower question/result owners are
    # selected only for matching topics. No heuristic filesystem search.
    terms = _task_terms(query)
    relevance = {topic['id']: len(terms.intersection(tokens(' '.join([
        topic['id'], topic['title'], *topic.get('aliases', [])])))) for topic in route_hits}
    candidates = [entry for entry in owners if entry['role'] == 'index' or matched.intersection(entry['topic_ids'])]
    candidates.sort(key=lambda e: (VALID_ROLES_ORDER[e['role']],
                    -max((relevance.get(t, 0) for t in e['topic_ids']), default=0),
                    -e.get('priority', 0), e['id']))
    if not candidates:
        status['gaps'].append({'reason': 'no_owner_for_task'})
        return [], status
    # Reserve one read per matching role before filling the bounded remainder.
    selected, roles = [], set()
    for entry in candidates:
        if entry['role'] not in roles:
            selected.append(entry['id'])
            roles.add(entry['role'])
    selected.extend(entry['id'] for entry in candidates if entry['id'] not in selected)
    selected = set(selected[:MAX_SELECTED])
    try:
        reader = ViewReader(store, context)
        _, profile = reader._policy()
        catalog = reader._catalog(profile)
        if reader._target(profile) != scope['project_id']:
            _fail('scope_mismatch', 'Owner source scope must match the actual caller')
    except MemoryError as exc:
        status['gaps'].append({'reason': exc.code})
        return [], status
    units = []
    for entry in candidates:
        selection = {'grant_id': entry['grant_id']}
        if entry.get('relative_path'):
            selection['relative_path'] = entry['relative_path']
        try:
            specs = catalog.resolve([selection])
            spec = specs[0]
            if spec['format'] != 'document' or not catalog.authorized(spec):
                _fail('source_forbidden', 'A foreground owner requires a current document grant')
            uri = Path(spec['path']).as_uri()
            bindings = _source_keys(['source-uri:' + uri])
            if any(item['target'] == scope['project_id'] and
                   item['scope'] in {'research', 'collaboration'} and
                   item['kind'] in {'no_reuse', 'user_rejected', 'inference_error', 'no_value'} and
                   bindings.intersection(_source_keys(item['source_keys']))
                   for item in dispositions(store)['items']):
                _fail('source_forbidden', 'An owner source has been prohibited for reuse')
            if entry['id'] not in selected:
                _, latest_profile = reader._policy()
                if not reader._catalog(latest_profile).authorized(spec):
                    _fail('source_forbidden', 'Source grant was withdrawn before the pointer was returned')
                status['gaps'].append({'id':entry['id'], 'reason':'owner_selection_limit',
                                      'read_hint':{'path':spec['path']}})
                continue
            with _open_source(spec) as stream:
                before = os.fstat(stream.fileno())
                if not 0 < before.st_size <= MAX_FILE_BYTES:
                    _fail('owner_size_gap', 'Current owner exceeds the bounded read limit')
                raw = stream.read(MAX_FILE_BYTES + 1)
                after = os.fstat(stream.fileno())
                if (len(raw) != before.st_size or len(raw) > MAX_FILE_BYTES or
                        (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns,
                         before.st_ctime_ns) !=
                        (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns,
                         after.st_ctime_ns)):
                    _fail('source_changed', 'Owner changed during bounded read')
            text = raw.decode('utf-8', errors='strict')
            if SECRET.search(text):
                _fail('sensitive_content', 'Sensitive owner text must not enter context')
            # Grants and source-use restrictions may change while source I/O happens.
            _, latest_profile = reader._policy()
            if not reader._catalog(latest_profile).authorized(spec):
                _fail('source_forbidden', 'Source grant was withdrawn during the read')
            digest = hashlib.sha256(raw).hexdigest()
            excerpt, line_ids = _excerpt(text, query)
            if not excerpt:
                _fail('empty_owner', 'The current owner has no usable selected text')
            info = {'id':entry['id'], 'grant_id':entry['grant_id'],
                    'role':entry['role'], 'path':spec['path'],
                    'source_version':digest, 'excerpt_lines':line_ids,
                    'excerpt_only':len(line_ids) < len(text.splitlines())}
            status['items'].append(info)
            label = (f"[current owner; read-verified source hash {digest[:16]}; "
                     "literal excerpt, not complete document or scientific proof]\n")
            unit_text = label + excerpt + f"\nOriginal owner: {spec['path']} @ {digest[:16]}"
            units.append({'id':'owner:'+entry['id']+':'+digest[:16],
                          'unit_id':entry['id'], 'role':'current', 'level':'source',
                          'text':unit_text, 'as_of':digest[:16], 'task_modes':[],
                          'freshness':'read-verified',
                          'read_hint': {'path':spec['path']}})
        except (MemoryError, OSError, UnicodeError, KeyError, TypeError, ValueError) as exc:
            code = exc.code if isinstance(exc, MemoryError) else 'owner_unverifiable'
            status['gaps'].append({'id':entry['id'], 'reason':code})
    status['status'] = 'checked' if status['items'] and not status['gaps'] else ('partial' if status['items'] else 'gap')
    return units, status


VALID_ROLES_ORDER = {'index':0, 'result':1, 'question':2}
