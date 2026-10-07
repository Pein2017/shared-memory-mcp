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
        if old and source['format'] != 'document' and all(e['key'] in old_processed for e in old['events']):
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
