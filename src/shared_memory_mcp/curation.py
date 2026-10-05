"""Small, reviewed retrieval metadata journals; captured Markdown stays intact.

All mutations use the core's existing local write gate and atomic publication.
A curation journal is not independent evidence or an authorization database.
"""
from __future__ import annotations

from pathlib import Path

from .core import (HARNESSES, MAX_RECORD_BYTES, MAX_RECORDS, RECORD_ID, SAFE_ID,
                   MemoryError, _decode, _digest, _fail, _json, _keys,
                   _nonempty, _now, _sources, _utc)

DETAIL_FIELDS = {'summary', 'conditions', 'domain', 'topics', 'aliases', 'share_with',
                 'statement_type', 'observed_at', 'source_roles', 'relations', 'extensions'}
STATEMENT_TYPES = {'observation', 'experiment', 'result', 'interpretation', 'hypothesis',
                   'user_decision', 'engineering_lesson', 'reference'}
SOURCE_ROLES = {'owner', 'evidence', 'derivative', 'origin'}
RELATIONS = {'derived_from', 'related_to', 'conflicts_with', 'corrects'}


def safe_path(store, relative):
    path = store.root / relative
    current = store.root
    for part in Path(relative).parts:
        if part in ('..', '.') or Path(relative).is_absolute():
            _fail('unsafe_path', 'Curation/config path must remain inside the store')
        current = current / part
        if current.is_symlink():
            _fail('unsafe_path', 'Curation/config paths may not be symlinks')
    return path


def read_json(store, relative, default=None):
    path = safe_path(store, relative)
    if not path.exists():
        return default
    try:
        if not path.is_file() or path.stat().st_size > MAX_RECORD_BYTES:
            raise ValueError('Non-file or oversized JSON')
        return _decode(path.read_text('utf-8'))
    except (OSError, ValueError, MemoryError) as exc:
        _fail('corrupt_curation', f'Cannot read bounded curation/config: {path.name}: {exc}')


def validate_details(details, record, project_ids):
    _keys(details, set(), DETAIL_FIELDS, 'details')
    for key in ('summary', 'conditions'):
        if key in details:
            _nonempty(details[key], key)
            if len(details[key]) > 8192:
                _fail('invalid_input', f'{key} exceeds the text bound')
    if 'domain' in details and (not isinstance(details['domain'], str) or not SAFE_ID.fullmatch(details['domain'])):
        _fail('invalid_input', 'domain must be a short identifier')
    for key in ('topics', 'aliases', 'share_with'):
        if key not in details:
            continue
        value = details[key]
        if (not isinstance(value, list) or len(value) > 32 or
                any(not isinstance(x, str) or not x.strip() or len(x) > 256 for x in value) or
                len(set(value)) != len(value)):
            _fail('invalid_input', f'{key} must contain distinct bounded strings')
    sharing = details.get('share_with', [])
    if sharing:
        if details.get('domain') != 'engineering' or record['scope'] != 'project':
            _fail('invalid_input', 'Only project-scoped engineering records can be explicitly shared')
        if any(p not in project_ids or p == record['project_id'] for p in sharing):
            _fail('invalid_input', 'Sharing targets must be other registered projects')
    if 'statement_type' in details and (not isinstance(details['statement_type'], str) or details['statement_type'] not in STATEMENT_TYPES):
        _fail('invalid_input', 'Unsupported statement_type')
    if 'observed_at' in details:
        _utc(details['observed_at'])
    if 'source_roles' in details:
        roles = details['source_roles']
        if not isinstance(roles, list) or len(roles) > 32:
            _fail('invalid_input', 'source_roles must be a bounded list')
        seen = set()
        source_uris = {s['uri'] for s in record['sources']}
        for item in roles:
            _keys(item, {'uri', 'role'}, {'uri', 'role'}, 'source role')
            if (not isinstance(item['uri'], str) or not isinstance(item['role'], str) or
                    item['uri'] not in source_uris or item['uri'] in seen or item['role'] not in SOURCE_ROLES):
                _fail('invalid_input', 'Source roles must identify distinct original record sources')
            seen.add(item['uri'])
    if 'relations' in details:
        value = details['relations']
        if not isinstance(value, list) or len(value) > 32:
            _fail('invalid_input', 'relations must be a bounded list')
        for item in value:
            _keys(item, {'type', 'uri'}, {'type', 'uri'}, 'relation')
            if not isinstance(item['type'], str) or item['type'] not in RELATIONS:
                _fail('invalid_input', 'Unsupported relation type')
            _sources([{'uri': item['uri']}])
    if 'extensions' in details and not isinstance(details['extensions'], dict):
        _fail('invalid_input', 'extensions must be an optional JSON object')
    try:
        if len(_json(details).encode('utf-8')) > 32768:
            _fail('invalid_input', 'details exceed the metadata bound')
    except (TypeError, ValueError):
        _fail('invalid_input', 'details must be finite JSON data')
    return details


def validate_review(review):
    _keys(review, {'reason', 'evidence'}, {'reason', 'evidence'}, 'review')
    _nonempty(review['reason'], 'review.reason')
    _sources(review['evidence'])


