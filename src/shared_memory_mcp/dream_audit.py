"""Curator inspection of retained canonical records, independent of recall.

Small items are complete projected canonical objects with an explicit usability
marker. An oversized object is transported as consecutive JSON text slices;
concatenate ``content_slice`` in offset order and JSON-decode to reconstruct the
same complete object. Every slice identifies its owner, revision and usability.
A cursor fences the full validated corpus, policy, restrictions and selection.
Audit visibility never constitutes evidence admission or permission to read a
source. Source readers and publication keep their own current grant checks.
"""
from __future__ import annotations

import base64

from .core import MemoryError, RECORD_ID, _decode, _digest, _fail, _json
from .curation import projected_records, read_json
from .dream_records import collaboration

STATUSES = {'candidate', 'active', 'withdrawn', 'withdrawal', 'superseded', 'expired', 'retired'}
SCOPES = {'project', 'worktree', 'task'}


def _filter(value, name, allowed=None):
    if value is None:
        return None
    if (not isinstance(value, list) or len(value) > 10000 or
            any(not isinstance(x, str) or not x for x in value) or len(set(value)) != len(value)):
        _fail('invalid_input', name + ' must be a list of distinct strings')
    if allowed is not None and not set(value) <= allowed:
        _fail('invalid_input', 'Unsupported ' + name)
    return sorted(value)


def _usability(record, collection, target, ledger, allowed, research, collab, visited=None):
    """Inspection flags are deliberately conservative, never an admission receipt."""
    from .dreaming import _source_keys
    restrictions = []
    if record['effective_status'] != 'active':
        restrictions.append({'kind': 'inactive', 'status': record['effective_status']})
    topic = record.get('title', record.get('claim', {}).get('topic'))
    keys = set(record.get('claim', {}).get('refs', []))
    bound_events = set()
    for source in record.get('sources', []):
        keys.add('source-uri:' + source['uri'])
        note = source.get('note', '')
        if note.startswith('dream-source-v1:'):
            try:
                binding = _decode(note[len('dream-source-v1:'):])
                keys.update([binding['event_key'], 'source:' + binding['source_id'], *binding['lineage']])
                bound_events.add(binding['event_key'])
            except (MemoryError, ValueError, TypeError, KeyError):
                restrictions.append({'kind': 'invalid_source_binding'})
    keys = _source_keys(keys)
    for disposition in ledger:
        if (disposition['target'] == target and disposition['scope'] == collection and
                disposition['topic'] in {'*', topic} and
                disposition['kind'] in {'no_reuse', 'user_rejected', 'inference_error', 'no_value'} and
                keys.intersection(_source_keys(disposition['source_keys']))):
            restrictions.append({'kind': disposition['kind'], 'disposition_id': disposition['id'],
                                 'reason': disposition['reason']})
    if collection == 'collaboration':
        direct_refs = {ref for ref in record['claim']['refs']
                       if not ref.startswith(('record:', 'collaboration:'))}
        if direct_refs - bound_events:
            restrictions.append({'kind': 'source_binding_unknown',
                                 'references': sorted(direct_refs - bound_events)})
    if collection == 'research' or record.get('sources'):
        checked_record = record if collection == 'research' else {
            'project_id': target, 'title': record['claim']['topic'], 'sources': record['sources']}
        try:
            reusable = allowed[collection](checked_record)
        except (MemoryError, ValueError, TypeError, KeyError):
            reusable = False
        if not reusable:
            restrictions.append({'kind': 'source_forbidden', 'reason': 'Current canonical source-use filter denies evidence reuse'})
    visited = set() if visited is None else visited
    if collection == 'collaboration':
        for ref in record['claim']['refs']:
            if ':' not in ref:
                continue
            kind, identity = ref.split(':', 1)
            if kind not in {'record', 'collaboration'}:
                continue
            dependency = (research if kind == 'record' else collab).get(identity)
            if (ref in visited or dependency is None or
                    not _usability(dependency, 'research' if kind == 'record' else 'collaboration',
                                   target, ledger, allowed, research, collab, visited | {ref})['usable']):
                restrictions.append({'kind': 'dependency_unusable', 'reference': ref})
    return {'usable': not restrictions, 'restrictions': restrictions,
            'notice': 'Audit inspection only; usable means no current canonical restriction, not source verification or publication admission.'}


