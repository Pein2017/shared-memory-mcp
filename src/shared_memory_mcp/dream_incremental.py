"""Bounded cross-Run continuation; checkpoints are cursors, not transcript copies.

Reverify consumed prefixes, including their actual I/O cost. When that cannot fit
in the configured budget, report a gap instead of bypassing integrity. The pure
reader's finite history window and event-identity bounds remain explicit.
"""
from __future__ import annotations

from copy import deepcopy
import os
import re
import time

from .core import MAX_RECORD_BYTES, MAX_RECORDS, MemoryError, _digest, _fail, _json
from .dream_sources import read_source
from .curation import read_json, safe_path

TRANSIENT_GAPS = {'bounded_partial', 'event_exceeds_remaining_budget', 'partial_line'}
# Gaps that bounded continuation, reading or a larger page can still resolve; they cannot be accepted.
UNACCEPTABLE_GAPS = TRANSIENT_GAPS | {'excerpt_truncated', 'unreviewed_range', 'source_budget_exhausted'}
REVIEWED = {'processed', 'excluded', 'no-signal'}
# An accepted permanent gap ends pending work without being reviewed content.
DONE = REVIEWED | {'gap-accepted'}
DEFAULT_OBJECTIVE = {'id': 'default-maintenance-v2',
                     'question': 'Maintain this target memory: triage candidates and stale candidates, '
                                 'duplicate titles, missing sources, expired actives and open issues.'}
STALE_DAYS = 7
# Root discovery only inventories sessions written within this window; explicit sources still reach older files.
HISTORY_WINDOW_DAYS = 30


def _in_scope(progress, kind, key):
    scope = progress.get('scope')
    return scope is None or key in scope[kind]


def _objective_bound(progress):
    if len(progress['sources']) + len(progress['memory']) > MAX_RECORDS:
        _fail('dream_limit', 'Objective inventory exceeds the supported record bound; nothing was omitted')
    for kind in ('sources', 'memory'):
        for key, entry in progress[kind].items():
            _objective_entry_bound(key, entry)
    return progress


def _objective_entry_bound(key, entry):
    if len(_json({'version': 1, 'kind': 'sources', 'entries': [[key, entry]]}).encode()) + 1 > MAX_RECORD_BYTES:
        _fail('dream_limit', 'Individual objective entry exceeds the checkpoint file bound')


def _objective_document(store, document):
    digest = _digest(document)
    path = safe_path(store, f'dreaming/checkpoints/objectives/{digest}.json')
    data = (_json(document) + '\n').encode()
    if len(data) > MAX_RECORD_BYTES:
        _fail('dream_limit', 'Objective checkpoint file exceeds its supported byte bound')
    if path.exists():
        if read_json(store, path.relative_to(store.root)) != document:
            _fail('corrupt_objective', 'Immutable objective checkpoint has changed')
    else:
        store._publish(path, data)
    return digest


def save_objective(store, progress):
    """Save immutable metadata shards; caller holds the existing writer gate."""
    _objective_bound(progress)
    shards = []
    for kind in ('sources', 'memory'):
        entries = []
        encoded_bytes = len(_json({'version': 1, 'kind': kind, 'entries': []}).encode()) + 1
        for key, entry in progress[kind].items():
            item_bytes = len(_json([key, entry]).encode()) + bool(entries)
            if entries and (len(entries) == 128 or encoded_bytes + item_bytes > MAX_RECORD_BYTES):
                document = {'version': 1, 'kind': kind, 'entries': entries}
                shards.append({'kind': kind, 'digest': _objective_document(store, document), 'count': len(entries)})
                entries = []
                encoded_bytes = len(_json({'version': 1, 'kind': kind, 'entries': []}).encode()) + 1
                item_bytes = len(_json([key, entry]).encode())
            entries.append([key, entry])
            encoded_bytes += item_bytes
        if entries:
            document = {'version': 1, 'kind': kind, 'entries': entries}
            shards.append({'kind': kind, 'digest': _objective_document(store, document), 'count': len(entries)})
    manifest = {'version': 1, 'header': {k: v for k, v in progress.items() if k not in {'sources', 'memory'}},
                'shards': shards, 'counts': {kind: len(progress[kind]) for kind in ('sources', 'memory')}}
    return {'version': 1, 'manifest': _objective_document(store, manifest)}


