"""Independently published views. Current access always precedes historical reads."""
from __future__ import annotations

import re

from .core import _decode, _digest, _fail, _json, _now
from .curation import projected_records, read_json
from .dream_records import collaboration, render_claim, reviewed
from .dream_sources import check_snapshot


def _base(target, view):
    if view not in {'research', 'collaboration'}:
        _fail('invalid_input', 'Expected research or collaboration view')
    return f'dreaming/views/{target}/{view}'


def _disposition_revision(store, target, view):
    from .dreaming import dispositions
    return _digest([d for d in dispositions(store)['items'] if d['target'] == target and d['scope'] == view])


def _read_policy_revision(policy, profile, document):
    scenarios = {s for claim in document['claims'] for s in claim['scenarios']}
    grant_ids = {source['spec']['_grant_id'] for source in document['sources'].values()}
    collab = document['view'] == 'collaboration' or any(
        d['type'] == 'collaboration' for d in document['dependencies'].values())
    inferred = collab and any(c.get('level') == 'inferred'
                             for c in [*document['claims'], *document['dependencies'].values()])
    projects = {p for claim in document['claims'] for p in claim['projects']} if collab else set()
    inherited_access = {}
    if any(s['spec'].get('_inherited_selection') for s in document['sources'].values()):
        inherited_access['reader'] = profile.get('read_access', 'granted')
    for dependency in document['dependencies'].values():
        for source in dependency.get('sources', []):
            note = source.get('note', '')
            if note.startswith('dream-source-v1:'):
                binding = _decode(note[len('dream-source-v1:'):])
                if binding.get('source_spec', {}).get('_inherited_selection'):
                    owner = binding['profile']
                    inherited_access[owner] = policy['profiles'].get(owner, {}).get('read_access', 'granted')
    return _digest({'version': policy['version'], 'subject': policy['subject'],
                    'target_allowed': document['target'] in profile['target_projects'],
                    'scenarios': sorted(scenarios.intersection(profile['scenarios'])),
                    'grants': {g['id']: g for g in profile['source_grants'] if g['id'] in grant_ids},
                    'collaboration_projects': sorted(projects.intersection(policy['collaboration_projects'])),
                    **({'inherited_access': inherited_access} if inherited_access else {}),
                    'allow_inferred': profile['allow_inferred'] if inferred else None})


