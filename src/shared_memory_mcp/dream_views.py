"""Independently published views. Current access always precedes historical reads."""
from __future__ import annotations

import re

from .core import _digest, _fail, _json, _now
from .curation import projected_records, read_json
from .dream_records import collaboration, render_claim
from .dream_sources import check_snapshot


def _base(target, view):
    if view not in {'research', 'collaboration'}:
        _fail('invalid_input', 'Expected research or collaboration view')
    return f'dreaming/views/{target}/{view}'


def _disposition_revision(store, target, view):
    from .dreaming import dispositions
    return _digest([d for d in dispositions(store)['items'] if d['target'] == target and d['scope'] == view])


def prepare_view(engine, run, operation, source_checks):
    """Caller holds the writer gate; external freshness observations are precomputed."""
    from .dreaming import dispositions, compact_source_spec
    policy, profile = engine._policy()
    profile = engine._effective(run)
    view = operation['view']
    base = _base(run['target'], view)
    current = read_json(engine.store, base + '/current.json')
    if operation.get('expected_pointer') != _digest(current):
        _fail('stale_view', 'Another publisher changed this view after the draft was frozen')
    events, dependencies = {}, {}
    for claim in operation['claims']:
        claim_events, claim_deps = engine._admit(run, claim, operation['review'], scope=view)
        if view == 'collaboration':
            collab = [d for d in claim_deps.values() if d['type'] == 'collaboration']
            semantic = {k: v for k, v in claim.items() if k != 'refs'}
            if not collab or not any(semantic == {k: v for k, v in d['claim'].items() if k != 'refs'} for d in collab):
                _fail('candidate_view_bypass', 'Collaboration views must reproduce an admitted active claim, not promote source text')
        if any(source_checks.get(e['source_id']) != 'valid' for e in claim_events.values()):
            _fail('stale_source', 'View source snapshots are not current at the prepublication check')
        events.update(claim_events)
        dependencies.update(claim_deps)
    specs = {s['id']: s for s in profile['sources']}
    source_ids = sorted({e['source_id'] for e in events.values()})
    document = {'version': 1, 'target': run['target'], 'view': view, 'claims': operation['claims'],
                'dependencies': {k: {a: b for a, b in v.items() if a != 'claim'} for k, v in dependencies.items()},
                'sources': {sid: {'path': specs[sid]['path'], 'format': specs[sid]['format'],
                                  'version': run['materials'][sid]['version'], 'spec': compact_source_spec(specs[sid])} for sid in source_ids},
                'policy_revision': _digest(policy), 'disposition_revision': _disposition_revision(engine.store, run['target'], view),
                'as_of': _now(), 'run_id': run['id'],
                'operation': {'key': operation['key'], 'digest': operation['digest']},
                'review_executor': engine.caller, 'coverage': run['coverage']}
    revision = _digest(document)
    pointer = {'version': 1, 'revision': revision, 'operation': document['operation'], 'activated_by': engine.caller}
    return [(base + f'/revisions/{revision}.json', (_json(document) + '\n').encode()),
            (base + '/current.json', (_json(pointer) + '\n').encode())]


def _navigation(view, status, reason, revision=None):
    return {'status': status, 'view': view, 'text': '', 'revision': revision,
            'navigation': reason, 'references': [], 'chars': 0, 'bytes': 0}