def journals(store, project_id, records):
    """Validate before applying any metadata, including all operation identities."""
    directory = safe_path(store, Path('curation') / project_id)
    by_id = {r['id']: r for r in records}
    project_ids = {p['id'] for p in store._registry()['projects']}
    result, operations = {}, {}
    if not directory.exists():
        return result, operations
    paths = sorted(directory.glob('*.json'))
    if len(paths) > MAX_RECORDS:
        _fail('corpus_limit', 'Curation journal count exceeds the project bound')
    for path in paths:
        try:
            if not RECORD_ID.fullmatch(path.stem) or path.stem not in by_id:
                raise ValueError('Orphaned or invalid curation identity')
            r = by_id[path.stem]
            doc = read_json(store, path.relative_to(store.root))
            _keys(doc, {'version', 'record_id', 'content_digest', 'events'},
                  {'version', 'record_id', 'content_digest', 'events'}, 'curation journal')
            if doc['version'] != 1 or doc['record_id'] != r['id'] or doc['content_digest'] != r['content_digest']:
                raise ValueError('Curation content binding mismatch')
            if not isinstance(doc['events'], list) or not 1 <= len(doc['events']) <= 512:
                raise ValueError('Invalid curation event count')
            details, retired, previous = {}, False, 'start'
            for event in doc['events']:
                _keys(event, {'key', 'digest', 'payload', 'at'}, {'key', 'digest', 'payload', 'at'}, 'curation event')
                _nonempty(event['key'], 'curation key')
                _utc(event['at'])
                p = event['payload']
                _keys(p, {'id', 'content_digest', 'context', 'details', 'retired', 'review', 'previous', 'capture_digest'},
                      {'id', 'content_digest', 'context', 'details', 'retired', 'review', 'previous', 'capture_digest'}, 'curation payload')
                if (p['id'] != r['id'] or p['content_digest'] != r['content_digest'] or p['previous'] != previous or
                        event['digest'] != _digest(p) or event['key'] in operations):
                    raise ValueError('Curation digest, chain or replay identity mismatch')
                c = p['context']
                _keys(c, {'cwd', 'harness', 'session_id', 'actor', 'project_id'},
                      {'cwd', 'harness', 'session_id', 'actor', 'project_id', 'task_id'}, 'curation caller')
                if c['harness'] not in HARNESSES or not Path(c['cwd']).is_absolute() or c['project_id'] != project_id:
                    raise ValueError('Invalid curation caller')
                for key in ('session_id', 'actor'):
                    _nonempty(c[key], key)
                validate_review(p['review'])
                if p['retired'] is not None and not isinstance(p['retired'], bool):
                    raise ValueError('retired must be boolean or absent')
                _keys(p['details'], set(), DETAIL_FIELDS, 'details')
                details = {**details, **p['details']}
                validate_details(details, r, project_ids)
                if p['retired'] is not None:
                    retired = p['retired']
                previous = event['digest']
                operations[event['key']] = (r['id'], event)
            result[r['id']] = {'details': details, 'recall_retired': retired,
                               'curation_revision': _digest(doc), 'curation_audit': doc['events']}
        except (ValueError, TypeError, KeyError, OSError, MemoryError) as exc:
            _fail('corrupt_curation', f'Cannot trust curation {path.name}: {exc}')
    return result, operations


def projected_records(store, project_id):
    records = store._effective(store._load(project_id))
    metadata, _ = journals(store, project_id, records)
    result = []
    for record in records:
        overlay = metadata.get(record['id'], {'details': {}, 'recall_retired': False,
                                              'curation_revision': 'absent', 'curation_audit': []})
        r = {**record, **overlay, 'lifecycle_status': record['effective_status']}
        if r['recall_retired'] and r['effective_status'] == 'active':
            r['effective_status'] = 'retired'
        result.append(r)
    return result


