"""Bounded cross-Run continuation; checkpoints are cursors, not transcript copies.

Reverify consumed prefixes, including their actual I/O cost. When that cannot fit
in the configured budget, report a gap instead of bypassing integrity. The pure
reader's finite history window and event-identity bounds remain explicit.
"""
from __future__ import annotations

from copy import deepcopy

from .core import MemoryError, _digest, _fail
from .dream_sources import read_source

TRANSIENT_GAPS = {'bounded_partial', 'event_exceeds_remaining_budget', 'partial_line'}


def collect(profile, previous=None, *, reconsider=False):
    remaining = profile['budgets']['source_bytes']
    event_budget = profile['budgets']['events']
    collected, processed = {}, {}
    old_specs = {s['id']: s for s in previous['profile_snapshot']['sources']} if previous else {}
    def priority(source):
        old = previous['materials'].get(source['id']) if previous else None
        if old and any(g['reason'] in {'budget_exhausted', 'prefix_verification_budget'} for g in old['coverage'].get('gaps', [])):
            return 0
        return 1 if old and not old['coverage']['complete'] else 2
    for source in sorted(profile['sources'], key=priority):
        sid = source['id']
        old = previous['materials'].get(sid) if previous and old_specs.get(sid) == source and not reconsider else None
        old_processed = previous['processed'] if old else {}
        cursor = None
        if old and source['format'] != 'document' and all(old_processed.get(e['key']) in {'processed', 'excluded', 'no-signal'} for e in old['events']):
            cursor = deepcopy(old.get('cursor'))
        offset = cursor.get('offset', 0) if cursor else 0
        # Prefix verification occurs once before and once after a source batch.
        # Leave one prefix verification available to the publication phase.
        allocation = remaining // 3 - offset
        if allocation < 1 or event_budget < 1:
            collected[sid] = {'source_id': sid, 'events': [], 'version': old.get('version') if old else None,
                              'cursor': cursor, 'coverage': {'complete': False, 'read_bytes': 0, 'verification_bytes': 0,
                              'gaps': [{'reason': 'prefix_verification_budget' if offset else 'budget_exhausted'}]}}
            continue
        try:
            result = read_source(source, max_bytes=min(allocation, 8 * 1024 * 1024),
                                 max_events=event_budget, cursor=cursor, refresh_cutoff=True)
            if source.get('_catalog_page') and (len(result['events']) > event_budget or result['coverage']['read_bytes'] > allocation):
                _fail('source_budget_exhausted', 'Selected page exceeds this Run remaining byte/event budget')
        except MemoryError as exc:
            # Failed reads can consume their reservation; never silently undercount.
            remaining -= min(remaining, 2 * (offset + allocation))
            collected[sid] = {'source_id': sid, 'events': [], 'version': None, 'cursor': cursor,
                              'coverage': {'complete': False, 'gaps': [{'reason': exc.code,
                              'recovery': 'Inspect the allowed owner/path; explicit reconsider preserves all dispositions'}]}}
            continue
        coverage = result['coverage']
        result['snapshot_checked'] = True
        remaining -= coverage['read_bytes'] + coverage['verification_bytes']
        if old and result['version'] == old.get('version') and not result['events']:
            # Keep a small already-reviewed working set available for references.
            # It is not newly discovered evidence and does not trigger a new model.
            result['events'] = deepcopy(old['events'])[:event_budget]
            coverage = {**old['coverage'], 'read_bytes': coverage['read_bytes'],
                        'verification_bytes': coverage['verification_bytes']}
            result['coverage'] = coverage
        if old and cursor:
            prior_gaps = {g['reason'] for g in old['coverage'].get('gaps', []) if g['reason'] not in TRANSIENT_GAPS}
            current_gaps = {g['reason'] for g in coverage['gaps']}
            coverage['gaps'].extend({'reason': g, 'prior_batch': True} for g in sorted(prior_gaps - current_gaps))
            coverage['complete'] = coverage['complete'] and not prior_gaps
            coverage['previously_consumed_bytes'] = offset
        for event in result['events']:
            if len(event['text']) > 4096:
                event['text'] = event['text'][:4096]
                event['excerpt_truncated'] = True
                coverage['complete'] = False
                coverage['gaps'].append({'reason': 'excerpt_truncated', 'event_id': event['event_id']})
            if event['key'] in old_processed:
                processed[event['key']] = old_processed[event['key']]
        event_budget -= len(result['events'])
        collected[sid] = result
    return collected, processed, profile['budgets']['source_bytes'] - remaining


def change_set(engine, run_id, *, max_bytes=12000):
    """Only public, currently permitted frozen excerpts; membership changes are not truth changes."""
    import difflib
    from .core import _json
    if type(max_bytes) is not int or not 512 <= max_bytes <= 12000:
        _fail('invalid_input', 'Change-set budget must be between 512 and 12000 bytes')
    run = engine._run(run_id)
    previous = engine._run(run['previous_run'], check_caller=False) if run.get('previous_run') else None
    current = engine.materials(run_id)['sources']
    authorized = {s['id'] for s in engine._effective(run)['sources']}
    sources = []
    for sid in sorted(set(current) | set(previous['materials'] if previous else {})):
        new = current.get(sid)
        old = previous['materials'].get(sid) if previous else None
        row = {'source_id': sid, 'from_version': old.get('version') if old else None,
               'to_version': new.get('version') if new else None}
        if sid not in authorized or not new or not new.get('version'):
            row['change'] = 'unavailable'
        elif old and new.get('version') == old.get('version'):
            row['change'] = 'unchanged'
        else:
            new_events = new.get('events', [])
            allowed_old = [e for e in (old or {}).get('events', []) if not engine._forbidden_source(run, e)]
            before = '\n'.join(e['text'] for e in allowed_old)
            after = '\n'.join(e['text'] for e in new_events)
            row['change'] = 'added' if old is None else 'appended' if after.startswith(before) else 'modified'
            row['diff'] = ''.join(difflib.unified_diff(before.splitlines(True), after.splitlines(True),
                                                      fromfile='previous-reviewed-excerpt', tofile='current-frozen-excerpt'))[:1600]
            row['excerpt_only'] = True
        sources.append(row)
    before_ns = previous.get('working_basis', {}).get('namespace', {}) if previous else {}
    after_ns = run['basis']['namespace']
    memory_changes = [{'path': path, 'change': 'added' if path not in before_ns else 'unavailable' if path not in after_ns else 'modified'}
                      for path in sorted(set(before_ns) | set(after_ns)) if before_ns.get(path) != after_ns.get(path)]
    result = {'run_id': run_id, 'review_objective': run.get('review_objective'),
              'source_changes': run.get('source_changes', 'unknown'),
              'objective_completion': run.get('objective_completion', 'unknown'),
              'pending_review': sum(v == 'pending-review' for v in run['processed'].values()),
              'unresolved_effects': len(run['unresolved']), 'sources': [], 'memory_changes': [],
              'from_run': previous['id'] if previous else None, 'omitted': 0,
              'notice': 'Source changes and processing coverage do not establish semantic review or scientific support.'}
    for key, items in [('sources', sources), ('memory_changes', memory_changes)]:
        for item in items:
            result[key].append(item)
            if len(_json(result).encode()) > max_bytes:
                result[key].pop(); result['omitted'] += 1
    return result