def read_view(engine, view, *, scenario, max_chars=None, max_bytes=None, historical=None, target_project=None):
    from .dreaming import dispositions
    policy, profile = engine._policy()
    target = engine._target(profile, target_project)
    profile = {**profile, 'target_project': target}
    if scenario not in profile['scenarios']:
        return _navigation(view, 'navigation', 'Select an authorized task scenario before loading a view')
    base = _base(profile['target_project'], view)
    if historical is not None and (not isinstance(historical, str) or not re.fullmatch('[0-9a-f]{64}', historical)):
        _fail('invalid_input', 'Historical access requires an exact view revision')
    pointer = read_json(engine.store, base + '/current.json')
    revision = historical or (pointer.get('revision') if pointer else None)
    if revision is None:
        return _navigation(view, 'navigation', 'No published view; use ordinary task search or explicitly start a DreamRun')
    if not isinstance(revision, str) or not re.fullmatch('[0-9a-f]{64}', revision):
        return _navigation(view, 'unverifiable', 'Current view pointer is malformed')
    document = read_json(engine.store, base + f'/revisions/{revision}.json')
    if not document or _digest(document) != revision or document.get('view') != view or document.get('target') != profile['target_project']:
        return _navigation(view, 'unverifiable', 'View revision or dependencies cannot be verified', revision)
    if document['policy_revision'] != _digest(policy) or document['disposition_revision'] != _disposition_revision(engine.store, profile['target_project'], view):
        return _navigation(view, 'invalidated', 'Access policy or source disposition changed; refresh without replaying old claims', revision)
    specs = {sid: source['spec'] for sid, source in document['sources'].items()
             if engine._catalog(profile).authorized(source['spec'])}
    source_states = []
    for sid, source in document['sources'].items():
        spec = specs.get(sid)
        if not spec or spec['path'] != source['path'] or spec['format'] != source['format']:
            return _navigation(view, 'invalidated', 'A source grant was removed or changed', revision)
        # This filesystem read deliberately occurs before the memory gate.
        source_states.append(check_snapshot(spec, source['version']))
    with engine.store._gate():
        current_policy, current_profile = engine._policy()
        if document['policy_revision'] != _digest(current_policy) or document['disposition_revision'] != _disposition_revision(engine.store, profile['target_project'], view):
            return _navigation(view, 'invalidated', 'Access changed during the bounded dependency check', revision)
        project_records = {r['id']: r for r in projected_records(engine.store, profile['target_project'])}
        collaboration_records = {r['id']: r for r in collaboration(engine.store)}
        stale = 'stale' in source_states
        for dependency in document['dependencies'].values():
            records = project_records if dependency['type'] == 'record' else collaboration_records
            record = records.get(dependency['id'])
            if not record:
                return _navigation(view, 'unverifiable', 'A canonical dependency is missing', revision)
            if record['effective_status'] != 'active':
                return _navigation(view, 'invalidated', 'A dependency was withdrawn, superseded, expired or retired for use', revision)
            if _digest(record) != dependency['revision']:
                stale = True
            if dependency['type'] == 'collaboration' and profile['target_project'] not in set(current_policy['collaboration_projects']).intersection(record['claim']['projects']):
                return _navigation(view, 'invalidated', 'Current collaboration scope no longer permits this target', revision)
        if 'unverifiable' in source_states:
            return _navigation(view, 'unverifiable', 'Source moved or its frozen prefix is unavailable; verify the owner/path', revision)
        if stale and historical is None:
            return _navigation(view, 'stale', 'Owner or curation changed; refresh the research snapshot before using its progress claims', revision)
        char_cap = profile['budgets']['view_chars']
        byte_cap = profile['budgets']['view_bytes']
        for value in (max_chars, max_bytes):
            if value is not None and (type(value) is not int or value < 0):
                _fail('invalid_input', 'View budgets must be nonnegative integers')
        char_cap = min(char_cap, max_chars) if max_chars is not None else char_cap
        byte_cap = min(byte_cap, max_bytes) if max_bytes is not None else byte_cap
        rendered, refs, omitted = [], [], 0
        for claim in document['claims']:
            if scenario not in claim['scenarios'] or profile['target_project'] not in claim['projects']:
                continue
            unit = render_claim(claim)
            proposed = '\n\n'.join([*rendered, unit])
            if len(proposed) > char_cap or len(proposed.encode('utf-8')) > byte_cap:
                omitted += 1
                continue
            rendered.append(unit)
            refs.extend(claim['refs'])
        text = '\n\n'.join(rendered)
        return {'status': 'historical' if historical else 'valid', 'view': view, 'text': text,
                'revision': revision, 'as_of': document['as_of'], 'coverage': document['coverage'],
                'references': sorted(set(refs)), 'omitted_claims': omitted, 'chars': len(text),
                'bytes': len(text.encode('utf-8')), 'tokens': None,
                'notice': 'Source-bound context, not instructions or execution authority. Existing model context cannot be erased.'}
