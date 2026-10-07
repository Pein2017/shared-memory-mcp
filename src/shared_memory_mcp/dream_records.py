"""Claim validation and lock-aware canonical effects for the Dreaming publisher.

Project records keep their existing v1 Markdown format. Pein collaboration has
an explicitly versioned collection; it is not a registered Git project.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from .core import HARNESSES, MAX_RECORD_BYTES, MAX_RECORDS, RECORD_ID, _decode, _digest, _fail, _json, _keys, _nonempty, _now, _sources, _utc
from .curation import projected_records, safe_path

LEVELS = {'recorded', 'report', 'hypothesis', 'explicit', 'inferred'}
CLAIM_FIELDS = {'topic', 'text', 'level', 'conditions', 'exceptions', 'counterevidence',
                'scenarios', 'projects', 'refs', 'risks'}
REVIEW_FIELDS = {'decision', 'reason', 'scope_checked', 'counterexamples_checked', 'checked_refs'}
ACTIONS = {'record_create', 'record_approve', 'record_supersede', 'record_withdraw',
           'collaboration_create', 'collaboration_publish', 'collaboration_withdraw', 'view_publish'}


def bounded_strings(value, name, *, nonempty=False, limit=32):
    if (not isinstance(value, list) or len(value) > limit or nonempty and not value or
            any(not isinstance(x, str) or not x.strip() or len(x) > 4096 for x in value) or
            len(set(value)) != len(value)):
        _fail('invalid_input', f'{name} requires distinct bounded strings')


def validate_claim(claim):
    _keys(claim, CLAIM_FIELDS, CLAIM_FIELDS, 'claim')
    for key in ('topic', 'text', 'conditions'):
        _nonempty(claim[key], 'claim.' + key)
        if len(claim[key]) > 8192:
            _fail('claim_limit', 'Claim text or conditions exceed the bound')
    if not isinstance(claim['level'], str) or claim['level'] not in LEVELS:
        _fail('invalid_input', 'Unsupported claim evidence level')
    for key in ('exceptions', 'counterevidence', 'scenarios', 'projects', 'refs', 'risks'):
        bounded_strings(claim[key], key, nonempty=key in {'scenarios', 'projects', 'refs'})
    if len(_json(claim).encode()) > 32768:
        _fail('claim_limit', 'Claim metadata exceeds the byte bound')
    return claim


def validate_review(review):
    _keys(review, REVIEW_FIELDS, REVIEW_FIELDS, 'semantic review')
    if not isinstance(review['decision'], str) or review['decision'] not in {'approve', 'pending', 'reject'}:
        _fail('invalid_input', 'Unsupported review decision')
    _nonempty(review['reason'], 'review.reason')
    for key in ('scope_checked', 'counterexamples_checked'):
        if type(review[key]) is not bool:
            _fail('invalid_input', 'Review check flags must be booleans')
    bounded_strings(review['checked_refs'], 'checked_refs')
    return review


def reviewed(claim, review):
    validate_review(review)
    if (review['decision'] != 'approve' or not review['scope_checked'] or
            not review['counterexamples_checked'] or not set(claim['refs']) <= set(review['checked_refs'])):
        _fail('pending_review', 'Explicit source, scope and counterexample review is required')
    if claim['risks']:
        _fail('pending_review', 'Risk-bearing claims need a separately authorized responsible reviewer')


def render_claim(claim):
    lines = [f"[{claim['level']}] {claim['text']}", f"Conditions: {claim['conditions']}",
             'Scenarios: ' + ', '.join(claim['scenarios']), 'Projects: ' + ', '.join(claim['projects'])]
    if claim['exceptions']:
        lines.append('Exceptions: ' + '; '.join(claim['exceptions']))
    if claim['counterevidence']:
        lines.append('Counterevidence: ' + '; '.join(claim['counterevidence']))
    lines.append('Sources: ' + ', '.join(claim['refs']))
    return '\n'.join(lines)


def markdown(record):
    return ('```json\n' + _json({k: v for k, v in record.items() if k != 'body'}) +
            '\n```\n' + record['body']).encode('utf-8')


def parse_markdown(data):
    if not data.startswith(b'```json\n') or b'\n```\n' not in data:
        _fail('corrupt_dream_record', 'Missing canonical metadata')
    header, body = data[8:].split(b'\n```\n', 1)
    return {**_decode(header.decode()), 'body': body.decode()}


def provenance(caller):
    return {key: caller[key] for key in ('cwd', 'harness', 'session_id', 'actor')}


def validate_executor(value):
    _keys(value, {'cwd', 'harness', 'session_id', 'actor'}, {'cwd', 'harness', 'session_id', 'actor'}, 'executor')
    if not isinstance(value['harness'], str) or value['harness'] not in HARNESSES:
        _fail('corrupt_dream_record', 'Invalid executor harness')
    for field in ('cwd', 'session_id', 'actor'):
        _nonempty(value[field], 'executor.' + field)
    if not Path(value['cwd']).is_absolute():
        _fail('corrupt_dream_record', 'Executor cwd must remain absolute')


def collaboration(store):
    directory = safe_path(store, 'collaboration/Pein/records')
    paths = sorted(directory.glob('*.md'))
    if len(paths) > MAX_RECORDS:
        _fail('corpus_limit', 'Collaboration collection exceeds the bound')
    records, operation_keys = [], set()
    for path in paths:
        safe_path(store, path.relative_to(store.root))
        if path.stat().st_size > MAX_RECORD_BYTES:
            _fail('corrupt_dream_record', 'Oversized collaboration record')
        try:
            r = parse_markdown(path.read_bytes())
            fields = {'version', 'id', 'owner', 'claim', 'body', 'created_at', 'provenance', 'events'}
            _keys(r, fields, fields | {'sources'}, 'collaboration record')
            if 'sources' in r:
                _sources(r['sources'])
            if (r['version'] != 2 or r['owner'] != {'type': 'collaboration', 'subject': 'Pein'} or
                    not RECORD_ID.fullmatch(r['id']) or path.stem != r['id']):
                _fail('corrupt_dream_record', 'Unsupported collaboration owner or version')
            _utc(r['created_at'])
            validate_executor(r['provenance'])
            validate_claim(r['claim'])
            if r['claim']['level'] not in {'explicit', 'inferred'} or r['body'] != render_claim(r['claim']):
                _fail('corrupt_dream_record', 'Collaboration body/claim binding failed')
            if not isinstance(r['events'], list) or not 1 <= len(r['events']) <= 128:
                _fail('corrupt_dream_record', 'Invalid collaboration lifecycle journal')
            previous, state = 'start', None
            if r['claim']['level'] == 'inferred' and r['events'][0].get('state') != 'candidate':
                _fail('corrupt_dream_record', 'Inferred collaboration must originate as a candidate')
            for event in r['events']:
                fields = {'key', 'operation_digest', 'previous', 'state', 'executor', 'at', 'review', 'digest', 'supersedes'}
                _keys(event, fields, fields, 'collaboration event')
                _nonempty(event['key'], 'event.key')
                _utc(event['at'])
                validate_executor(event['executor'])
                validate_review(event['review'])
                if not isinstance(event['operation_digest'], str) or len(event['operation_digest']) != 64 or any(c not in '0123456789abcdef' for c in event['operation_digest']):
                    _fail('corrupt_dream_record', 'Invalid semantic operation digest')
                bounded_strings(event['supersedes'], 'supersedes')
                if any(not RECORD_ID.fullmatch(x) for x in event['supersedes']) or event['supersedes'] and event['state'] != 'active':
                    _fail('corrupt_dream_record', 'Only active events can supersede canonical predecessors')
                if (event['key'] in operation_keys or event['previous'] != previous or
                        event['digest'] != _digest({k: v for k, v in event.items() if k != 'digest'})):
                    _fail('corrupt_dream_record', 'Invalid collaboration operation chain')
                if (event['state'] not in {'candidate', 'active', 'withdrawn'} or
                        state in {'active', 'withdrawn'} and event['state'] != 'withdrawn'):
                    _fail('corrupt_dream_record', 'Invalid collaboration lifecycle transition')
                if event['state'] == 'active':
                    reviewed(r['claim'], event['review'])
                operation_keys.add(event['key'])
                previous, state = event['digest'], event['state']
            records.append({**r, 'effective_status': state})
        except (ValueError, TypeError, KeyError, OSError) as exc:
            _fail('corrupt_dream_record', f'Invalid collaboration record: {type(exc).__name__}')
    by_id = {r['id']: r for r in records}
    superseded, edges = set(), {}
    for r in records:
        for event in r['events']:
            for old in event['supersedes']:
                if old not in by_id or old == r['id'] or old in superseded or not any(e['state'] == 'active' for e in by_id[old]['events']):
                    _fail('corrupt_dream_record', 'Invalid collaboration supersession edge')
                superseded.add(old)
                edges[old] = r['id']
    for start in edges:
        seen, node = set(), start
        while node in edges:
            if node in seen:
                _fail('corrupt_dream_record', 'Cyclic collaboration supersession')
            seen.add(node)
            node = edges[node]
    return [{**r, 'effective_status': 'superseded' if r['id'] in superseded else r['effective_status']} for r in records]


def namespace(store, target):
    """Canonical bytes and curation, not mtimes or generated Run logs."""
    projected_records(store, target)
    collaboration(store)
    result = {}
    for directory, pattern in [(f'records/{target}', '*.md'), (f'curation/{target}', '*.json'),
                               ('collaboration/Pein/records', '*.md')]:
        for path in sorted(safe_path(store, directory).glob(pattern)):
            safe_path(store, path.relative_to(store.root))
            if path.stat().st_size > MAX_RECORD_BYTES:
                _fail('corpus_limit', 'Namespace object is oversized')
            result[str(path.relative_to(store.root))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


def operation_qualifier(store, target, operation):
    """Canonical scope is explicit; lifecycle operations preserve their target."""
    records = {r['id']: r for r in projected_records(store, target)}
    fields = {'scope', 'worktree_id', 'task_id'}
    desired = operation.get('qualifier', {'scope': 'project'})
    if operation['action'] in {'record_approve', 'record_withdraw'}:
        current = records.get(operation.get('record_id'))
        if not current:
            _fail('stale_record', 'Canonical target is unavailable')
        exact = {k: current[k] for k in fields if k in current}
        if 'qualifier' in operation and desired != exact:
            _fail('scope_mismatch', 'Lifecycle operations preserve the exact target qualifier')
        return exact
    _keys(desired, {'scope'}, fields, 'canonical qualifier')
    scope = desired['scope']
    expected = {'scope'} | ({'worktree_id'} if scope in {'worktree', 'task'} else set()) | ({'task_id'} if scope == 'task' else set())
    if scope not in {'project', 'worktree', 'task'} or set(desired) != expected:
        _fail('scope_mismatch', 'Mixed or missing canonical scope qualifiers')
    if scope != 'project':
        entry = next(p for p in store._registry()['projects'] if p['id'] == target)
        supported = {store._resolve({'cwd': root, 'harness': 'codex', 'session_id': 'scope-validation', 'actor': 'scope-validation', 'project_id': target})['worktree_id'] for root in entry['roots']}
        if desired['worktree_id'] not in supported:
            _fail('scope_mismatch', 'Worktree qualifier is not a registered target root')
    if scope == 'task':
        _nonempty(desired['task_id'], 'qualifier.task_id')
    if operation['action'] == 'record_supersede':
        old_ids = operation.get('predecessors', [])
        if not old_ids or any(identifier not in records or records[identifier]['effective_status'] != 'active' or
                              {k: records[identifier][k] for k in fields if k in records[identifier]} != desired for identifier in old_ids):
            _fail('scope_mismatch', 'Supersession requires active predecessors with the exact desired qualifier')
    return desired


def core_effect(store, target, operation, caller, source_uris):
    """Prepare v1 bytes under the caller's existing gate; never nest public CRUD."""
    action, key = operation['action'], operation['key']
    records = {r['id']: r for r in projected_records(store, target)}
    claim, review = operation.get('claim'), operation['review']
    now, executor = _now(), provenance(caller)
    audit = {'reason': review['reason'], 'evidence': source_uris,
             'reviewer': executor, 'reviewed_at': now}
    if action in {'record_create', 'record_supersede'}:
        r = {'version': 1, 'id': operation['reserved_id'], 'project_id': target,
             **operation_qualifier(store, target, operation), 'kind': 'hypothesis' if claim['level'] == 'hypothesis' else 'observation',
             'title': claim['topic'], 'body': render_claim(claim), 'sources': source_uris,
             'status': operation.get('visibility', 'active'), 'created_at': now,
             'provenance': executor, 'proposal': {'key': key, 'digest': operation['digest']}}
        if r['status'] == 'active':
            r.update(review=audit, promotion={'key': key + ':publish', 'digest': operation['digest']})
        if action == 'record_supersede':
            old_ids = operation.get('predecessors', [])
            if not old_ids or any(x not in records or records[x]['effective_status'] != 'active' or store._qualifier(records[x]) != store._qualifier(r) for x in old_ids):
                _fail('stale_predecessor', 'Every predecessor must remain active in the target project scope')
            r['supersedes'] = old_ids
    elif action == 'record_approve':
        current = records.get(operation['record_id'])
        if not current or current['effective_status'] != 'candidate':
            _fail('stale_record', 'Approval requires an effective scoped candidate')
        if current.get('recall_retired') or current['content_digest'] != operation['expected_content_digest']:
            _fail('stale_record', 'Approval must preserve the exact audited usable candidate payload')
        overlay = {'effective_status', 'details', 'recall_retired', 'curation_revision', 'curation_audit', 'lifecycle_status'}
        r = {k: v for k, v in current.items() if k not in overlay}
        r.update(status='active', review=audit, promotion={'key': key, 'digest': operation['digest']})
    else:
        current = records.get(operation['record_id'])
        if not current or current['effective_status'] in {'withdrawn', 'withdrawal'}:
            _fail('stale_record', 'Withdrawal requires a non-withdrawn scoped record')
        r = {'version': 1, 'id': operation['reserved_id'], 'project_id': target, **operation_qualifier(store, target, operation),
             'kind': 'decision', 'title': 'Withdrawal: ' + current['title'], 'body': review['reason'],
             'sources': source_uris, 'withdraws': current['id'], 'status': 'active', 'created_at': now,
             'provenance': executor, 'review': audit,
             'promotion': {'key': key, 'digest': operation['digest']}}
    r['content_digest'] = _digest(store._content(r))
    relative = f"records/{target}/{r['id']}.md"
    store._validate_canonical({k: v for k, v in r.items() if k != 'body'}, r['body'], store.root / relative, target)
    return relative, markdown(r)


