"""Scoped discovery and disposition of the retained Dreaming issue objects.

A proposal is not active knowledge, a task queue, or execution authority. Source
identity and current restrictions are checked even when resolved notes are read.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import re

from .core import _digest, _fail, _json, _nonempty, _now
from .curation import read_json, safe_path
from .configuration import configured_profile


def _allowed(store, item, scope, profile_id, profile):
    from .dream_catalog import SourceCatalog
    from .dreaming import dispositions, _source_keys
    if item.get('target') != scope['project_id'] or not item.get('source_bindings'):
        return False  # Legacy digests alone do not prove a readable note's scope.
    catalog = SourceCatalog(store, profile_id, profile)
    keys = set(item.get('evidence_keys', []))
    for source in item['source_bindings']:
        if not catalog.authorized(source):
            return False
        keys.update({'source:' + source['id'], 'source-uri:' + Path(source['path']).as_uri()})
        keys.update(source.get('lineage', []))
    keys = _source_keys(keys)
    return not any(d['target'] == scope['project_id'] and d['scope'] == 'research' and
                   d['topic'] in {'*', item['topic']} and d['kind'] in {'no_reuse', 'user_rejected', 'inference_error'} and
                   keys.intersection(_source_keys(d['source_keys'])) for d in dispositions(store)['items'])


def search(store, context, query='', include_resolved=False, limit=8):
    if not isinstance(query, str) or len(query) > 4096 or type(include_resolved) is not bool or type(limit) is not int or not 1 <= limit <= 32:
        _fail('invalid_input', 'Proposal search needs bounded query and limits')
    from .recall import tokens
    from .context_packet import exposure_size
    with store._gate():
        profile_id, _, profile, scope = configured_profile(store, context, reading=True)
        files = sorted(safe_path(store, 'dreaming/issues').glob('*.json'))
        if len(files) > 2048:
            _fail('corpus_limit', 'Proposal inventory exceeds the supported bound')
        items = []
        terms = set(tokens(query))
        for path in files:
            item = read_json(store, path.relative_to(store.root))
            if not _allowed(store, item, scope, profile_id, profile):
                continue
            if not include_resolved and item.get('disposition', 'pending') != 'pending':
                continue
            if terms and not terms.intersection(tokens(item['topic'] + ' ' + item['note'] + ' ' + item['relation'])):
                continue
            items.append({k: deepcopy(item.get(k)) for k in ('id', 'target', 'topic', 'relation', 'note',
                'disposition', 'needs_semantic_review', 'observations', 'as_of', 'source_pointers')} |
                {'revision': _digest(item), 'authority': 'advisory-only',
                 'current_actions': sorted(profile['actions']),
                 **({'observed_actions_changed': sorted(item['observations']['current_actions']) != sorted(profile['actions'])}
                    if isinstance(item.get('observations', {}).get('current_actions'), list) and
                       all(isinstance(action, str) for action in item['observations']['current_actions']) else {})})
        result = {'status': 'ok', 'scope': scope, 'items': [], 'omitted': len(items)}
        for item in items[:limit]:
            trial = {**result, 'items': [*result['items'], item], 'omitted': len(items) - len(result['items']) - 1}
            if exposure_size(trial) <= 12000:
                result = trial
        return result


def resolve(store, context, id, disposition, reason, expected_revision, idempotency_key):
    if not isinstance(id, str) or not re.fullmatch('[0-9a-f]{64}', id):
        _fail('invalid_input', 'Resolve one exact proposal id')
    if disposition not in {'accepted', 'rejected', 'handled', 'deferred'}:
        _fail('invalid_input', 'Expected a proposal disposition')
    for value in (reason, expected_revision, idempotency_key):
        _nonempty(value, 'proposal disposition field')
        if len(value) > 4096:
            _fail('invalid_input', 'Proposal disposition is oversized')
    digest = _digest({'context': context, 'id': id, 'disposition': disposition, 'reason': reason,
                      'expected_revision': expected_revision})
    with store._gate():
        profile_id, _, profile, scope = configured_profile(store, context)
        path = f'dreaming/issues/{id}.json'
        item = read_json(store, path)
        if not item or not _allowed(store, item, scope, profile_id, profile):
            _fail('not_found', 'Proposal is outside the current caller/source scope')
        journal = item.get('resolutions', [])
        for prior in journal:
            if prior['key'] == idempotency_key:
                if prior['digest'] != digest:
                    _fail('idempotency_conflict', 'Proposal key already binds a different payload')
                return {'status': 'ok', 'id': id, 'disposition': item['disposition'], 'replayed': True}
        if _digest(item) != expected_revision:
            _fail('stale_proposal', 'Proposal changed after the reviewed read')
        if len(journal) >= 128:
            _fail('proposal_limit', 'Proposal disposition journal is full')
        item['resolutions'] = [*journal, {'key': idempotency_key, 'digest': digest, 'disposition': disposition,
                               'reason': reason, 'at': _now(), 'caller': deepcopy(context)}]
        item.update(disposition=disposition, resolved_semantic_digest=item['semantic_digest'])
        from .dreaming import _put
        _put(store, path, item)
        return {'status': 'ok', 'id': id, 'disposition': disposition, 'revision': _digest(item), 'replayed': False}