def _load_objective_document(store, digest):
    if not isinstance(digest, str) or not re.fullmatch('[0-9a-f]{64}', digest):
        _fail('corrupt_objective', 'Objective checkpoint needs an exact content-addressed locator')
    document = read_json(store, f'dreaming/checkpoints/objectives/{digest}.json')
    if document is None or _digest(document) != digest:
        _fail('corrupt_objective', 'Objective checkpoint is missing or changed')
    return document


def load_objective(store, descriptor):
    """Reassemble exact metadata; missing or changed shards never imply progress."""
    if not isinstance(descriptor, dict) or set(descriptor) != {'version', 'manifest'} or descriptor['version'] != 1:
        _fail('corrupt_objective', 'Unsupported objective checkpoint descriptor')
    manifest = _load_objective_document(store, descriptor['manifest'])
    try:
        if (set(manifest) != {'version', 'header', 'shards', 'counts'} or manifest['version'] != 1 or
                not isinstance(manifest['header'], dict) or
                {'sources', 'memory'} & manifest['header'].keys() or
                set(manifest['counts']) != {'sources', 'memory'} or
                any(type(n) is not int or n < 0 for n in manifest['counts'].values()) or
                sum(manifest['counts'].values()) > MAX_RECORDS or
                not isinstance(manifest['shards'], list) or len(manifest['shards']) > MAX_RECORDS):
            _fail('corrupt_objective', 'Invalid objective checkpoint manifest')
        progress = {**manifest['header'], 'sources': {}, 'memory': {}}
        for locator in manifest['shards']:
            if (set(locator) != {'kind', 'digest', 'count'} or locator['kind'] not in {'sources', 'memory'} or
                    type(locator['count']) is not int or not 1 <= locator['count'] <= 128):
                _fail('corrupt_objective', 'Invalid objective shard locator')
            shard = _load_objective_document(store, locator['digest'])
            if (set(shard) != {'version', 'kind', 'entries'} or shard['version'] != 1 or
                    shard['kind'] != locator['kind'] or not isinstance(shard['entries'], list) or
                    len(shard['entries']) != locator['count']):
                _fail('corrupt_objective', 'Invalid objective checkpoint shard')
            for key, entry in shard['entries']:
                if not isinstance(key, str) or not isinstance(entry, dict) or key in progress[locator['kind']]:
                    _fail('corrupt_objective', 'Invalid or duplicate objective entry')
                progress[locator['kind']][key] = entry
        if any(len(progress[kind]) != manifest['counts'][kind] for kind in ('sources', 'memory')):
            _fail('corrupt_objective', 'Objective shard inventory is incomplete')
        return _objective_bound(progress)
    except (KeyError, TypeError, ValueError):
        _fail('corrupt_objective', 'Malformed objective checkpoint')