def prepare_view(engine, run, operation, source_checks):
    """Caller holds the writer gate; external freshness observations are precomputed."""
    from .dreaming import compact_source_spec
    policy, profile = engine._policy()
    profile = engine._effective(run)
    view = operation['view']
    base = _base(run['target'], view)
    current = read_json(engine.store, base + '/current.json')
    if operation.get('expected_pointer') != _digest(current):
        _fail('stale_view', 'Another publisher changed this view after the draft was frozen')
    events, dependencies, unit_bindings, claims = {}, {}, [], []
    carried_sources, carried_dependencies = {}, {}
    unit_ids = [claim.get('narrative', {}).get('id') for claim in operation['claims']]
    named = [identifier for identifier in unit_ids if identifier is not None]
    if len(named) != len(set(named)):
        _fail('duplicate_unit', 'Stable narrative identities must be unique inside one scoped view')
    previous = read_json(engine.store, base + f"/revisions/{current['revision']}.json") if current else None
    for claim in operation['claims']:
        cited = [ref for ref in claim['refs'] if ref.startswith('view-claim:')]
        if cited:
            # A refresh may carry one unchanged claim of the immediately previous revision with its
            # original dependencies, review time and reviewer; its sources are not refrozen.
            if len(claim['refs']) != 1 or not previous or not previous.get('unit_bindings'):
                _fail('invalid_input', 'A carried claim cites exactly one claim of the current view revision')
            match = [(old, binding) for old, binding in zip(previous['claims'], previous['unit_bindings'])
                     if binding.get('claim_digest') == cited[0][len('view-claim:'):]]
            if not match:
                _fail('stale_view', 'The cited claim is not part of the immediately previous view revision')
            old, binding = match[0]
            if {k: v for k, v in claim.items() if k != 'refs'} != {k: v for k, v in old.items() if k != 'refs'}:
                _fail('invalid_input', 'A carried claim must be unchanged; cite changed claims from fresh evidence')
            reviewed(claim, operation['review'])
            from .view_units import _forbidden
            sources = {sid: previous['sources'][sid] for sid in binding['sources']}
            if (any(not engine._catalog(engine._policy()[1]).authorized(source['spec']) for source in sources.values())
                    or _forbidden(engine.store, run['target'], view, old, sources, binding.get('evidence_keys', []))):
                _fail('source_forbidden', 'A carried claim source is no longer permitted for this use')
            engine._refs(run, binding['dependencies'], scope=view)  # Dependencies must still be active and usable.
            for sid, source in sources.items():
                if carried_sources.setdefault(sid, source) != source:
                    _fail('invalid_input', 'Carried claims bind one source identity to different frozen versions')
            carried_dependencies.update({ref: previous['dependencies'][ref] for ref in binding['dependencies']})
            unit_bindings.append({**binding, 'carried_from': current['revision'],
                                  'as_of': binding.get('as_of', previous['as_of']),
                                  'review_executor': binding.get('review_executor', previous['review_executor'])})
            claims.append(old)
            continue
        claims.append(claim)
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
        unit_bindings.append({'sources': sorted({e['source_id'] for e in claim_events.values()}),
                              'dependencies': sorted(claim_deps), 'claim_digest': _digest(claim),
                              'evidence_keys': sorted({key for e in claim_events.values() for key in [e['key'], *e.get('lineage', [])]})})
    specs = {s['id']: s for s in profile['sources']}
    source_ids = sorted({e['source_id'] for e in events.values()})
    fresh = {sid: {'path': specs[sid]['path'], 'format': specs[sid]['format'],
                   'version': run['materials'][sid]['version'], 'spec': compact_source_spec(specs[sid])} for sid in source_ids}
    if any(fresh[sid] != carried_sources[sid] for sid in set(fresh) & set(carried_sources)):
        _fail('invalid_input', 'A carried claim and a fresh claim bind one source identity to different versions')
    progress = engine._progress(run)
    for sid, source in fresh.items():
        accepted = (progress or {'sources': {}})['sources'].get(sid, {}).get('accepted_gaps', [])
        if accepted:  # Accepted permanent gaps stay visible to readers of any view citing the source.
            source['accepted_gaps'] = [{k: g[k] for k in ('reason', 'note', 'start', 'end')} for g in accepted[-8:]]
    dependencies = {**carried_dependencies, **{k: {a: b for a, b in v.items() if a != 'claim'} for k, v in dependencies.items()}}
    document = {'version': 1, 'target': run['target'], 'view': view, 'claims': claims,
                'unit_bindings': unit_bindings, 'qualifier': {'scope': 'project'},
                'dependencies': dependencies,
                'sources': {**carried_sources, **fresh},
                'policy_revision': _digest(policy), 'disposition_revision': _disposition_revision(engine.store, run['target'], view),
                'as_of': _now(), 'run_id': run['id'],
                'operation': {'key': operation['key'], 'digest': operation['digest']},
                'review_executor': engine.caller, 'coverage': run['coverage']}
    for sid, source in document['sources'].items():
        if source['format'] == 'pi':
            source['ancestry_verified'] = all(e.get('ancestry_verified') is True
                                              for e in events.values() if e['source_id'] == sid)
            if not source['ancestry_verified']:
                _fail('unverified_branch', 'A Pi view requires verified structural ancestry')
    document['read_policy_revision'] = _read_policy_revision(policy, profile, document)
    revision = _digest(document)
    pointer = {'version': 1, 'revision': revision, 'operation': document['operation'], 'activated_by': engine.caller}
    return [(base + f'/revisions/{revision}.json', (_json(document) + '\n').encode()),
            (base + '/current.json', (_json(pointer) + '\n').encode())]


def _navigation(view, status, reason, revision=None, *, available_scenarios=None):
    result = {'status': status, 'view': view, 'text': '', 'revision': revision,
              'navigation': reason, 'references': [], 'chars': 0, 'bytes': 0}
    if available_scenarios is not None:
        result['available_scenarios'] = sorted(available_scenarios)
    return result


def read_view(engine, view, *, scenario, max_chars=None, max_bytes=None, historical=None, target_project=None, compact=True,
              unit_index=None, page=None):
    """Public reader; unit selection and authorization have one implementation."""
    from .view_units import read_view as read_units
    return read_units(engine, view, scenario=scenario, max_chars=max_chars, max_bytes=max_bytes,
                      historical=historical, target_project=target_project, compact=compact,
                      unit_index=unit_index, page=page)
