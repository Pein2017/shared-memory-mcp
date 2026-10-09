"""Read immutable views as independently qualified narrative units.

Publication still requires exact frozen evidence. Consumption tolerates ordinary
source drift, but checks current grants and canonical lifecycle on both sides of
bounded source I/O. Legacy snapshots use conservative aggregate dependencies.
"""
from __future__ import annotations

from pathlib import Path
import re

from .core import _digest, _fail
from .curation import projected_records, read_json
from .dream_records import collaboration, render_claim
from .dream_sources import check_snapshot
from .narrative import mask_view, view_reference


def _forbidden(store, target, view, claim, sources, evidence_keys=()):
    from .dreaming import dispositions, _source_keys
    keys = set(claim['refs']) | set(evidence_keys)
    for sid, source in sources.items():
        keys.update({'source:' + sid, 'source-uri:' + Path(source['path']).as_uri()})
        keys.update(source['spec'].get('lineage', []))
    keys = _source_keys(keys)
    return any(item['target'] == target and item['scope'] == view and item['topic'] in {'*', claim['topic']} and
               item['kind'] in {'no_reuse', 'user_rejected', 'inference_error'} and
               keys.intersection(_source_keys(item['source_keys'])) for item in dispositions(store)['items'])


def collect_units(engine, view, *, scenario, historical=None, target_project=None, compact=True, verify_sources=True):
    from .dream_views import _base, _navigation, check_snapshot
    policy, profile = engine._policy()
    target = engine._target(profile, target_project)
    if scenario not in profile['scenarios']:
        return {**_navigation(view, 'navigation', 'Select an authorized scenario', available_scenarios=profile['scenarios']), 'units': []}
    base = _base(target, view)
    pointer = read_json(engine.store, base + '/current.json')
    revision = historical or (pointer.get('revision') if pointer else None)
    if revision is None:
        return {**_navigation(view, 'navigation', 'No published view; use scoped context/search'), 'units': []}
    if not isinstance(revision, str) or not re.fullmatch('[0-9a-f]{64}', revision):
        _fail('invalid_input', 'A historical view requires an exact revision')
    document = read_json(engine.store, base + f'/revisions/{revision}.json')
    if not document or _digest(document) != revision or document.get('target') != target or document.get('view') != view:
        return {**_navigation(view, 'unverifiable', 'Immutable view identity is unverifiable', revision), 'units': []}
    if 'read_policy_revision' not in document and document['policy_revision'] != _digest(policy):
        return {**_navigation(view, 'invalidated', 'Legacy authority must be explicitly revalidated before migration', revision), 'units': []}
    bindings = document.get('unit_bindings')
    if bindings is None:
        # Exact original pointers, never guessed semantic boundaries for legacy text.
        bindings = [{'sources': sorted(document['sources']), 'dependencies': sorted(document['dependencies'])}
                    for _ in document['claims']]
    if len(bindings) != len(document['claims']):
        _fail('corrupt_view', 'Unit/dependency cardinality mismatch')
    source_states, readable_sources = {}, set()
    for claim, binding in zip(document['claims'], bindings):
        sources = {sid: document['sources'][sid] for sid in binding['sources']}
        if target in claim['projects'] and scenario in claim['scenarios'] and not _forbidden(engine.store, target, view, claim, sources, binding.get('evidence_keys', [])):
            readable_sources.update(sources)
    for sid, source in document['sources'].items():
        spec = source.get('spec')
        if sid not in readable_sources or not spec or not engine._catalog(profile).authorized(spec):
            source_states[sid] = 'forbidden'
        elif source['format'] == 'pi' and source.get('ancestry_verified') is not True:
            source_states[sid] = 'unproven'
        else:
            source_states[sid] = check_snapshot(spec, source['version']) if verify_sources else 'not-rechecked'
    with engine.store._gate():
        current_policy, current_profile = engine._policy()
        engine._target(current_profile, target)
        if scenario not in current_profile['scenarios']:
            return {**_navigation(view, 'invalidated', 'Scenario access changed during source check', revision), 'units': []}
        records = {r['id']: r for r in projected_records(engine.store, target)}
        collab = {r['id']: r for r in collaboration(engine.store)}
        masked = mask_view(engine.store, target, view, revision, document['claims'], list(records.values()), document.get('qualifier'))
        result = {'view': view, 'revision': revision, 'as_of': document['as_of'], 'coverage': document['coverage'],
                  'current_state_verified': False, 'units': [], 'unavailable_units': [], 'replaced_units': masked,
                  'status': 'historical' if historical else 'valid'}
        for index, (claim, binding) in enumerate(zip(document['claims'], bindings)):
            if target not in claim['projects'] or scenario not in claim['scenarios'] or index in masked:
                continue
            source_ids = binding['sources']
            if any(sid not in document['sources'] for sid in source_ids):
                _fail('corrupt_view', 'A narrative unit has an unknown source binding')
            sources = {sid: document['sources'][sid] for sid in source_ids}
            forbidden = _forbidden(engine.store, target, view, claim, sources, binding.get('evidence_keys', []))
            unavailable = forbidden or any(source_states[sid] in {'forbidden', 'unproven'} or
                not engine._catalog(current_profile).authorized(s['spec']) for sid, s in sources.items())
            changed = any(source_states[sid] != 'valid' for sid in sources)
            for ref in binding['dependencies']:
                dependency = document['dependencies'].get(ref)
                if dependency is None:
                    _fail('corrupt_view', 'A narrative unit has an unknown canonical dependency')
                record = (records if dependency['type'] == 'record' else collab).get(dependency['id'])
                from .dreaming import record_use_filter
                shaped = record if dependency['type'] == 'record' else {
                    'project_id': target, 'title': record['claim']['topic'] if record else claim['topic'],
                    'sources': (record or {}).get('sources', []), 'kind': 'decision'}
                if record and not record_use_filter(engine.store, scope=view)(shaped):
                    unavailable = True
                if not record or record['effective_status'] != 'active':
                    unavailable = True
                elif _digest(record) != dependency['revision']:
                    changed = True
                if dependency['type'] == 'collaboration' and record:
                    unavailable |= target not in set(current_policy['collaboration_projects']).intersection(record['claim']['projects'])
            if view == 'collaboration':
                unavailable |= target not in current_policy['collaboration_projects']
                unavailable |= claim['level'] == 'inferred' and not current_profile['allow_inferred']
            reference = view_reference(view, revision, index)
            if unavailable:
                result['unavailable_units'].append({'index': index, 'reason': 'access-or-lifecycle-unavailable'})
                continue
            narrative = claim.get('narrative', {})
            freshness = 'not-rechecked' if not verify_sources else 'needs-check' if changed else 'as-of'
            result['units'].append({'id': reference, 'unit_id': narrative.get('id', reference),
                'role': narrative.get('role', 'background'), 'index': index,
                'level': claim['level'], 'text': render_claim(claim, compact=compact),
                'as_of': document['as_of'], 'freshness': freshness,
                'conditions': claim['conditions'], 'task_modes': claim.get('task_modes', []),
                'read_hint': {'view': view, 'historical': revision, 'unit_index': index, 'scenario': scenario},
                'sources': [{'path': source['path'], 'status': source_states[sid]} for sid, source in sources.items()]})
        if not result['units']:
            result['status'] = ('unverifiable' if any(v == 'unproven' for v in source_states.values()) else
                                'invalidated' if result['unavailable_units'] else 'navigation')
            result['available_scenarios'] = sorted({s for c in document['claims'] if target in c['projects']
                                                    for s in c['scenarios'] if s in current_profile['scenarios']})
        elif not historical and any(u['freshness'] == 'needs-check' for u in result['units']):
            result['status'] = 'stale'
        result['freshness'] = 'needs-check' if result['status'] == 'stale' else 'as-of'
        return result


