"""Scoped narrative identities and disclosed live review, not another truth store.

Canonical records/curation and immutable view revisions own every assertion.
This module validates and resolves their explicit links; it never edits prose,
reads an arbitrary source URI, or authenticates a human from an Agent's account.
"""
from __future__ import annotations

from copy import deepcopy
import re
from urllib.parse import quote

from .core import RECORD_ID, SAFE_ID, _digest, _fail, _keys, _nonempty, _sources, _utc
from .curation import read_json

ROLES = ('preference', 'goal', 'background', 'milestone', 'branch', 'outcome', 'current', 'question')
VIEW_REF = re.compile(r'^view:(research|collaboration):([0-9a-f]{64}):(\d{1,4})$')
RECORD_REF = re.compile(r'^record:([0-9a-f]{32})$')


def metadata(record):
    return record.get('details', {}).get('extensions', {}).get('narrative', {})


def validate(value):
    _keys(value, {'id', 'role'}, {'id', 'role', 'compact', 'replaces'}, 'narrative unit')
    if not isinstance(value['id'], str) or not SAFE_ID.fullmatch(value['id']) or value['role'] not in ROLES:
        _fail('invalid_narrative', 'A narrative needs a stable short id and a known role')
    if 'compact' in value:
        _nonempty(value['compact'], 'reviewed compact rendition')
        if len(value['compact'].encode('utf-8')) > 4096:
            _fail('invalid_narrative', 'Compact text exceeds 4096 UTF-8 bytes')
    refs = value.get('replaces', [])
    if (not isinstance(refs, list) or len(refs) > 16 or
            any(not isinstance(r, str) or not (VIEW_REF.fullmatch(r) or RECORD_REF.fullmatch(r)) for r in refs) or
            len(set(refs)) != len(refs)):
        _fail('invalid_narrative', 'Replacements require distinct exact record or view-unit pointers')
    return value


def view_reference(view, revision, index):
    return f'view:{view}:{revision}:{index}'


def view_target(store, project, reference):
    match = VIEW_REF.fullmatch(reference)
    if not match:
        _fail('invalid_narrative', 'Expected an exact view-unit pointer')
    view, revision, index = match.groups()
    base = f'dreaming/views/{project}/{view}'
    document = read_json(store, f'{base}/revisions/{revision}.json')
    if (not document or _digest(document) != revision or document.get('target') != project or
            document.get('view') != view or int(index) >= len(document.get('claims', []))):
        _fail('unverifiable_unit', 'The scoped view unit cannot be verified')
    return document, document['claims'][int(index)], read_json(store, base + '/current.json')


def replacements(store, project, records):
    """Published links remain tombstones after withdrawal; predecessors never revive."""
    references, identities = {}, {}
    for record in records:
        if record['status'] != 'active' or 'withdraws' in record:
            continue
        unit = metadata(record)
        if not unit:
            continue
        qualifier = store._qualifier(record)
        for ref in unit.get('replaces', []):
            references.setdefault((qualifier, ref), []).append(record['id'])
            if VIEW_REF.fullmatch(ref):
                _, old, _ = view_target(store, project, ref)
                stable = old.get('narrative', {}).get('id')
                if stable:
                    identities.setdefault((qualifier, stable), []).append(record['id'])
    return references, identities


def check_replacements(store, scope, record, details, *, records=None, context=None):
    """Caller holds the common write gate. Validate exact scope and stale targets."""
    from .curation import projected_records
    from .dreaming import record_use_filter
    unit = details.get('extensions', {}).get('narrative')
    if not unit:
        return
    validate(unit)
    shaped = {**record, 'project_id': scope['project_id']}
    if record['scope'] != 'project':
        shaped['worktree_id'] = scope['worktree_id']
    if record['scope'] == 'task':
        shaped['task_id'] = scope.get('task_id')
    qualifier = store._qualifier(shaped)
    if not record_use_filter(store)(shaped):
        _fail('source_forbidden', 'A source-use restriction forbids this narrative')
    records = projected_records(store, scope['project_id']) if records is None else records
    others = [r for r in records if r['id'] != record.get('id')]
    refs, _ = replacements(store, scope['project_id'], others)
    by_id = {r['id']: r for r in records}
    for ref in unit.get('replaces', []):
        if (qualifier, ref) in refs:
            _fail('stale_unit', 'Another published correction already replaced this exact unit')
        if match := RECORD_REF.fullmatch(ref):
            old = by_id.get(match[1])
            if (not old or old['effective_status'] != 'active' or
                    store._qualifier(old) != qualifier or not record_use_filter(store)(old)):
                _fail('scope_mismatch', 'Replacement needs an active permitted record in the exact scope')
        else:
            document, old, pointer = view_target(store, scope['project_id'], ref)
            expected = {'project_id': scope['project_id'], **document.get('qualifier', {'scope': 'project'})}
            if store._qualifier(expected) != qualifier:
                _fail('scope_mismatch', 'A view replacement cannot cross project/worktree/task scope')
            if not pointer or pointer['revision'] != VIEW_REF.fullmatch(ref)[2]:
                _fail('stale_unit', 'The view changed; reread the current unit before correction')
            if context is None:
                _fail('source_forbidden', 'A source-only correction needs the actual reviewing caller')
            from .configuration import ViewReader
            reader = ViewReader(store, context)
            _, profile = reader._policy()
            reader._target(profile, scope['project_id'])
            index = int(VIEW_REF.fullmatch(ref)[3])
            bindings = document.get('unit_bindings')
            source_ids = bindings[index]['sources'] if bindings else list(document['sources'])
            if not all(reader._catalog(profile).authorized(document['sources'][sid]['spec']) for sid in source_ids):
                _fail('source_forbidden', 'The exact replaced unit is outside current source grants')
            # A view correction cannot use a forbidden source as its target.
            from .dreaming import dispositions, _source_keys
            from pathlib import Path
            bound = {'source-uri:' + Path(document['sources'][sid]['path']).as_uri() for sid in source_ids}
            bound.update(old['refs'])
            if bindings:
                bound.update(bindings[index].get('evidence_keys', []))
            for item in dispositions(store)['items']:
                if (item['target'] == scope['project_id'] and item['scope'] == document['view'] and
                        item['topic'] in {'*', old['topic']} and item['kind'] in {'no_reuse', 'user_rejected', 'inference_error', 'no_value'} and
                        _source_keys(bound).intersection(_source_keys(item['source_keys']))):
                    _fail('source_forbidden', 'The view target is prohibited for this source use')