def objective_inventory(catalog, objective, *, previous=None, selections=None, memory_refs=(), binding=None):
    """Freeze navigation, never review it. Caller owns persistence under the Run gate."""
    if previous:
        if previous['review_objective'] != objective or previous.get('binding') != binding:
            _fail('objective_conflict', 'Objective checkpoint belongs to another question or binding')
        progress = deepcopy(previous)
    else:
        progress = {'version': 1, 'review_objective': deepcopy(objective), 'binding': deepcopy(binding),
                    'sources': {}, 'memory': {}, 'linked_runs': [], 'gaps': [], 'inventory_complete': True}
    discovered = []
    if selections is None and (not previous or not progress['inventory_complete']):
        progress['gaps'] = []
        progress['inventory_complete'] = True
        roots = []
        # Full native roots precede overlapping grants so the inherited locator
        # remains stable when navigation grants are later enlarged.
        for root in catalog.profile.get('history_roots', []):
            roots.append((root['path'], root, True))
        for grant in catalog.grants:
            if grant['kind'] == 'file':
                discovered.append({'grant_id': grant['id']})
            elif grant['format'] in {'pi', 'codex', 'claude'}:
                roots.append((grant['id'], grant, False))
        seen = set()  # grants overlapping a root list the same files; count each once
        horizon, excluded = time.time() - HISTORY_WINDOW_DAYS * 86400, 0
        for locator, root, inherited in roots:
            directories = ['']
            while directories:
                relative, cursor = directories.pop(), None
                while True:
                    try:
                        page = catalog.list(locator, relative_dir=relative, cursor=cursor, limit=100)
                    except (MemoryError, OSError) as exc:
                        progress['gaps'].append({'reason': getattr(exc, 'code', 'source_unavailable'),
                                                 'root': locator, 'relative_dir': relative})
                        progress['inventory_complete'] = False
                        break
                    for item in page['items']:
                        if item['kind'] == 'directory':
                            directories.append(item['path'])
                        elif item['path'].endswith('.jsonl'):
                            physical = os.path.realpath(item['absolute_path'] if inherited
                                                        else os.path.join(root['path'], item['path']))
                            if physical in seen:
                                continue
                            seen.add(physical)
                            try:
                                if os.stat(physical).st_mtime < horizon:
                                    excluded += 1
                                    continue
                            except OSError:
                                pass  # Unreadable files stay in the inventory and surface as gaps.
                            discovered.append(({'absolute_path': item['absolute_path'],
                                **{k: root[k] for k in ('format', 'schema', 'native_version', 'native_versions') if k in root}}
                                if inherited else {'grant_id': locator, 'path': item['path']}))
                        if len(discovered) + len(directories) > MAX_RECORDS:
                            _fail('dream_limit', 'Historical navigation exceeds the supported inventory bound')
                    cursor = page['next_cursor']
                    if cursor is None:
                        break
        progress['history_window'] = {'days': HISTORY_WINDOW_DAYS, 'excluded': excluded}
        # Prefer roots over exact grants for physical duplicates.
        discovered.sort(key=lambda item: 'absolute_path' not in item)
    elif selections is not None:
        if not isinstance(selections, list) or len(selections) > 16:
            _fail('source_limit', 'Expand an objective through at most sixteen selectors per batch')
        discovered = selections
    paths = {entry['path']: sid for sid, entry in progress['sources'].items()}
    for selection in discovered:
        spec = catalog.resolve([selection])[0]
        path = spec['path']
        if path in paths:
            continue
        try:
            frozen = catalog.freeze(selection)
            entry = {'selection': frozen['selection'], 'path': path, 'cutoff': frozen['selection']['cutoff'],
                     'identity': frozen['identity'], 'deferred_bytes': frozen['deferred_bytes'],
                     'epoch': frozen.get('epoch'),
                     'reviewed_offset': 0, 'cursor': None, 'pending_page': None, 'status': 'pending', 'gaps': []}
        except (MemoryError, OSError) as exc:
            entry = {'selection': deepcopy(selection), 'path': path, 'cutoff': None, 'identity': None,
                     'reviewed_offset': 0, 'cursor': None, 'pending_page': None, 'status': 'pending',
                     'gaps': [{'reason': getattr(exc, 'code', 'source_unavailable')}]}
        progress['sources'][spec['id']] = entry
        paths[path] = spec['id']
        if len(progress['sources']) + len(progress['memory']) > MAX_RECORDS:
            _fail('dream_limit', 'Objective inventory exceeds the supported record bound; nothing was omitted')
        _objective_entry_bound(spec['id'], entry)
    for item in memory_refs:
        ref, revision = item['ref'], item['revision']
        old = progress['memory'].get(ref)
        if old and old['revision'] != revision:
            _fail('objective_conflict', 'Changed memory revision belongs to a subsequent increment')
        progress['memory'].setdefault(ref, {'revision': revision, 'status': 'pending'})
    return _objective_bound(progress)