def read_view(engine, view, *, scenario, max_chars=None, max_bytes=None, historical=None, target_project=None, compact=True,
              unit_index=None, page=None):
    from .context_packet import exposure_size
    char_cap = 8000 if max_chars is None else max_chars
    byte_cap = 8000 if max_bytes is None else min(max_bytes, 8000)
    if type(char_cap) is not int or type(byte_cap) is not int or char_cap < 0 or byte_cap < 0:
        _fail('invalid_input', 'View caps must be nonnegative integers')
    collected = collect_units(engine, view, scenario=scenario, historical=historical,
                              target_project=target_project, compact=compact)
    candidates = collected.pop('units')
    if unit_index is not None or page is not None:
        if type(unit_index) is not int or unit_index < 0:
            _fail('invalid_input', 'Detail continuation requires an explicit nonnegative unit_index')
        from .projection import bounded_read
        selected = [{**u, 'current_state_verified': False} for u in candidates if u['index'] == unit_index]
        if not selected:
            _fail('detail_unavailable', 'The exact narrative unit is no longer eligible in this scope')
        scope = engine.store._resolve(engine.caller)
        return bounded_read({'status': 'ok', 'scope': scope, 'collection': 'overview', 'items': selected},
                            max_bytes=byte_cap, page=page)
    result = {**collected, 'text': '', 'items': [], 'omitted_claims': 0, 'chars': 0, 'bytes': 0,
              'tokens': None, 'token_accounting': 'unavailable',
              'notice': 'Dated source-linked understanding, not current verification or execution authority.'}
    for unit in candidates:
        text = '\n\n'.join(filter(None, [result['text'], unit['text']]))
        item = {k: v for k, v in unit.items() if k not in {'text', 'conditions'}}
        trial = {**result, 'text': text, 'items': result['items'] + [item],
                 'chars': len(text), 'bytes': len(text.encode())}
        if len(text) <= char_cap and exposure_size(trial) <= byte_cap:
            result = trial
        else:
            result['omitted_claims'] += 1
    if candidates and not result['text']:
        result['status'] = 'budget-limited'
        result['navigation'] = 'Select a smaller reviewed rendition or explicitly read this view unit.'
        result['continuation'] = candidates[0]['read_hint']
    if exposure_size(result) > byte_cap:
        result = {'status': 'budget-limited', 'view': view, 'text': '', 'chars': 0, 'bytes': 0,
                  'navigation': 'The requested cap cannot hold the required scope and view envelope.'}
    return result