def mask_view(store, project, view, revision, claims, records, qualifier=None):
    """Return exact masked indices. No text matching or invented legacy mapping."""
    key = store._qualifier({'project_id': project, **(qualifier or {'scope': 'project'})})
    refs, ids = replacements(store, project, records)
    masked = {}
    for i, claim in enumerate(claims):
        replacing = set(refs.get((key, view_reference(view, revision, i)), []))
        stable = claim.get('narrative', {}).get('id')
        if stable:
            replacing.update(ids.get((key, stable), []))
        # A reviewed successor view may explicitly cite the accepted correction.
        if replacing and not any('record:' + r in claim['refs'] for r in replacing):
            masked[i] = sorted(replacing)
    return masked


def live_review(context, scope, record, basis, *, reviewed_at):
    """Trust the authorized foreground report explicitly; never invent event evidence."""
    _keys(basis, {'kind', 'excerpt', 'original_locator', 'history_gap', 'review_method'},
          {'kind', 'excerpt', 'original_locator', 'history_gap', 'review_method'}, 'live correction')
    if basis['kind'] != 'direct-current-user':
        _fail('not_live_original', 'Historical, quoted, delegated or ambiguous input is not a direct current correction')
    for field in ('excerpt', 'review_method'):
        _nonempty(basis[field], field)
        if len(basis[field].encode('utf-8')) > 4096:
            _fail('live_review_limit', 'Keep only a bounded necessary original excerpt and method')
    from .dream_sources import SECRET
    if SECRET.search(basis['excerpt']):
        _fail('sensitive_content', 'The correction excerpt contains a recognized secret')
    locator = basis['original_locator']
    if locator is None:
        if not isinstance(basis['history_gap'], str) or not basis['history_gap'].strip():
            from .curation import LOCATOR_HINT
            _fail('invalid_input', 'live_correction without original_locator needs a nonempty history_gap. ' + LOCATOR_HINT)
    else:
        _sources([locator])
    if not isinstance(basis['history_gap'], str) or len(basis['history_gap']) > 1024:
        _fail('invalid_input', 'history_gap must be a bounded disclosed limitation')
    _utc(reviewed_at)
    caller = {k: context[k] for k in ('cwd', 'harness', 'session_id', 'actor')}
    caller['cwd'] = scope['cwd']
    applicability = {'project_id': scope['project_id'], 'scope': record['scope']}
    if record['scope'] != 'project':
        applicability['worktree_id'] = scope['worktree_id']
    if record['scope'] == 'task':
        applicability['task_id'] = scope.get('task_id')
    return {**deepcopy(basis), 'assurance': 'agent-reviewed', 'caller': caller,
            'scope': applicability, 'reviewed_at': reviewed_at}


def validate_live_review(review, provenance):
    required = {'kind', 'excerpt', 'original_locator', 'history_gap', 'review_method',
                'assurance', 'caller', 'scope', 'reviewed_at'}
    _keys(review, required, required, 'stored cooperative review')
    if review['kind'] != 'direct-current-user' or review['assurance'] != 'agent-reviewed':
        _fail('invalid_assurance', 'Stored live review is cooperative, not operator attestation')
    if any(review['caller'].get(k) != provenance.get(k) for k in ('cwd', 'harness', 'session_id', 'actor')):
        _fail('invalid_assurance', 'Live review must retain the original capturing caller')
    _utc(review['reviewed_at'])
    for field in ('excerpt', 'review_method'):
        _nonempty(review[field], field)
        if len(review[field].encode('utf-8')) > 4096:
            _fail('live_review_limit', 'Stored current-message excerpt exceeds the admitted bound')
    if review['original_locator'] is None:
        _nonempty(review['history_gap'], 'native-history limitation')
    else:
        _sources([review['original_locator']])


def live_source(review):
    locator = review['original_locator']
    if locator is not None:
        return {**locator, 'note': 'Cooperative current-message Agent review; not operator attestation.'}
    caller = review['caller']
    return {'uri': f"conversation://{caller['harness']}/{quote(caller['session_id'], safe='')}",
            'note': 'Current-message basis only; native event locator unavailable. No event ID or human authentication claimed.'}