def objective_batch(catalog, progress, budgets):
    """Stage bounded public pages. Only durable close advances their reviewed cursor."""
    progress = deepcopy(progress)
    selected, remaining, events_left = [], budgets['source_bytes'], budgets['events']
    progress['batch_read_bytes'] = 0
    for sid, entry in progress['sources'].items():
        if entry['status'] in DONE or not _in_scope(progress, 'sources', sid):
            continue
        if len(selected) == 16 or events_left < 1 or remaining < 1:
            break
        try:
            if entry['pending_page']:
                if len(entry['pending_page']['event_keys']) > events_left:
                    continue
                catalog.resolve([entry['pending_page']['selection']])
                selected.append(deepcopy(entry['pending_page']['selection']))
                events_left -= len(entry['pending_page']['event_keys'])
                continue
            if entry['cutoff'] is None:
                frozen = catalog.freeze(entry['selection'])
                entry.update(selection=frozen['selection'], cutoff=frozen['selection']['cutoff'],
                             identity=frozen['identity'], deferred_bytes=frozen['deferred_bytes'], epoch=frozen.get('epoch'))
            selection = {k: v for k, v in entry['selection'].items() if k != 'page'}
            allocation = min(remaining // 4, 8 * 1024 * 1024)
            page = catalog.read(selection, cursor=entry['cursor'], max_bytes=max(65537, allocation),
                                max_events=min(events_left, 1024))
            cost = page['coverage']['read_bytes'] + page['coverage']['verification_bytes']
            progress['batch_read_bytes'] += cost
            # Verification re-hashes the page and its prefix, so it is charged to the batch total, not the page allocation.
            over, remaining = cost > remaining, remaining - cost
            # Keep room for the retained Run collection and publication checks.
            if over or page['coverage']['read_bytes'] > allocation:
                entry['gaps'] = [{'reason': 'source_budget_exhausted'}]
                continue
            entry['pending_page'] = {'selection': page['selection'], 'next_cursor': page['next_cursor'],
                'tail_cursor': page.get('tail_cursor'),
                'version': page['version'], 'coverage': page['coverage'],
                'event_keys': [event['key'] for event in page['events']]}
            entry['gaps'] = deepcopy(page['coverage']['gaps'])
            selected.append(deepcopy(page['selection']))
            events_left -= len(page['events'])
        except (MemoryError, OSError) as exc:
            entry['gaps'] = [{'reason': getattr(exc, 'code', 'source_unavailable')}]
            if entry.get('appended'):
                # The suffix continuation is gone or the reviewed prefix changed: re-review from the start.
                entry.update(reviewed_offset=0, cursor=None, appended=False)
    return _objective_bound(progress), selected


def objective_close(progress, run):
    """Fold only a durable, reconciled Run; replaying its index write is harmless."""
    if run['phase'] != 'closed' or not run.get('checkpoint') or run.get('unresolved'):
        _fail('pending_objective', 'Only durable reconciled close can advance objective review')
    if run.get('review_objective') != progress['review_objective']:
        _fail('objective_conflict', 'Run belongs to another review objective')
    if run['id'] in progress['linked_runs']:
        return deepcopy(progress)
    progress = deepcopy(progress)
    accepted = run.get('accepted_gaps', {})
    for sid, material in run['materials'].items():
        entry = progress['sources'].get(sid)
        page = entry.get('pending_page') if entry else None
        if not page or material['version'] != page['version']:
            _fail('stale_objective_page', 'Closed Run does not match its staged objective page')
        version = page['version']
        # Gaps accepted now, or earlier for this exact range (an explicit re-read), are not re-staged.
        reasons = {g['reason'] for g in accepted.get(sid, [])} | {
            g['reason'] for g in entry.get('accepted_gaps', [])
            if g.get('end') is not None and g['start'] <= version['start'] and version['consumed'] <= g['end']}
        keys = page['event_keys'] or ([] if reasons else ['source:' + sid])
        if not all(run['processed'].get(key) in REVIEWED for key in keys):
            continue
        def recovered_excerpt(gap):
            if gap['reason'] != 'excerpt_truncated' or not gap.get('event_id'):
                return False
            for event in material['events']:
                if event.get('event_id') != gap['event_id']:
                    continue
                receipt = run.get('material_reads', {}).get(event['key'], {})
                return (receipt.get('complete') is True and type(receipt.get('end')) is int and
                        receipt['end'] >= len(event.get('text', '')) and
                        isinstance(receipt.get('text_sha256'), str) and
                        re.fullmatch('[0-9a-f]{64}', receipt['text_sha256']) is not None)
            return False
        gaps = [gap for gap in material['coverage'].get('gaps', [])
                if gap['reason'] != 'bounded_partial' and not recovered_excerpt(gap) and gap['reason'] not in reasons]
        entry['gaps'] = deepcopy(gaps)
        # Missing/truncated bodies cannot be skipped by marking their excerpt.
        if gaps:
            continue
        if version['start'] != entry['reviewed_offset']:
            entry['gaps'] = [{'reason': 'unreviewed_range', 'next_offset': entry['reviewed_offset']}]
            continue
        entry.setdefault('accepted_gaps', []).extend(
            {**gap, 'run_id': run['id'], 'start': version['start'], 'end': version['consumed']} for gap in accepted.get(sid, []))
        entry['reviewed_offset'] = version['consumed']
        entry['cursor'] = page['next_cursor']
        entry['tail_cursor'] = page.get('tail_cursor')
        entry['appended'] = False
        entry['pending_page'] = None
        if entry['reviewed_offset'] == entry['cutoff']:
            entry['status'] = 'processed'
    for sid, gaps in accepted.items():
        entry = progress['sources'].get(sid)
        if sid not in run['materials'] and entry and not entry.get('pending_page'):
            # An unstageable source (for example a removed file) is closed as a whole-source gap.
            entry.setdefault('accepted_gaps', []).extend(
                {**gap, 'run_id': run['id'], 'start': entry['reviewed_offset'], 'end': entry.get('cutoff')} for gap in gaps)
            entry.update(status='gap-accepted', gaps=[])
    for ref, entry in progress['memory'].items():
        supplied = run.get('memory_inputs', {}).get(ref, {})
        if supplied.get('revision') == entry['revision'] and run['processed'].get(ref) in REVIEWED:
            entry['status'] = run['processed'][ref]
    progress['linked_runs'].append(run['id'])
    return _objective_bound(progress)


def objective_observe(progress):
    """Bounded navigation; reviewable-complete never asserts semantic completion."""
    sources = [(sid, entry) for sid, entry in progress['sources'].items() if _in_scope(progress, 'sources', sid)]
    memory = [(ref, entry) for ref, entry in progress['memory'].items() if _in_scope(progress, 'memory', ref)]
    pending = [(sid, entry) for sid, entry in sources if entry['status'] not in DONE]
    memory_pending = sum(entry['status'] not in REVIEWED for _, entry in memory)
    gaps = [{**gap, 'source_id': sid} for sid, entry in pending for gap in entry['gaps']]
    gaps = deepcopy(progress['gaps']) + gaps
    # Positions are target-keyed: report what earlier objectives already reviewed or accepted.
    reviewed = [{'source_id': sid, 'reviewed_offset': entry['reviewed_offset'], 'cutoff': entry.get('cutoff'),
                 'status': entry['status']} for sid, entry in progress['sources'].items() if entry['reviewed_offset'] or entry['status'] in DONE]
    accepted = [{**gap, 'source_id': sid} for sid, entry in progress['sources'].items() for gap in entry.get('accepted_gaps', [])]
    return {'objective_completion': 'pending' if pending or memory_pending or gaps or not progress['inventory_complete'] else 'reviewable-complete',
            'remaining_sources': len(pending), 'remaining_memory': memory_pending,
            'pending_pages': sum(bool(entry['pending_page']) for _, entry in pending),
            'ready_selections': [deepcopy((entry['pending_page'] or {}).get('selection', entry['selection']))
                                 for _, entry in pending[:16]],
            'ready_memory': [{'ref': ref, 'revision': entry['revision']}
                             for ref, entry in memory if entry['status'] not in REVIEWED][:16],
            'gaps': gaps[:16], 'omitted_gaps': max(0, len(gaps) - 16),
            'reviewed_sources': reviewed[:16], 'omitted_reviewed_sources': max(0, len(reviewed) - 16),
            'accepted_gaps': accepted[:16], 'omitted_accepted_gaps': max(0, len(accepted) - 16),
            'linked_runs': len(progress['linked_runs']), 'inventory_complete': progress['inventory_complete'],
            'history_window': progress.get('history_window')}


def rebase(progress, objective, *, scope=None):
    """Carry target-keyed reviewed positions to another objective; semantic completion does not transfer."""
    progress = deepcopy(progress)
    progress.update(review_objective=deepcopy(objective), linked_runs=[], gaps=[], target_keyed=True, scope=scope)
    for entry in progress['sources'].values():
        if entry['status'] not in DONE:
            entry['gaps'] = []
    return progress


def merge_positions(progresses):
    """Conservative union of objective-keyed checkpoints: the minimum reviewed position wins."""
    merged = deepcopy(progresses[0])
    for other in progresses[1:]:
        for sid, entry in other['sources'].items():
            mine = merged['sources'].get(sid)
            if (mine is None or entry['reviewed_offset'] < mine['reviewed_offset'] or
                    mine['status'] in DONE and entry['status'] not in DONE):
                merged['sources'][sid] = deepcopy(entry)
        for ref, entry in other['memory'].items():
            mine = merged['memory'].get(ref)
            if mine is None:
                merged['memory'][ref] = deepcopy(entry)
            elif mine != entry:
                merged['memory'][ref] = {'revision': mine['revision'], 'status': 'pending'}
    merged['inventory_complete'] = False
    return _objective_bound(merged)


def apply_reread(progress, reread):
    """Explicit re-review: a named source returns to pending from its start (never advances)."""
    for item in reread:
        entry = progress['sources'].get(item['source_id'])
        if entry is None:
            _fail('invalid_objective', f"reread names `{item['source_id']}`, which is not a source of this target")
        if entry['reviewed_offset'] > item['range'][0] or entry['status'] in DONE:
            # shortcut: catalog pages cannot seek, so re-review restarts at byte 0, not at range start.
            entry.update(reviewed_offset=0, cursor=None, pending_page=None, status='pending', gaps=[],
                         reread=list(item['range']))
    return progress


def default_inventory(store, target, memory, *, limit=64):
    """Default objective deliverable, in order: candidates by age, duplicate titles, missing file
    sources, expired actives and open issues. Reads no native history. Self-review is a card label only."""
    from datetime import datetime, timezone
    from pathlib import Path
    from urllib.parse import unquote, urlparse
    from .core import _utc
    from .curation import projected_records
    now = datetime.now(timezone.utc)
    records = projected_records(store, target)
    def last_operation(record):
        return max(_utc(t) for t in [record['created_at'], record.get('review', {}).get('reviewed_at', record['created_at'])])
    def pending(record):
        prior = memory.get('record:' + record['id'], {})
        return not (prior.get('status') in REVIEWED and prior.get('revision') == _digest(record))
    def row(record, reason, **extra):
        return {'ref': 'record:' + record['id'], 'reason': reason, 'title': record['title'][:200],
                'age_days': round((now - last_operation(record)).total_seconds() / 86400, 1),
                'pending': pending(record), **extra}
    items = [row(r, 'stale-candidate' if (now - last_operation(r)).days >= STALE_DAYS else 'candidate')
             for r in sorted((r for r in records if r['effective_status'] == 'candidate'), key=last_operation)]
    live = [r for r in records if r['effective_status'] in {'active', 'candidate'}]
    titles = {}
    for r in live:
        titles.setdefault(' '.join(r['title'].casefold().split()), []).append(r)
    for group in titles.values():
        if len(group) > 1:
            items.extend(row(r, 'duplicate-title', duplicates=['record:' + x['id'] for x in group if x is not r]) for r in group)
    for r in live:
        missing = [s['uri'] for s in r['sources'] if urlparse(s['uri']).scheme == 'file' and
                   not Path(unquote(urlparse(s['uri']).path)).exists()]
        if missing:
            items.append(row(r, 'missing-source', missing=missing[:4]))
    items.extend(row(r, 'expired-active') for r in records if r['status'] == 'active' and r['effective_status'] == 'expired')
    issues = []
    for path in sorted(safe_path(store, 'dreaming/issues').glob('*.json'))[:2048]:
        issue = read_json(store, path.relative_to(store.root))
        if isinstance(issue, dict) and issue.get('target') == target and issue.get('disposition', 'pending') == 'pending':
            issues.append({'issue': issue.get('id'), 'reason': 'open-issue', 'topic': str(issue.get('topic', ''))[:200]})
    refs = list(dict.fromkeys(item['ref'] for item in items if item['pending']))
    listed = (items + issues)[:limit]
    return {'items': listed, 'omitted': len(items) + len(issues) - len(listed), 'refs': refs}


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
            if 'text' in event:  # Reused events of a closed Run keep only their recorded length.
                event['text_chars'] = len(event['text'])
            if len(event.get('text', '')) > 4096:
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
    current = engine._admitted(run, engine._policy()[1])[1]  # Observation serves nothing to the attempt.
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
            if any('text' not in e for e in allowed_old):
                # A closed Run keeps identities, not text: show only material outside its frozen keys.
                known = {e['key'] for e in allowed_old}
                before, after = '', '\n'.join(e.get('text', '') for e in new_events if e['key'] not in known)
                row.update(change='changed', previous_text_retained=False)
            else:
                before = '\n'.join(e['text'] for e in allowed_old)
                after = '\n'.join(e.get('text', '') for e in new_events)
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
    if run.get('objective_progress'):
        summary = objective_observe(engine._progress(run))
        result['objective_progress'] = {**summary, 'ready_selections': [], 'ready_memory': [], 'gaps': [],
                                        'reviewed_sources': [], 'accepted_gaps': []}
        if len(_json(result).encode()) > max_bytes:
            result.pop('objective_progress')
            result['omitted'] += 1
        else:
            for key in ('ready_selections', 'ready_memory', 'gaps', 'reviewed_sources', 'accepted_gaps'):
                for item in summary[key]:
                    result['objective_progress'][key].append(item)
                    if len(_json(result).encode()) > max_bytes:
                        result['objective_progress'][key].pop()
                        result['omitted'] += 1
    for key, items in [('sources', sources), ('memory_changes', memory_changes)]:
        for item in items:
            result[key].append(item)
            if len(_json(result).encode()) > max_bytes:
                result[key].pop(); result['omitted'] += 1
    return result