def curate(store, context, id, review, idempotency_key, details=None, retired=None,
           expected_content_digest=None, expected_revision=None, *, capture_digest=None):
    if not isinstance(id, str) or not RECORD_ID.fullmatch(id):
        _fail('invalid_input', 'curate requires a canonical record ID')
    validate_review(review)
    _nonempty(idempotency_key, 'idempotency_key')
    if retired is not None and not isinstance(retired, bool):
        _fail('invalid_input', 'retired must be boolean')
    details = {} if details is None else details
    _keys(details, set(), DETAIL_FIELDS, 'details')
    with store._gate():
        scope = store._resolve(context)
        records = store._effective(store._load(scope['project_id']))
        r = next((r for r in records if r['id'] == id and store._visible(r, scope)), None)
        if r is None or 'withdraws' in r:
            _fail('not_found', 'Curation target must belong to the actual caller scope, not an imported project')
        metadata, operations = journals(store, scope['project_id'], records)
        current = metadata.get(id, {'details': {}, 'curation_revision': 'absent', 'curation_audit': [], 'recall_retired': False})
        caller = {key: context[key] for key in ('harness', 'session_id', 'actor', 'task_id') if key in context}
        caller.update(cwd=scope['cwd'], project_id=scope['project_id'])
        request = {'id': id, 'content_digest': r['content_digest'], 'context': caller,
                   'details': details, 'retired': retired, 'review': review, 'capture_digest': capture_digest}
        prior = operations.get(idempotency_key)
        if prior:
            prior_payload = {k: v for k, v in prior[1]['payload'].items() if k != 'previous'}
            if prior[0] != id or _digest(prior_payload) != _digest(request):
                _fail('idempotency_conflict', 'Curation key was used with a different payload')
            return {'status': 'ok', 'id': id, 'curation_revision': current['curation_revision'], 'replayed': True}
        if expected_content_digest is not None and expected_content_digest != r['content_digest']:
            _fail('stale_record', 'Record content changed since the source check')
        if expected_revision is not None and expected_revision != current['curation_revision']:
            _fail('stale_curation', 'Curation changed since the previous read')
        merged = {**current['details'], **details}
        validate_details(merged, r, {p['id'] for p in store._registry()['projects']})
        events = current['curation_audit']
        request['previous'] = events[-1]['digest'] if events else 'start'
        event = {'key': idempotency_key, 'digest': _digest(request), 'payload': request, 'at': _now()}
        doc = {'version': 1, 'record_id': id, 'content_digest': r['content_digest'], 'events': events + [event]}
        data = (_json(doc) + '\n').encode('utf-8')
        if len(data) > MAX_RECORD_BYTES or len(doc['events']) > 512:
            _fail('curation_limit', 'Curation journal exceeds its explicit local bound')
        path = safe_path(store, Path('curation') / scope['project_id'] / (id + '.json'))
        store._publish(path, data)
        return {'status': 'ok', 'id': id, 'curation_revision': _digest(doc), 'replayed': False}


def capture(store, context, record, idempotency_key, review=None, details=None):
    """Replayable admission: interrupted calls leave a candidate, never an implicit review."""
    store._record_input(record)
    _nonempty(idempotency_key, 'idempotency_key')
    details = {} if details is None else details
    if review is not None:
        validate_review(review)
    with store._gate():
        scope = store._resolve(context)
        if record['scope'] == 'task' and 'task_id' not in scope:
            _fail('invalid_input', 'Task-scoped records require context.task_id')
        validate_details(details, {**record, 'project_id': scope['project_id']},
                         {p['id'] for p in store._registry()['projects']})
        digest = _digest({'context': context, 'record': record, 'review': review, 'details': details})
        # Bind the entire call before the first candidate can become visible.
        # The existing proposal only binds context/record, not review/details.
        relative = Path('capture') / scope['project_id'] / (_digest(idempotency_key) + '.json')
        expected = {'version': 1, 'project_id': scope['project_id'], 'key': idempotency_key, 'digest': digest}
        existing = read_json(store, relative)
        if safe_path(store, relative).exists():
            _keys(existing, set(expected), set(expected), 'capture receipt')
            if (type(existing['version']) is not int or existing['version'] != 1 or
                    existing['project_id'] != scope['project_id'] or existing['key'] != idempotency_key or
                    not isinstance(existing['digest'], str) or len(existing['digest']) != 64 or
                    any(c not in '0123456789abcdef' for c in existing['digest'])):
                _fail('corrupt_capture', 'Cannot trust capture request binding')
            if existing['digest'] != digest:
                _fail('idempotency_conflict', 'Capture key was used with a different payload')
        else:
            # Completed pre-repair calls already have a full binding in curation.
            records = store._effective(store._load(scope['project_id']))
            prior = store._retry(records, 'proposal', 'capture:' + idempotency_key,
                                 _digest({'context': context, 'record': record}))
            if prior:
                _, operations = journals(store, scope['project_id'], records)
                operation = operations.get('capture-curation:' + idempotency_key)
                if not operation or operation[0] != prior['id'] or not operation[1]['payload']['capture_digest']:
                    _fail('incomplete_capture', 'Legacy candidate has no complete capture binding; explicit recovery is required')
                if operation[1]['payload']['capture_digest'] != digest:
                    _fail('idempotency_conflict', 'Capture key was used with a different payload')
            data = (_json(expected) + '\n').encode('utf-8')
            if len(data) > MAX_RECORD_BYTES:
                _fail('invalid_input', 'Capture request binding exceeds the metadata bound')
            store._publish(safe_path(store, relative), data)
    proposal = store.propose(context, record, 'capture:' + idempotency_key)
    id = proposal['record']['id']
    curation_review = review or {'reason': 'Candidate metadata only; source truth has not been reviewed.',
                                 'evidence': record['sources']}
    curate(store, context, id, curation_review, 'capture-curation:' + idempotency_key,
           details=details, capture_digest=digest)
    if review is not None:
        store.promote(context, id, review, 'capture-review:' + idempotency_key)
    full = store.read(context, [id], include_inactive=True, include_shared=False)['items'][0]
    return {'status': 'ok', 'id': id, 'project_id': full['project_id'],
            'effective_status': full['effective_status'], 'replayed': proposal['replayed'],
            'curation_revision': full['curation_revision']}
