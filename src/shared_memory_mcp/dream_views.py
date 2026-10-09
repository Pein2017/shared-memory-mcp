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


def _read_policy_revision(policy, profile, document):
    scenarios = {s for claim in document['claims'] for s in claim['scenarios']}
    grant_ids = {source['spec']['_grant_id'] for source in document['sources'].values()}
    collab = document['view'] == 'collaboration' or any(
        d['type'] == 'collaboration' for d in document['dependencies'].values())
    inferred = collab and any(c.get('level') == 'inferred'
                             for c in [*document['claims'], *document['dependencies'].values()])
    projects = {p for claim in document['claims'] for p in claim['projects']} if collab else set()
    return _digest({'version': policy['version'], 'subject': policy['subject'],
                    'target_allowed': document['target'] in profile['target_projects'],
                    'scenarios': sorted(scenarios.intersection(profile['scenarios'])),
                    'grants': {g['id']: g for g in profile['source_grants'] if g['id'] in grant_ids},
                    'collaboration_projects': sorted(projects.intersection(policy['collaboration_projects'])),
                    'allow_inferred': profile['allow_inferred'] if inferred else None})


def _policy_matches(document, policy, profile):
    if 'read_policy_revision' not in document:
        return document['policy_revision'] == _digest(policy)
    return document['read_policy_revision'] == _read_policy_revision(policy, profile, document)


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
    events, dependencies, unit_bindings = {}, {}, []
    unit_ids = [claim.get('narrative', {}).get('id') for claim in operation['claims']]
    named = [identifier for identifier in unit_ids if identifier is not None]
    if len(named) != len(set(named)):
        _fail('duplicate_unit', 'Stable narrative identities must be unique inside one scoped view')
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
        unit_bindings.append({'sources': sorted({e['source_id'] for e in claim_events.values()}),
                              'dependencies': sorted(claim_deps), 'claim_digest': _digest(claim),
                              'evidence_keys': sorted({key for e in claim_events.values() for key in [e['key'], *e.get('lineage', [])]})})
    specs = {s['id']: s for s in profile['sources']}
    source_ids = sorted({e['source_id'] for e in events.values()})
    document = {'version': 1, 'target': run['target'], 'view': view, 'claims': operation['claims'],
                'unit_bindings': unit_bindings, 'qualifier': {'scope': 'project'},
                'dependencies': {k: {a: b for a, b in v.items() if a != 'claim'} for k, v in dependencies.items()},
                'sources': {sid: {'path': specs[sid]['path'], 'format': specs[sid]['format'],
                                  'version': run['materials'][sid]['version'], 'spec': compact_source_spec(specs[sid])} for sid in source_ids},
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