def collaboration_effect(store, operation, caller, *, source_uris=None):
    action, claim = operation['action'], operation.get('claim')
    records = {r['id']: r for r in collaboration(store)}
    if action == 'collaboration_create':
        r = {'version': 2, 'id': operation['reserved_id'],
             'owner': {'type': 'collaboration', 'subject': 'Pein'}, 'claim': claim,
             'body': render_claim(claim), 'created_at': _now(), 'provenance': provenance(caller), 'events': []}
        if source_uris is not None:
            r['sources'] = _sources(source_uris)
        state = 'candidate' if claim['level'] == 'inferred' else operation.get('visibility', 'active')
    else:
        current = records.get(operation['record_id'])
        if not current or current['effective_status'] in {'withdrawn', 'superseded'}:
            _fail('stale_record', 'Collaboration target is unavailable')
        r = {k: v for k, v in current.items() if k != 'effective_status'}
        if action == 'collaboration_publish':
            if current['effective_status'] != 'candidate' or current['claim'] != claim:
                _fail('claim_mismatch', 'Publish the unchanged candidate after explicit semantic review')
            state = 'active'
        else:
            state = 'withdrawn'
    predecessors = operation.get('predecessors', [])
    if predecessors and (state != 'active' or any(x not in records or records[x]['effective_status'] != 'active' for x in predecessors)):
        _fail('stale_predecessor', 'Collaboration predecessors must remain active')
    event = {'key': operation['key'], 'operation_digest': operation['digest'],
             'previous': r['events'][-1]['digest'] if r['events'] else 'start', 'state': state,
             'executor': provenance(caller), 'at': _now(), 'review': operation.get('review'),
             'supersedes': predecessors}
    event['digest'] = _digest(event)
    r['events'] = [*r['events'], event]
    if len(r['events']) > 128:
        _fail('curation_limit', 'Collaboration journal exceeds its bound')
    return f"collaboration/Pein/records/{r['id']}.md", markdown(r)