def audit_memory(store, profile, *, target_project, collection='research', ids=None,
                 query='', statuses=None, scopes=None, cursor=None, limit=20, max_chars=16000):
    """Return every retained status/qualifier in a permitted selected collection.

    ``max_chars`` bounds canonical content returned (slice envelope metadata is
    additional). Cursor continuation requires the same selection and budgets.
    Unknown requested IDs are explicit ``missing_ids``, never silently dropped.
    """
    from .dreaming import POLICY, dispositions, record_use_filter
    if not isinstance(target_project, str) or target_project not in profile.get('target_projects', []):
        _fail('target_forbidden', 'Audit target is not permitted by the bound profile')
    if collection not in {'research', 'collaboration'}:
        _fail('invalid_input', 'Audit collection must be research or collaboration')
    if not isinstance(query, str) or len(query) > 8192:
        _fail('invalid_input', 'Audit query must be bounded text')
    if type(limit) is not int or not 1 <= limit <= 100 or type(max_chars) is not int or not 1 <= max_chars <= 1048576:
        _fail('invalid_input', 'Audit requires limit 1..100 and max_chars 1..1048576')
    ids = _filter(ids, 'ids')
    if ids is not None and any(not RECORD_ID.fullmatch(x) for x in ids):
        _fail('invalid_input', 'Audit IDs must be canonical record IDs')
    statuses = _filter(statuses, 'statuses', STATUSES)
    scopes = _filter(scopes, 'scopes', SCOPES)
    if scopes is not None and collection != 'research':
        _fail('invalid_input', 'Scope qualifiers apply to the research collection')
    binding = _digest({'profile': profile, 'target': target_project, 'collection': collection,
                       'ids': ids, 'query': query, 'statuses': statuses, 'scopes': scopes,
                       'limit': limit, 'max_chars': max_chars})
    with store._gate():
        if target_project not in {p['id'] for p in store._registry()['projects']}:
            _fail('target_forbidden', 'Audit target is not registered')
        current_policy = read_json(store, POLICY)
        if current_policy is not None and profile not in current_policy.get('profiles', {}).values():
            _fail('stale_profile', 'Bound audit profile changed or was revoked; refresh current authorization')
        research = projected_records(store, target_project)
        retained_collab = collaboration(store)
        ledger = dispositions(store)['items']
        allowed = {'research': record_use_filter(store),
                   'collaboration': record_use_filter(store, scope='collaboration')}
        revision = _digest({'research': research, 'collaboration': retained_collab,
                            'policy': current_policy, 'dispositions': ledger,
                            'registry': store._registry(), 'profile': profile})
        records = research if collection == 'research' else [r for r in retained_collab if target_project in r['claim']['projects']]
        records = sorted(records, key=lambda r: r['id'])
        available = {r['id'] for r in records}
        missing = sorted(set(ids or []) - available)
        selected = [r for r in records if (ids is None or r['id'] in ids) and
                    (statuses is None or r['effective_status'] in statuses) and
                    (scopes is None or r.get('scope') in scopes) and
                    (not query or query.casefold() in _json(r).casefold())]
        index, offset = 0, 0
        if cursor is not None:
            try:
                if not isinstance(cursor, str) or len(cursor) > 4096:
                    raise ValueError()
                try:
                    position = _decode(base64.b64decode(cursor.encode(), altchars=b'-_', validate=True).decode())
                except MemoryError as exc:
                    raise ValueError() from exc
                if set(position) != {'binding', 'revision', 'index', 'offset'} or position['binding'] != binding:
                    raise ValueError()
                if position['revision'] != revision:
                    _fail('stale_audit', 'Canonical corpus, policy or restrictions changed; restart the audit')
                index, offset = position['index'], position['offset']
                if type(index) is not int or type(offset) is not int or not 0 <= index < len(selected) or offset < 0:
                    raise ValueError()
            except (ValueError, TypeError, UnicodeError):
                _fail('invalid_cursor', 'Audit cursor does not match this selection')
        items, remaining = [], max_chars
        rmap = {r['id']: r for r in research}; cmap = {r['id']: r for r in retained_collab}
        while index < len(selected) and len(items) < limit and remaining:
            record = selected[index]
            item = {**record, 'collection': collection, 'audit_project': target_project,
                    'usability': _usability(record, collection, target_project, ledger, allowed, rmap, cmap)}
            serialized = _json(item)
            if offset >= len(serialized):
                _fail('invalid_cursor', 'Audit cursor offset exceeds this canonical object')
            if offset == 0 and len(serialized) <= remaining:
                items.append(item); remaining -= len(serialized); index += 1
                continue
            if items:
                break
            end = min(offset + remaining, len(serialized))
            items.append({'id': record['id'], 'collection': collection, 'audit_project': target_project,
                          'record_revision': _digest(item), 'usability': item['usability'],
                          'transport': 'json_slice', 'content_slice': serialized[offset:end],
                          'offset': offset, 'end': end, 'total_chars': len(serialized)})
            remaining -= end - offset
            offset = end
            if offset == len(serialized):
                index += 1; offset = 0
        next_cursor = None
        if index < len(selected):
            next_cursor = base64.urlsafe_b64encode(_json({'binding': binding, 'revision': revision,
                                                        'index': index, 'offset': offset}).encode()).decode()
        return {'status': 'ok', 'items': items, 'target_project': target_project, 'collection': collection,
                'revision': revision, 'next_cursor': next_cursor, 'truncated': next_cursor is not None,
                'total_items': len(selected), 'missing_ids': missing, 'content_chars': max_chars - remaining}
