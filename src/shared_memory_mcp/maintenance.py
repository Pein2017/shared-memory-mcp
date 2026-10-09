"""Ordinary collection maintenance over the canonical stores and one writer gate.

History reuses the project record lifecycle with explicit episode ownership.
Collaboration reuses its existing v2 lifecycle journal; it is not a new store.
No method starts a DreamRun, classifies a task, launches a model, or expands grants.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re
import uuid

from .core import MemoryStore, MemoryError, _digest, _fail, _json, _keys, _nonempty, _sources, _now, RECORD_ID
from .curation import safe_path, validate_review as ordinary_review
from .dream_records import (collaboration, collaboration_effect, validate_claim, reviewed,
                            render_claim, parse_markdown, markdown)
from .narrative import live_review, live_source


def select_collection(store, name):
    if name not in {'project', 'collaboration', 'history'}:
        _fail('invalid_collection', 'Select project, collaboration or history explicitly')
    if name == getattr(store, 'collection', 'project'):
        return store
    if name == 'project':
        return MemoryStore(store.root)
    return HistoryStore(store.root) if name == 'history' else CollaborationStore(MemoryStore(store.root))


def validate_episode(episode, sources):
    required = {'harness', 'session_id', 'cwd', 'project_id', 'branch', 'task_modes',
                'task_state', 'ranges', 'review_scope', 'coverage_refs', 'gaps'}
    _keys(episode, required, required | {'worktree_id', 'review_objective'}, 'history episode')
    if episode['harness'] not in {'codex', 'pi', 'claude', 'webcodex'}:
        _fail('invalid_episode', 'Retain the original supported harness')
    for field in ('session_id', 'cwd', 'project_id', 'task_state', 'review_scope'):
        _nonempty(episode[field], 'episode.' + field)
        if len(episode[field]) > 4096:
            _fail('invalid_episode', 'Episode metadata exceeds the bounded field size')
    if not Path(episode['cwd']).is_absolute():
        _fail('invalid_episode', 'Original episode cwd must be absolute')
    if episode['branch'] is not None:
        _nonempty(episode['branch'], 'selected branch/leaf')
    modes = episode['task_modes']
    if not isinstance(modes, list) or not modes or len(modes) > 2 or any(m not in {'research', 'general'} for m in modes):
        _fail('invalid_episode', 'Episode modes describe the task segment, not directory names')
    ranges = episode['ranges']
    if not isinstance(ranges, list) or not 1 <= len(ranges) <= 32:
        _fail('invalid_episode', 'An episode needs bounded original source ranges')
    uris = {s['uri'] for s in sources}
    for item in ranges:
        _keys(item, {'uri', 'locator', 'source_version'}, {'uri', 'locator', 'source_version'}, 'episode range')
        _sources([{'uri': item['uri'], 'locator': item['locator']}])
        if item['uri'] not in uris or not isinstance(item['source_version'], str) or not re.fullmatch('[0-9a-f]{64}', item['source_version']):
            _fail('invalid_episode', 'Ranges must identify the retained original source and version')
    for field in ('coverage_refs', 'gaps'):
        values = episode[field]
        if not isinstance(values, list) or len(values) > 32 or any(not isinstance(v, str) or not v.strip() or len(v) > 4096 for v in values):
            _fail('invalid_episode', 'Coverage uses bounded references/gaps, not a second cursor ledger')
    if not episode['coverage_refs'] and not episode['gaps']:
        _fail('invalid_episode', 'Missing source/review coverage must remain an explicit gap')
    if len(_json(episode).encode()) > 32768:
        _fail('invalid_episode', 'Episode metadata exceeds its byte budget')


class HistoryStore(MemoryStore):
    collection = 'history'

    def _record_input(self, record):
        super()._record_input(record)
        if record['kind'] == 'episode':
            validate_episode(record.get('episode'), record['sources'])
        return record

    def _admit(self, record):
        super()._admit(record)
        if 'withdraws' not in record and record['kind'] != 'episode':
            _fail('invalid_episode', 'History accepts an explicit episode, not relabeled active knowledge')

    def search(self, *args, **kwargs):
        kwargs['include_shared'] = False
        result = super().search(*args, **kwargs)
        return {**result, 'collection': 'history', 'items': [{**r, 'collection': 'history'} for r in result['items']]}

    def read(self, *args, **kwargs):
        kwargs['include_shared'] = False
        result = super().read(*args, **kwargs)
        return {**result, 'collection': 'history', 'items': [{**r, 'collection': 'history'} for r in result['items']]}

    def capture(self, context, record, idempotency_key, review=None, details=None, **options):
        if options.get('live_correction') is not None:
            _fail('not_live_original', 'Historical accounts cannot use the direct current-user correction exception')
        details = deepcopy(details or {})
        details.setdefault('task_modes', record.get('episode', {}).get('task_modes', []))
        details.setdefault('statement_type', 'reference')
        return super().capture(context, record, idempotency_key, review, details, **options)


def _semantic_review(review, refs):
    """The ordinary explicit review contract is cooperative source/scope review."""
    ordinary_review(review)
    return {'decision': 'approve', 'reason': review['reason'],
            'scope_checked': True, 'counterexamples_checked': True, 'checked_refs': list(refs)}


def _qualifier(record):
    return (tuple(sorted(record['claim']['projects'])),
            *[record.get('qualifier', {'scope': 'project'}).get(k) for k in ('scope', 'worktree_id', 'task_id')])


def _canonical(record):
    return {k: v for k, v in record.items() if k not in {'effective_status', 'details', 'recall_retired', 'curation_revision'}}


class CollaborationStore:
    collection = 'collaboration'

    def __init__(self, store):
        self.store = store
        self.root = store.root

    def context(self, *args, **kwargs):
        _fail('invalid_collection', 'Use the common project context for applicable preferences')

    def _access(self, context, *, write=False):
        from .configuration import configured_profile
        identifier, policy, profile, scope = configured_profile(self.store, context, reading=not write)
        if scope['project_id'] not in policy['collaboration_projects']:
            _fail('scope_mismatch', 'Current project has no collaboration grant')
        return identifier, policy, profile, scope

    def _visible(self, record, scope):
        q = record.get('qualifier', {'scope': 'project'})
        return (scope['project_id'] in record['claim']['projects'] and
                (q['scope'] == 'project' or q.get('worktree_id') == scope['worktree_id'] and
                 (q['scope'] == 'worktree' or q.get('task_id') == scope.get('task_id'))))

    def _usable(self, record, scope):
        from .dreaming import record_use_filter
        shaped = {'project_id': scope['project_id'], 'kind': 'decision',
                  'title': record['claim']['topic'], 'sources': record.get('sources', [])}
        # Source-less legacy objects are history-navigation only until reviewed.
        if not shaped['sources']:
            return False
        return record_use_filter(self.store, scope='collaboration')(shaped)

    def _records(self, context, include_inactive=False):
        _, policy, profile, scope = self._access(context)
        records = [r for r in collaboration(self.store) if self._visible(r, scope) and self._usable(r, scope)]
        if not profile['allow_inferred']:
            records = [r for r in records if r['claim']['level'] != 'inferred']
        return scope, [r for r in records if include_inactive or r['effective_status'] == 'active']

    def read(self, context, ids, include_inactive=False, *, include_shared=False):
        if not isinstance(ids, list) or not 1 <= len(ids) <= 100 or any(not isinstance(i, str) or not RECORD_ID.fullmatch(i) for i in ids):
            _fail('invalid_input', 'Read canonical collaboration IDs')
        with self.store._gate():
            scope, records = self._records(context, include_inactive)
            by_id = {r['id']: r for r in records}
            return {'status': 'ok', 'collection': 'collaboration', 'scope': scope,
                    'items': [by_id[i] for i in ids if i in by_id], 'missing_ids': [i for i in ids if i not in by_id]}

    def search(self, context, query, limit=20, include_inactive=False, *, offset=0, expected_revision=None,
               task_mode=None, mode_restriction=None, **options):
        from .context_packet import validate_mode
        from .recall import rank, size
        validate_mode(task_mode, mode_restriction)
        if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or offset < 0:
            _fail('invalid_input', 'Search limit and offset must be bounded nonnegative integers')
        with self.store._gate():
            scope, records = self._records(context, include_inactive)
            revision = _digest([scope, query, task_mode, mode_restriction, records])
            if expected_revision is not None and expected_revision != revision:
                _fail('stale_search', 'Refresh collaboration search after a corpus change')
            ranked = rank([{'id': r['id'], 'project_id': scope['project_id'], 'title': r['claim']['topic'],
                            'body': r['body'], 'sources': r.get('sources', []), 'details': {}} for r in records], query)
            by_id = {r['id']: r for r in records}
            if mode_restriction:
                ranked = [r for r in ranked if mode_restriction['mode'] in by_id[r['id']]['claim'].get('task_modes', [])]
            result = {'status': 'ok', 'collection': 'collaboration', 'scope': scope, 'items': [],
                      'corpus_revision': revision, 'next_offset': None, 'omitted': max(0, len(ranked) - offset)}
            for hit in ranked[offset:offset + limit]:
                r = by_id[hit['id']]
                card = {'id': r['id'], 'collection': 'collaboration', 'title': r['claim']['topic'],
                        'level': r['claim']['level'], 'conditions': r['claim']['conditions'],
                        'effective_status': r['effective_status'], 'read_hint': {'collection': 'collaboration', 'ids': [r['id']]}}
                result['items'].append(card)
                if size(result) > 11500:
                    result['items'].pop(); break
            end = offset + len(result['items'])
            result.update(next_offset=end if end < len(ranked) else None, omitted=max(0, len(ranked) - end))
            return result

    def propose(self, context, record, idempotency_key):
        return self.capture(context, record, idempotency_key)

    def capture(self, context, record, idempotency_key, review=None, details=None, *, live_correction=None, source_review=None):
        _keys(record, {'claim', 'scope', 'sources'}, {'claim', 'scope', 'sources'}, 'collaboration record')
        validate_claim(record['claim']); _sources(record['sources'])
        if record['claim']['level'] not in {'explicit', 'inferred'} or record['scope'] not in {'project', 'worktree', 'task'}:
            _fail('invalid_input', 'Collaboration retains explicit/inferred scoped claims')
        if details:
            _fail('invalid_input', 'Collaboration semantic metadata belongs in its typed claim')
        _nonempty(idempotency_key, 'idempotency_key')
        digest = _digest({'operation': 'capture', 'context': context, 'record': record, 'review': review,
                          'live_correction': live_correction, 'source_review': source_review})
        with self.store._gate():
            profile_id, policy, profile, scope = self._access(context, write=True)
            records = collaboration(self.store)
            prior = self._retry(records, idempotency_key, digest, scope)
            if prior:
                return prior
            if (scope['project_id'] not in record['claim']['projects'] or
                    not set(record['claim']['projects']) <= set(policy['collaboration_projects']).intersection(profile['target_projects'])):
                _fail('scope_mismatch', 'Claim projects exceed existing collaboration/target grants')
            qualifier = {'scope': record['scope']}
            if record['scope'] != 'project':
                qualifier['worktree_id'] = scope['worktree_id']
            if record['scope'] == 'task':
                if not scope.get('task_id'):
                    _fail('scope_mismatch', 'Task preference needs the real task identity')
                qualifier['task_id'] = scope['task_id']
            policy_revision = _digest(policy)
        c = deepcopy(record['claim'])
        basis, sources = None, deepcopy(record['sources'])
        if live_correction is not None:
            if review is None:
                _fail('pending_review', 'Direct current-user publication needs the foreground review')
            basis = live_review(context, scope, {'scope': record['scope']}, live_correction, reviewed_at=_now())
            source = live_source(basis)
            sources = [source, *sources]
            c['refs'] = [source['uri']]
        elif review is not None:
            if source_review is None:
                _fail('historical_source_review_required', 'Historical collaboration needs the original granted public evidence')
            sources = self._review_sources(context, c, review, source_review)
        semantic = _semantic_review(review, c['refs']) if review else {
            'decision': 'pending', 'reason': 'Unreviewed candidate only.', 'scope_checked': False,
            'counterexamples_checked': False, 'checked_refs': []}
        active = review is not None and c['level'] == 'explicit'
        if active:
            reviewed(c, semantic)
        operation = {'action': 'collaboration_create', 'reserved_id': uuid.uuid4().hex,
                     'claim': c, 'visibility': 'active' if active else 'candidate',
                     'key': idempotency_key, 'digest': digest, 'review': semantic}
        with self.store._gate():
            _, current_policy, _, current_scope = self._access(context, write=True)
            if _digest(current_policy) != policy_revision or current_scope != scope:
                _fail('stale_policy', 'Scope changed while reviewing source material')
            records = collaboration(self.store)
            prior = self._retry(records, idempotency_key, digest, scope)
            if prior:
                return prior
            shaped = {'claim': c, 'sources': sources, 'qualifier': qualifier}
            if not self._usable(shaped, scope):
                _fail('source_forbidden', 'Current source-use restrictions prohibit this capture')
            relative, data = collaboration_effect(self.store, operation, context, source_uris=sources)
            canonical = parse_markdown(data)
            canonical['qualifier'] = qualifier
            if basis is not None:
                canonical['live_review'] = basis
            canonical['content_digest'] = _digest({k: canonical.get(k) for k in ('claim', 'sources', 'qualifier', 'live_review')})
            self.store._publish(safe_path(self.store, relative), markdown(canonical))
            return {'status': 'ok', 'id': canonical['id'], 'collection': 'collaboration',
                    'effective_status': canonical['events'][-1]['state'], 'replayed': False}

    def _review_sources(self, context, claim, review, selection):
        from .configuration import configured_engine
        from .dreaming import compact_source_spec
        from .dream_sources import check_snapshot
        engine = configured_engine(self.store, context)
        policy, profile = engine._policy()
        target = self.store._resolve(context)['project_id']
        profile = {**profile, 'target_project': target, 'sources': engine._catalog(profile).resolve(selection)}
        materials, _, _ = engine._collect(profile)
        working_set = {'target': target, 'profile_snapshot': profile, 'materials': materials}
        semantic = _semantic_review(review, claim['refs'])
        events, _ = engine._admit(working_set, claim, semantic, scope='collaboration', active=claim['level'] == 'explicit')
        specs = {s['id']: s for s in profile['sources']}
        if any(check_snapshot(specs[e['source_id']], materials[e['source_id']]['version']) != 'valid' for e in events.values()):
            _fail('stale_source', 'Historical evidence changed during the bounded normal review')
        return [{'uri': Path(specs[e['source_id']]['path']).as_uri(), 'locator': e.get('locator', str(e['event_id'])),
                 'note': 'dream-source-v1:' + _json({'profile': engine.profile_id, 'source_id': e['source_id'],
                     'event_key': e['key'], 'lineage': e.get('lineage', []),
                     'source_grant': _digest(compact_source_spec(specs[e['source_id']])),
                     'source_spec': compact_source_spec(specs[e['source_id']]), 'claim_level': claim['level']})}
                for e in events.values()]

    def _retry(self, records, key, digest, scope):
        for r in records:
            for event in r['events']:
                if event['key'] == key:
                    if not self._visible(r, scope) or event['operation_digest'] != digest:
                        _fail('idempotency_conflict', 'Operation key already has another scoped payload')
                    return {'status': 'ok', 'id': r['id'], 'collection': 'collaboration',
                            'effective_status': r['effective_status'], 'replayed': True}

    def _transition(self, context, id, review, idempotency_key, action, old_ids=(), expected_revision=None):
        ordinary_review(review)
        if not isinstance(id, str) or not RECORD_ID.fullmatch(id):
            _fail('invalid_input', 'A canonical collaboration target is required')
        digest = _digest({'context': context, 'id': id, 'review': review, 'action': action,
                          'old_ids': list(old_ids), 'expected_revision': expected_revision})
        with self.store._gate():
            _, _, profile, scope = self._access(context, write=True)
            records = collaboration(self.store)
            prior = self._retry(records, idempotency_key, digest, scope)
            if prior:
                return prior
            by_id = {r['id']: r for r in records}
            r = by_id.get(id)
            if not r or not self._visible(r, scope):
                _fail('not_found', 'Target is outside the actual caller scope')
            if expected_revision is not None and expected_revision != _digest(_canonical(r)):
                _fail('stale_record', 'Collaboration changed after review')
            if action == 'collaboration_publish':
                if not self._usable(r, scope) or (r['claim']['level'] == 'inferred' and not profile['allow_inferred']):
                    _fail('source_forbidden', 'Current grants do not permit publication')
                if r.get('live_review') is None and not any(s.get('note', '').startswith('dream-source-v1:') for s in r.get('sources', [])):
                    _fail('historical_source_review_required', 'Candidate lacks original historical source review')
            for old_id in old_ids:
                old = by_id.get(old_id)
                if not old or not self._visible(old, scope) or _qualifier(old) != _qualifier(r):
                    _fail('scope_mismatch', 'Replacement must use exact preference scope and projects')
            semantic = _semantic_review(review, r['claim']['refs'])
            op = {'action': action, 'record_id': id, 'claim': r['claim'], 'key': idempotency_key,
                  'digest': digest, 'review': semantic, 'predecessors': list(old_ids)}
            relative, data = collaboration_effect(self.store, op, context)
            self.store._publish(safe_path(self.store, relative), data)
            return {'status': 'ok', 'id': id, 'collection': 'collaboration',
                    'effective_status': 'active' if action == 'collaboration_publish' else 'withdrawn', 'replayed': False}

    def promote(self, context, id, review, idempotency_key):
        return self._transition(context, id, review, idempotency_key, 'collaboration_publish')

    def supersede(self, context, id, old_ids, review, idempotency_key):
        if not isinstance(old_ids, list) or not old_ids or any(not isinstance(x, str) or not RECORD_ID.fullmatch(x) for x in old_ids) or len(set(old_ids)) != len(old_ids):
            _fail('invalid_input', 'A replacement needs distinct canonical predecessor IDs')
        return self._transition(context, id, review, idempotency_key, 'collaboration_publish', old_ids)

    def delete(self, context, id, review, idempotency_key):
        return self._transition(context, id, review, idempotency_key, 'collaboration_withdraw')

    def curate(self, context, id, review, idempotency_key, details=None, retired=None,
               expected_content_digest=None, expected_revision=None):
        from .curation import validate_details
        ordinary_review(review)
        if retired is not None and type(retired) is not bool:
            _fail('invalid_input', 'retired must be a boolean')
        details = deepcopy(details or {})
        if details.get('extensions', {}).get('live_review'):
            _fail('invalid_assurance', 'Curation cannot manufacture live-review provenance')
        digest = _digest({'context': context, 'id': id, 'review': review, 'details': details, 'retired': retired,
                          'expected_content_digest': expected_content_digest, 'expected_revision': expected_revision})
        with self.store._gate():
            _, _, _, scope = self._access(context, write=True)
            records = collaboration(self.store)
            prior = self._retry(records, idempotency_key, digest, scope)
            if prior:
                return prior
            r = next((r for r in records if r['id'] == id and self._visible(r, scope)), None)
            if r is None:
                _fail('not_found', 'Curation target is outside actual scope')
            if expected_content_digest is not None and expected_content_digest != r.get('content_digest', _digest(r['claim'])):
                _fail('stale_record', 'Collaboration content changed')
            if expected_revision is not None and expected_revision != r['curation_revision']:
                _fail('stale_curation', 'Collaboration curation changed')
            shaped = {'sources': r.get('sources', []), 'scope': r.get('qualifier', {'scope': 'project'})['scope'], 'project_id': scope['project_id']}
            validate_details(details, shaped, {p['id'] for p in self.store._registry()['projects']})
            canonical = _canonical(r)
            event = {'key': idempotency_key, 'operation_digest': digest, 'previous': canonical['events'][-1]['digest'],
                     'state': canonical['events'][-1]['state'], 'executor': {k: context[k] for k in ('harness', 'cwd', 'session_id', 'actor')},
                     'at': _now(), 'review': _semantic_review(review, r['claim']['refs']), 'supersedes': [],
                     'curation': {'details': details, 'retired': retired}}
            event['digest'] = _digest(event)
            canonical['events'].append(event)
            if len(canonical['events']) > 128:
                _fail('curation_limit', 'Collaboration journal is full')
            self.store._publish(safe_path(self.store, f'collaboration/Pein/records/{id}.md'), markdown(canonical))
            return {'status': 'ok', 'id': id, 'collection': 'collaboration', 'replayed': False,
                    'curation_revision': _digest(canonical['events'])}
