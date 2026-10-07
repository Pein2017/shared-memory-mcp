"""Operator-bound, model-free DreamRuns and recoverable restricted publication.

No method launches a model, a research job or a native session. The dedicated
transport binds profile and executor outside model arguments. This is an endpoint
boundary, not an OS sandbox or proof about an external harness's other tools.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path
import re
import uuid
from urllib.parse import unquote, urlparse

from .core import MAX_RECORD_BYTES, MAX_RECORDS, RECORD_ID, SAFE_ID, MemoryError, _decode, _digest, _fail, _json, _keys, _nonempty, _now
from .curation import projected_records, read_json, safe_path
from .dream_records import (ACTIONS, bounded_strings, collaboration, collaboration_effect,
                            core_effect, namespace, parse_markdown, render_claim,
                            reviewed, validate_claim, validate_review)
from .dream_sources import read_source, validate_source

POLICY = 'dreaming/policy.json'
DISPOSITIONS = 'dreaming/dispositions.json'
BUDGET_KEYS = {'source_bytes', 'events', 'operations', 'drafts', 'view_chars', 'view_bytes',
               'model_calls', 'input_tokens', 'output_tokens', 'seconds', 'repair_rounds'}


def _put(store, relative, document, *, immutable=False):
    path = safe_path(store, relative)
    data = (_json(document) + '\n').encode('utf-8')
    if len(data) > MAX_RECORD_BYTES:
        _fail('dream_limit', 'Dream object exceeds the explicit byte bound')
    if immutable and path.exists():
        if path.read_bytes() != data:
            _fail('immutable_draft', 'Immutable Dream object already has different bytes')
        return
    store._publish(path, data)


def validate_policy(store, policy):
    _keys(policy, {'version', 'subject', 'collaboration_projects', 'profiles'},
          {'version', 'subject', 'collaboration_projects', 'profiles'}, 'dream policy')
    if policy['version'] != 2 or policy['subject'] != 'Pein':
        _fail('invalid_policy', 'Unsupported policy version or collaboration subject')
    projects = {p['id'] for p in store._registry()['projects']}
    bounded_strings(policy['collaboration_projects'], 'collaboration_projects')
    if not set(policy['collaboration_projects']) <= projects:
        _fail('invalid_policy', 'Collaboration grants require real registered project IDs')
    if not isinstance(policy['profiles'], dict) or not 1 <= len(policy['profiles']) <= 32:
        _fail('invalid_policy', 'Profiles must be a bounded mapping')
    fields = {'target_projects', 'executor_projects', 'source_grants', 'actions', 'provider', 'transport',
              'budgets', 'scenarios', 'allow_inferred'}
    for name, profile in policy['profiles'].items():
        if not isinstance(name, str) or not SAFE_ID.fullmatch(name):
            _fail('invalid_policy', 'Invalid profile name')
        _keys(profile, fields, fields, 'dream profile')
        bounded_strings(profile['target_projects'], 'target_projects', nonempty=True)
        bounded_strings(profile['executor_projects'], 'executor_projects', nonempty=True)
        bounded_strings(profile['scenarios'], 'scenarios', nonempty=True)
        bounded_strings(profile['actions'], 'actions')
        if not set(profile['target_projects']) <= projects or not set(profile['executor_projects']) <= projects or not set(profile['actions']) <= ACTIONS:
            _fail('invalid_policy', 'Unregistered target/executor or unsupported action')
        for field in ('provider', 'transport'):
            _nonempty(profile[field], field)
        if type(profile['allow_inferred']) is not bool:
            _fail('invalid_policy', 'allow_inferred must be boolean')
        _keys(profile['budgets'], BUDGET_KEYS, BUDGET_KEYS, 'budgets')
        if any(type(x) is not int or x < 0 for x in profile['budgets'].values()):
            _fail('invalid_policy', 'Budgets must be explicit nonnegative integers')
        caps = {'source_bytes': 16 * 1048576, 'events': 128, 'operations': 32, 'drafts': 8,
                'view_chars': 16000, 'view_bytes': 64000, 'seconds': 86400, 'repair_rounds': 8}
        if any(not 1 <= profile['budgets'][k] <= cap for k, cap in caps.items()):
            _fail('invalid_policy', 'A local resource budget exceeds its supported bound')
        from .dream_catalog import validate_source_grants
        validate_source_grants(store, profile['source_grants'])
    return policy


def configure_policy(store, policy, *, expected_revision='absent'):
    """Trusted operator action. Not exposed to the bound Dreamer tool surface."""
    with store._gate():
        validate_policy(store, policy)
        old = read_json(store, POLICY)
        actual = _digest(old) if old is not None else 'absent'
        if actual != expected_revision:
            _fail('stale_policy', 'Refresh the current policy before replacing it')
        _put(store, POLICY, policy)
    return {'status': 'configured', 'revision': _digest(policy)}


def dispositions(store):
    data = read_json(store, DISPOSITIONS, {'version': 1, 'items': []})
    _keys(data, {'version', 'items'}, {'version', 'items'}, 'dispositions')
    if type(data['version']) is not int or data['version'] != 1 or not isinstance(data['items'], list) or len(data['items']) > 2048:
        _fail('corrupt_disposition', 'Unsupported or oversized disposition ledger')
    from .core import _utc
    identities = set()
    fields = {'id', 'at', 'target', 'topic', 'scope', 'source_keys', 'kind', 'reason', 'executor'}
    for item in data['items']:
        _keys(item, fields, fields, 'disposition')
        if (not isinstance(item['kind'], str) or item['kind'] not in {'no_value', 'inference_error', 'uncertain', 'user_rejected', 'no_reuse'} or
                not isinstance(item['scope'], str) or item['scope'] not in {'research', 'collaboration'}):
            _fail('corrupt_disposition', 'Unknown source-use disposition')
        for field in ('target', 'topic', 'reason'):
            _nonempty(item[field], 'disposition.' + field)
        bounded_strings(item['source_keys'], 'source_keys', nonempty=True, limit=64)
        _utc(item['at'])
        if not isinstance(item['executor'], dict):
            _fail('corrupt_disposition', 'Disposition executor is missing')
        payload = {k: v for k, v in item.items() if k not in {'id', 'at'}}
        if item['id'] != _digest(payload) or item['id'] in identities:
            _fail('corrupt_disposition', 'Disposition identity/integrity mismatch')
        identities.add(item['id'])
    return data


def add_disposition(store, context, *, target, topic, scope, source_keys, kind, reason):
    """Operator-only semantic disposition; no-use is not reversible metadata."""
    kinds = {'no_value', 'inference_error', 'uncertain', 'user_rejected', 'no_reuse'}
    bounded_strings(source_keys, 'source_keys', nonempty=True)
    if kind not in kinds or scope not in {'research', 'collaboration'}:
        _fail('invalid_input', 'Unsupported disposition kind or scope')
    _nonempty(topic, 'topic')
    _nonempty(reason, 'reason')
    with store._gate():
        caller = store._resolve(context)
        if target not in {p['id'] for p in store._registry()['projects']}:
            _fail('invalid_input', 'Disposition target must be registered')
        data = dispositions(store)
        source_keys = set(source_keys)
        policy = read_json(store, POLICY, {'profiles': {}})
        for profile in policy['profiles'].values():
            if target in profile['target_projects']:
                for source in profile['source_grants']:
                    if 'source:' + source['id'] in source_keys:
                        source_keys.add('source-uri:' + Path(source['path']).as_uri())
        item = {'target': target, 'topic': topic, 'scope': scope, 'source_keys': sorted(source_keys),
                'kind': kind, 'reason': reason, 'executor': {**context, 'project_id': caller['project_id']}}
        identity = _digest(item)
        if not any(x['id'] == identity for x in data['items']):
            data['items'].append({**item, 'id': identity, 'at': _now()})
            _put(store, DISPOSITIONS, data)
    return {'status': 'recorded', 'id': identity, 'revision': _digest(data)}


def _source_keys(keys):
    """Compare local-file identities like source_hint, without rewriting evidence."""
    result = set()
    for key in keys:
        if key.startswith('source-uri:'):
            parsed = urlparse(key[len('source-uri:'):])
            if parsed.scheme == 'file' and parsed.netloc in ('', 'localhost'):
                path = Path(unquote(parsed.path))
                if path.is_absolute():
                    key = 'source-uri:' + path.as_uri()
        result.add(key)
    return result


def compact_source_spec(spec):
    """Persist source authority and frozen identity, never unrelated page events."""
    result = {k: deepcopy(v) for k, v in spec.items() if k != '_catalog_page'}
    if '_catalog_page' in spec:
        result['_catalog_page'] = {'version': deepcopy(spec['_catalog_page']['version'])}
    return result


def record_use_filter(store, *, scope='research'):
    """Apply source-use dispositions, including inactive/audit reads.

    Dream records bind exact grants and event identities in source metadata.
    Untagged v1 records retain ordinary semantics except explicit URI-level
    source-use prohibitions; their original canonical bytes are never rewritten.
    """
    policy = read_json(store, POLICY)
    ledger = [{**item, 'source_keys': _source_keys(item['source_keys'])} for item in dispositions(store)['items']]
    def allowed(record):
        for source in record['sources']:
            if any(item['target'] == record['project_id'] and item['scope'] == scope and
                   item['topic'] in {'*', record['title']} and _source_keys(['source-uri:' + source['uri']]).intersection(item['source_keys']) and
                   item['kind'] in {'no_reuse', 'user_rejected', 'inference_error'} for item in ledger):
                return False
            note = source.get('note', '')
            if not note.startswith('dream-source-v1:'):
                continue
            try:
                binding = _decode(note[len('dream-source-v1:'):])
                profile = policy['profiles'][binding['profile']]
                from .dream_catalog import SourceCatalog
                spec = binding.get('source_spec')
                if spec is None:
                    spec = next(s for s in SourceCatalog(store, binding['profile'], profile).resolve() if s['id'] == binding['source_id'])
                if record['project_id'] not in profile['target_projects'] or Path(spec['path']).as_uri() != source['uri']:
                    return False
                if not SourceCatalog(store, binding['profile'], profile).authorized(spec) or binding.get('source_grant') != _digest(spec):
                    return False
                keys = _source_keys({binding['event_key'], 'source:' + binding['source_id'], 'source-uri:' + source['uri'], *binding['lineage']})
                for item in ledger:
                    if (item['target'] == record['project_id'] and item['scope'] == scope and
                            item['topic'] in {'*', record['title']} and keys.intersection(item['source_keys']) and
                            item['kind'] in {'no_reuse', 'user_rejected', 'inference_error'}):
                        return False
            except (MemoryError, ValueError, TypeError, KeyError, StopIteration):
                return False
        return True
    return allowed


class Dreaming:
    def __init__(self, store, profile_id, caller, *, publisher=False):
        self.store = store
        self.profile_id = profile_id
        self.caller = deepcopy(caller)
        scope = store._resolve(self.caller)
        self.caller.update(cwd=scope['cwd'], project_id=scope['project_id'])
        self.publisher = publisher is True
        self._policy()

    def _policy(self):
        policy = read_json(self.store, POLICY)
        if policy is None:
            _fail('unconfigured_dreaming', 'An operator must first install an explicit bounded profile')
        validate_policy(self.store, policy)
        profile = policy['profiles'].get(self.profile_id)
        scope = self.store._resolve(self.caller)
        if not profile or scope['project_id'] not in profile['executor_projects']:
            _fail('dream_access_denied', 'Bound executor is not allowed by the selected profile')
        return policy, profile

    def _run(self, run_id, generation=None, *, check_caller=True):
        if not isinstance(run_id, str) or not RECORD_ID.fullmatch(run_id):
            _fail('invalid_input', 'Expected an exact DreamRun ID')
        run = read_json(self.store, f'dreaming/runs/{run_id}/run.json')
        if not run or run['id'] != run_id or run['profile_id'] != self.profile_id:
            _fail('dream_access_denied', 'Run does not belong to the bound profile')
        _, profile = self._policy()
        if run['target'] not in profile['target_projects']:
            _fail('dream_access_denied', 'An existing Run cannot be retargeted by changing its profile')
        if generation is not None and (type(generation) is not int or run['generation'] != generation):
            _fail('stale_attempt', 'Attempt generation is stale; observe before requesting explicit takeover')
        if check_caller and run['attempts'][-1]['caller'] != self.caller:
            _fail('attempt_identity_mismatch', 'Run ID and generation do not authenticate another executor')
        return run

    def _target(self, profile, target_project=None):
        if target_project is None:
            if len(profile['target_projects']) != 1:
                _fail('target_required', 'Select one authorized target project')
            target_project = profile['target_projects'][0]
        if target_project not in profile['target_projects']:
            _fail('dream_access_denied', 'Target is outside the bound profile')
        return target_project

    def _catalog(self, profile=None):
        from .dream_catalog import SourceCatalog
        return SourceCatalog(self.store, self.profile_id, profile or self._policy()[1])

    def _effective(self, run):
        _, profile = self._policy()
        self._target(profile, run['target'])
        return {**profile, 'target_project': run['target'],
                'sources': [s for s in run['profile_snapshot']['sources'] if self._catalog(profile).authorized(s)]}

    def catalog(self, *, cursor=None, limit=50):
        if type(limit) is not int or not 1 <= limit <= 100:
            _fail('invalid_input', 'Catalog limit must be one to one hundred')
        with self.store._gate():
            policy, profile = self._policy()
            runs = []
            paths = sorted(safe_path(self.store, 'dreaming/active').glob(self.profile_id + '-*.json'))
            if len(paths) > MAX_RECORDS:
                _fail('dream_limit', 'Active lane inventory exceeds its supported bound')
            for path in paths:
                active = read_json(self.store, path.relative_to(self.store.root))
                run = read_json(self.store, f"dreaming/runs/{active['run_id']}/run.json")
                if not run or run['profile_id'] != self.profile_id:
                    _fail('dream_access_denied', 'Active index does not belong to this profile')
                if run['target'] not in profile['target_projects']:
                    continue
                run = self._run(active['run_id'], check_caller=False)
                if run['phase'] != 'closed':
                    runs.append({k: run[k] for k in ('id', 'target', 'generation', 'phase', 'lane')})
            runs.sort(key=lambda item: item['id'])
            revision = _digest({'profile_id': self.profile_id, 'policy': policy, 'runs': runs})
            after = None
            if cursor is not None:
                if not isinstance(cursor, str) or len(cursor) > 1024:
                    _fail('invalid_cursor', 'Expected a bounded catalog cursor')
                try:
                    position = _decode(cursor)
                    _keys(position, {'revision', 'after'}, {'revision', 'after'}, 'catalog cursor')
                except (MemoryError, ValueError, TypeError):
                    _fail('invalid_cursor', 'Catalog cursor is malformed')
                if position['revision'] != revision:
                    _fail('stale_cursor', 'Catalog changed; restart its bounded inventory')
                after = position['after']
                if after not in {item['id'] for item in runs}:
                    _fail('invalid_cursor', 'Catalog cursor does not identify a retained lane')
            remaining = [item for item in runs if after is None or item['id'] > after]
            selected = remaining[:limit]
            next_cursor = _json({'revision': revision, 'after': selected[-1]['id']}) if len(remaining) > limit else None
            grant_fields = {'id', 'path', 'kind', 'format', 'schema', 'native_version', 'leaf_id', 'derived'}
            return {'profile_id': self.profile_id, 'target_projects': profile['target_projects'],
                    'source_grants': [{k: deepcopy(v) for k, v in grant.items() if k in grant_fields} for grant in profile['source_grants']],
                    'actions': profile['actions'], 'publisher': self.publisher, 'active_runs': selected,
                    'revision': revision, 'next_cursor': next_cursor}

    def source_list(self, grant_id, *, relative_dir='', cursor=None, limit=50):
        return self._catalog().list(grant_id, relative_dir=relative_dir, cursor=cursor, limit=limit)

    def source_read(self, selection, *, cursor=None, max_bytes=262144, max_events=128):
        return self._catalog().read(selection, cursor=cursor, max_bytes=max_bytes, max_events=max_events)

    def audit(self, *, target_project=None, **kwargs):
        from .dream_audit import audit_memory
        _, profile = self._policy()
        target = self._target(profile, target_project)
        return audit_memory(self.store, profile, target_project=target, **kwargs)

    def _save(self, run):
        _put(self.store, f"dreaming/runs/{run['id']}/run.json", run)

    def _basis(self, profile):
        return {'namespace': namespace(self.store, profile['target_project']),
                'policy': _digest(read_json(self.store, POLICY)),
                'registry': _digest(self.store._registry()),
                'dispositions': _digest(dispositions(self.store))}

    def _collect(self, profile, previous=None, *, reconsider=False):
        from .dream_incremental import collect
        return collect(profile, previous, reconsider=reconsider)

    def start(self, *, target_project=None, sources=None, reconsider=None):
        policy, profile = self._policy()
        target = self._target(profile, target_project)
        profile = {**profile, 'target_project': target, 'sources': self._catalog(profile).resolve(sources)}
        lane = _digest({'profile': self.profile_id, 'target': target, 'sources': profile['sources']})
        active_path = f'dreaming/active/{self.profile_id}-{lane}.json'
        checkpoint_path = f'dreaming/checkpoints/{self.profile_id}-{lane}.json'
        with self.store._gate():
            active = read_json(self.store, active_path)
            if active:
                existing = self._run(active['run_id'], check_caller=False)
                if existing['phase'] != 'closed':
                    return {'status': 'resume-required', 'run_id': existing['id'],
                            'generation': existing['generation'], 'phase': existing['phase'], 'model_required': False}
            checkpoint = read_json(self.store, checkpoint_path)
            # Close persists its checkpoint inside the Run before publishing the
            # compact index. Recover that exact close-after-write boundary.
            if active and existing.get('checkpoint'):
                checkpoint = existing['checkpoint']
            previous = self._run(checkpoint['run_id'], check_caller=False) if checkpoint else None
        materials, processed, read_bytes = self._collect(profile, previous, reconsider=bool(reconsider))
        source_revision = _digest({k: v['version'] for k, v in materials.items()})
        with self.store._gate():
            current_policy, current_profile = self._policy()
            if _digest(current_policy) != _digest(policy):
                _fail('stale_policy', 'Policy changed during source collection')
            active = read_json(self.store, active_path)
            if active and self._run(active['run_id'], check_caller=False)['phase'] != 'closed':
                return {'status': 'resume-required', 'run_id': active['run_id'], 'model_required': False}
            basis = self._basis(profile)
            fingerprint = _digest({'sources': source_revision, 'basis': basis})
            if checkpoint and checkpoint['fingerprint'] == fingerprint and not reconsider and not checkpoint.get('unprocessed_events'):
                unchecked = [sid for sid, m in materials.items() if not m.get('snapshot_checked')]
                if unchecked:
                    return {'status': 'blocked', 'model_required': False, 'coverage': 'partial',
                            'reason': 'Some sources could not be reverified within budget; this is not no-change',
                            'unchecked_sources': unchecked}
                return {'status': 'no-change', 'model_required': False, 'checkpoint': checkpoint}
            if reconsider is not None:
                _nonempty(reconsider, 'reconsider reason')
            run_id = uuid.uuid4().hex
            run = {'version': 1, 'id': run_id, 'profile_id': self.profile_id,
                   'target': target, 'lane': lane, 'generation': 1,
                   'attempts': [{'generation': 1, 'caller': self.caller, 'at': _now(),
                                 'identity_assurance': 'operator-bound; native-session-unverified'}],
                   'phase': 'collecting', 'technical_outcome': 'pending', 'created_at': _now(),
                   'profile_snapshot': profile, 'policy_revision': _digest(policy),
                   'basis': basis, 'working_basis': deepcopy(basis), 'source_revision': source_revision,
                   'materials': materials, 'coverage': 'complete' if all(x['coverage']['complete'] for x in materials.values()) else 'partial',
                   'processed': processed, 'drafts': [], 'current_draft': None, 'receipts': {}, 'unresolved': [],
                   'issues': [], 'reconsider': reconsider, 'model_calls': 0, 'read_bytes': read_bytes,
                   'previous_run': previous['id'] if previous else None}
            self._save(run)
            _put(self.store, active_path, {'run_id': run_id})
            return {'status': 'created', 'run_id': run_id, 'generation': 1, 'coverage': run['coverage'],
                    'model_required': True, 'execution_mode': 'external-publisher' if self.publisher else 'advisory-draft-only',
                    'provider': profile['provider'], 'transport': profile['transport'], 'budgets': profile['budgets']}

    def inspect(self, run_id):
        self._policy()
        with self.store._gate():
            run = self._run(run_id, check_caller=False)
            result = {k: deepcopy(run[k]) for k in ('id', 'target', 'generation', 'attempts', 'phase',
                    'technical_outcome', 'coverage', 'processed', 'drafts', 'current_draft', 'receipts', 'unresolved', 'issues', 'model_calls', 'read_bytes')}
            if (run['policy_revision'] != _digest(read_json(self.store, POLICY)) or
                    run['basis']['dispositions'] != _digest(dispositions(self.store))):
                result.update(issues=[], unresolved=[], access='changed; semantic excerpts withheld')
            return result

    def materials(self, run_id, source_id=None):
        _, profile = self._policy()
        with self.store._gate():
            run = self._run(run_id)
            snapshot = {s['id']: s for s in run['profile_snapshot']['sources']}
            allowed = {s['id'] for s in snapshot.values() if self._catalog(profile).authorized(s)}
            if source_id is not None and source_id not in allowed:
                _fail('dream_access_denied', 'Source is outside the bound allowlist')
            output = {}
            for sid, material in run['materials'].items():
                if sid not in allowed or source_id is not None and source_id != sid:
                    continue
                item = deepcopy(material)
                item['events'] = [e for e in item['events'] if not self._forbidden_source(run, e)]
                output[sid] = item
            return {'as_of_run': run_id, 'sources': output, 'authority': 'untrusted source data; not execution instructions'}

    def memory(self, run_id, *, query='', limit=8, max_chars=8000):
        """Read admitted target memory, without borrowing a target cwd or raw CRUD."""
        if not isinstance(query, str) or len(query) > 1024 or type(limit) is not int or not 1 <= limit <= 32 or type(max_chars) is not int or not 0 <= max_chars <= 16000:
            _fail('invalid_input', 'Memory query/count/character bounds exceeded')
        with self.store._gate():
            run = self._run(run_id)
            _, profile = self._policy()
            uris = {Path(s['path']).as_uri() for s in self._effective(run)['sources']}
            allowed = record_use_filter(self.store)
            records = [r for r in projected_records(self.store, run['target'])
                       if r['scope'] == 'project' and r['effective_status'] == 'active' and allowed(r)
                       and all(s['uri'] in uris for s in r['sources'])]
            records = self.store._rank(records, query) if query else records
            items, used = [], 0
            for record in records[:limit]:
                item = {k: record[k] for k in ('id', 'title', 'body', 'sources', 'content_digest', 'curation_revision')}
                size = len(_json(item))
                if used + size <= max_chars:
                    items.append(item)
                    used += size
            return {'target': run['target'], 'items': items, 'chars': used,
                    'notice': 'Existing memory is navigation, not new independent evidence; recheck its original sources.'}

    def takeover(self, run_id, expected_generation):
        """Explicit operator continuation. Never a model-facing automatic takeover."""
        self._policy()
        with self.store._gate():
            run = self._run(run_id, expected_generation, check_caller=False)
            if run['phase'] == 'closed':
                _fail('closed_run', 'Closed runs cannot be taken over')
            run['generation'] += 1
            run['attempts'].append({'generation': run['generation'], 'caller': self.caller, 'at': _now(),
                                    'identity_assurance': 'operator-bound; native-session-unverified'})
            self._save(run)
            return {'status': 'taken-over', 'run_id': run_id, 'generation': run['generation']}

    def _events(self, run):
        return {e['key']: e for m in run['materials'].values() for e in m['events']}

    def _forbidden_source(self, run, event, scope=None):
        spec = next(s for s in run['profile_snapshot']['sources'] if s['id'] == event['source_id'])
        keys = _source_keys({event['key'], 'source:' + event['source_id'], 'source-uri:' + Path(spec['path']).as_uri(), *event.get('lineage', [])})
        return any(d['target'] == run['target'] and d['kind'] == 'no_reuse' and
                   (scope is None or d['scope'] == scope) and keys.intersection(_source_keys(d['source_keys']))
                   for d in dispositions(self.store)['items'])

    def _refs(self, run, refs, *, scope, visited=None):
        events, dependencies = {}, {}
        all_events = self._events(run)
        policy, profile = self._policy()
        source_specs = {s['id']: s for s in self._effective(run)['sources']}
        visited = set(visited or ())
        if len(visited) > 32:
            _fail('source_limit', 'Reference graph exceeds the bounded read set')
        for ref in refs:
            if ref in visited:
                _fail('cyclic_reference', 'Evidence references contain a cycle')
            if ref in all_events:
                event = all_events[ref]
                original = next((s for s in run['profile_snapshot']['sources'] if s['id'] == event['source_id']), None)
                if source_specs.get(event['source_id']) != original or self._forbidden_source(run, event, scope):
                    _fail('source_forbidden', 'Source is no longer permitted for this use')
                if event.get('evidence') == 'derivative':
                    _fail('derivative_only', 'Derived material is navigation, not independent support')
                if event.get('harness') in {'pi', 'claude'} and event.get('branch') == 'unspecified':
                    _fail('unverified_branch', 'An event without an explicit verified branch is navigation only')
                events[ref] = event
                continue
            if not isinstance(ref, str) or ':' not in ref:
                _fail('unverifiable_source', 'Unknown frozen event or canonical record reference')
            kind, identifier = ref.split(':', 1)
            if not RECORD_ID.fullmatch(identifier):
                _fail('unverifiable_source', 'Record references require canonical IDs')
            if kind == 'record':
                record = next((r for r in projected_records(self.store, run['target']) if r['id'] == identifier), None)
                if not record or record['effective_status'] != 'active' or not record_use_filter(self.store)(record):
                    _fail('dependency_inactive', 'A referenced project record is not active and usable')
                inner = []
                for source in record['sources']:
                    matches = [e['key'] for e in all_events.values()
                               if e['source_id'] in source_specs and
                               Path(source_specs[e['source_id']]['path']).as_uri() == source['uri'] and
                               (not source.get('locator') or source['locator'] in {e.get('locator'), str(e['event_id'])})]
                    if not matches:
                        _fail('unverifiable_source', 'Record source is outside the frozen authorized working set')
                    inner.extend(matches)
                dependencies[ref] = {'type': 'record', 'id': identifier, 'revision': _digest(record),
                                     'level': 'hypothesis' if record['kind'] == 'hypothesis' or
                                     record['details'].get('statement_type') in {'hypothesis', 'interpretation'} else
                                     'report' if any(s.get('note', '').startswith('dream-source-v1:') and
                                                     _decode(s['note'][len('dream-source-v1:'):]).get('claim_level') == 'report'
                                                     for s in record['sources']) else None}
            elif kind == 'collaboration':
                record = next((r for r in collaboration(self.store) if r['id'] == identifier), None)
                if (not record or record['effective_status'] != 'active' or
                        run['target'] not in set(policy['collaboration_projects']).intersection(record['claim']['projects'])):
                    _fail('dependency_inactive', 'Collaboration reference is not active or permitted for this project')
                inner = record['claim']['refs']
                dependencies[ref] = {'type': 'collaboration', 'id': identifier, 'revision': _digest(record),
                                     'level': record['claim']['level'], 'claim': record['claim']}
            else:
                _fail('unverifiable_source', 'Unsupported reference kind')
            nested_events, nested_deps = self._refs(run, inner, scope=scope, visited=visited | {ref})
            events.update(nested_events)
            dependencies.update(nested_deps)
        return events, dependencies

    def _admit(self, run, claim, review, *, scope, active=True):
        validate_claim(claim)
        policy, profile = self._policy()
        if run['target'] not in claim['projects'] or not set(claim['scenarios']) <= set(profile['scenarios']):
            _fail('scope_mismatch', 'Claim applicability exceeds the selected target or scenarios')
        events, dependencies = self._refs(run, claim['refs'], scope=scope)
        if not events:
            _fail('unverifiable_source', 'A claim needs original frozen source evidence')
        source_keys = set(events)
        for e in events.values():
            spec = next(s for s in run['profile_snapshot']['sources'] if s['id'] == e['source_id'])
            source_keys.update(['source:' + e['source_id'], 'source-uri:' + Path(spec['path']).as_uri(), *e.get('lineage', [])])
        for d in dispositions(self.store)['items']:
            if d['target'] != run['target'] or d['scope'] != scope or d['topic'] not in {'*', claim['topic']}:
                continue
            same = bool(_source_keys(source_keys).intersection(_source_keys(d['source_keys'])))
            if same and d['kind'] in {'no_reuse', 'user_rejected', 'inference_error', 'no_value'}:
                _fail('blocked_disposition', 'This source/topic disposition cannot be revived by backfill')
            if active and d['kind'] in {'user_rejected', 'uncertain', 'inference_error'}:
                _fail('reopen_candidate_only', 'New independent evidence may only reopen a candidate')
        if scope == 'collaboration':
            if (claim['level'] not in {'explicit', 'inferred'} or
                    not set(claim['projects']) <= set(policy['collaboration_projects'])):
                _fail('scope_mismatch', 'Collaboration is Pein-specific and centrally bounded')
            if any(e['human'] != 'attested-Pein' for e in events.values()):
                _fail('human_attribution_required', 'Role, repetition and writing style are not Pein attribution')
            if active and claim['level'] == 'inferred' and not profile['allow_inferred']:
                _fail('pending_review', 'Inferred publication is disabled by policy')
        else:
            if claim['level'] in {'explicit', 'inferred'}:
                _fail('scope_mismatch', 'Personal preferences belong to the collaboration owner')
            if claim['level'] == 'recorded' and not any(e['evidence'] == 'owner' for e in events.values()):
                _fail('evidence_upgrade', 'Public Agent reports are not independently verified owner results')
            if claim['level'] != 'hypothesis' and any(d['level'] == 'hypothesis' for d in dependencies.values()):
                _fail('evidence_upgrade', 'A view cannot promote a hypothesis into a conclusion')
            if claim['level'] == 'recorded' and any(d['level'] == 'report' for d in dependencies.values()):
                _fail('evidence_upgrade', 'A reported claim cannot become recorded evidence through a view')
        if active:
            reviewed(claim, review)
        else:
            validate_review(review)
        return events, dependencies

    def mark_processed(self, run_id, generation, statuses):
        self._policy()
        if not isinstance(statuses, dict) or len(statuses) > 128:
            _fail('invalid_input', 'Expected a bounded event/status mapping')
        with self.store._gate():
            run = self._run(run_id, generation)
            if run['phase'] == 'closed':
                _fail('closed_run', 'Closed coverage cannot be rewritten')
            events = self._events(run)
            for key, status in statuses.items():
                if key not in events or status not in {'processed', 'excluded', 'no-signal', 'pending-review'}:
                    _fail('invalid_input', 'Coverage must identify frozen events and explicit processing states')
            run['processed'].update(statuses)
            self._save(run)
            return {'status': 'recorded', 'processed': run['processed']}

    def freeze(self, run_id, generation, operations, *, reconsider_reason=None):
        policy, profile = self._policy()
        if not isinstance(operations, list) or not 1 <= len(operations) <= profile['budgets']['operations']:
            _fail('draft_limit', 'Operations exceed the selected working-set bound')
        with self.store._gate():
            run = self._run(run_id, generation)
            if run['phase'] == 'closed' or len(run['drafts']) >= profile['budgets']['drafts']:
                _fail('draft_limit', 'Run is closed or has exhausted its frozen-draft budget')
            if run['current_draft']:
                previous = self._draft(run, run['current_draft'])
                outstanding = [o for o in previous['operations'] if o['key'] not in run['receipts']]
                if outstanding and not reconsider_reason:
                    _fail('incomplete_draft', 'Reconcile existing effects before an explicitly reviewed replacement draft')
                for op in outstanding:
                    if read_json(self.store, self._intent_path(run, op)) is not None:
                        _fail('unresolved_effect', 'A persisted intent must be reconciled before replacing the draft')
            if reconsider_reason is not None:
                _nonempty(reconsider_reason, 'reconsider_reason')
            self._check_budget(run)
            if len(run['drafts']) > profile['budgets']['repair_rounds']:
                _fail('draft_limit', 'The explicit repair-round budget is exhausted')
            ops = deepcopy(operations)
            ids = [o.get('id') for o in ops if isinstance(o, dict)]
            if len(ids) != len(ops) or any(not isinstance(x, str) or not SAFE_ID.fullmatch(x) for x in ids) or len(set(ids)) != len(ids):
                _fail('invalid_input', 'Operations need unique bounded IDs')
            serial = len(run['drafts']) + 1
            reserved = {o['id']: _digest([run_id, o['id']])[:32] for o in ops}
            resolved_refs = {}
            for op in ops:
                action = op.get('action')
                if not isinstance(action, str) or action not in ACTIONS:
                    _fail('invalid_input', 'Unsupported restricted operation')
                if action in {'record_approve', 'collaboration_publish'}:
                    target = op.get('record_id')
                    if not isinstance(target, str) or not RECORD_ID.fullmatch(target):
                        _fail('invalid_input', 'Publishing requires an existing canonical target')
                else:
                    target = reserved[op['id']]
                if not action.endswith('_withdraw') and action != 'view_publish':
                    resolved_refs['op:' + op['id']] = ('collaboration:' if action.startswith('collaboration_') else 'record:') + target
            allowed = {'id', 'action', 'claim', 'review', 'visibility', 'record_id', 'predecessors', 'view', 'claims', 'qualifier', 'expected_content_digest'}
            for op in ops:
                _keys(op, {'id', 'action'}, allowed, 'draft operation')
                if op['action'] not in ACTIONS:
                    _fail('invalid_input', 'Unsupported restricted operation')
                if op['action'] == 'record_approve':
                    if not isinstance(op.get('expected_content_digest'), str) or not re.fullmatch('[0-9a-f]{64}', op['expected_content_digest']):
                        _fail('invalid_input', 'Approval requires the exact audited expected_content_digest')
                elif 'expected_content_digest' in op:
                    _fail('invalid_input', 'expected_content_digest belongs only to record_approve')
                if op.get('visibility', 'active') not in {'active', 'candidate'}:
                    _fail('invalid_input', 'Visibility must be candidate or active')
                if op.get('visibility') == 'candidate' and op['action'] not in {'record_create', 'collaboration_create'}:
                    _fail('invalid_input', 'Only create operations can produce a candidate; publication always requires active admission')
                if 'record_id' in op and (not isinstance(op['record_id'], str) or not RECORD_ID.fullmatch(op['record_id'])):
                    _fail('invalid_input', 'Target must be a canonical record ID')
                bounded_strings(op.get('predecessors', []), 'predecessors')
                if any(not RECORD_ID.fullmatch(x) for x in op.get('predecessors', [])):
                    _fail('invalid_input', 'Invalid predecessor identity')
                if op['action'].startswith('record_'):
                    from .dream_records import operation_qualifier
                    op['qualifier'] = operation_qualifier(self.store, run['target'], op)
                elif 'qualifier' in op:
                    _fail('invalid_input', 'Canonical qualifiers only apply to research records')
                claims = op.get('claims', []) if op['action'] == 'view_publish' else [op['claim']] if 'claim' in op else []
                if op['action'] == 'view_publish' and (op.get('view') not in {'research', 'collaboration'} or not isinstance(claims, list) or not 1 <= len(claims) <= 32):
                    _fail('invalid_input', 'A view needs a bounded list of claim units')
                for claim in claims:
                    validate_claim(claim)
                    claim['refs'] = [resolved_refs.get(r, r) for r in claim['refs']]
                validate_review(op.get('review'))
                op['review']['checked_refs'] = [resolved_refs.get(r, r) for r in op['review']['checked_refs']]
                if op['action'] not in {'record_withdraw', 'collaboration_withdraw', 'view_publish'} and not claims:
                    _fail('invalid_input', 'This operation requires a semantic claim')
                if op['action'] in {'record_approve', 'record_withdraw', 'collaboration_publish', 'collaboration_withdraw'} and 'record_id' not in op:
                    _fail('invalid_input', 'This operation requires an existing canonical target')
                if op['action'] == 'view_publish':
                    pointer = read_json(self.store, f"dreaming/views/{run['target']}/{op['view']}/current.json")
                    op['expected_pointer'] = _digest(pointer)
                op.update(key=f'dream:{run_id}:{serial}:{op["id"]}', reserved_id=reserved[op['id']])
                op['digest'] = _digest(op)
            basis = self._basis(self._effective(run))
            draft = {'version': 1, 'run_id': run_id, 'serial': serial, 'operations': ops,
                     'basis': basis, 'source_revision': run['source_revision'],
                     'review_executor': self.caller, 'reconsider_reason': reconsider_reason}
            revision = _digest(draft)
            _put(self.store, f'dreaming/runs/{run_id}/drafts/{revision}.json', draft, immutable=True)
            run.update(current_draft=revision, phase='draft-ready', working_basis=basis, unresolved=[])
            run['drafts'].append(revision)
            self._save(run)
            return {'status': 'frozen', 'run_id': run_id, 'generation': generation, 'draft_revision': revision,
                    'operations': [{'id': o['id'], 'action': o['action'], 'reserved_id': o['reserved_id']} for o in ops]}

    def _draft(self, run, revision):
        if not isinstance(revision, str) or not re.fullmatch('[0-9a-f]{64}', revision):
            _fail('invalid_input', 'Expected an immutable draft revision')
        draft = read_json(self.store, f"dreaming/runs/{run['id']}/drafts/{revision}.json")
        if not draft or _digest(draft) != revision or draft['run_id'] != run['id']:
            _fail('corrupt_draft', 'Frozen draft integrity check failed')
        return draft

    def candidate_diff(self, run_id, revision):
        self._policy()
        with self.store._gate():
            run = self._run(run_id)
            draft = self._draft(run, revision)
            if (run['policy_revision'] != _digest(read_json(self.store, POLICY)) or
                    run['basis']['dispositions'] != _digest(dispositions(self.store)) or
                    draft['basis']['policy'] != _digest(read_json(self.store, POLICY)) or
                    draft['basis']['dispositions'] != _digest(dispositions(self.store))):
                return {'status': 'invalidated', 'operations': [], 'reason': 'Current policy/disposition differs; review source access again'}
            return {'status': 'draft', 'revision': revision, 'operations': draft['operations'],
                    'source_revision': draft['source_revision'], 'publication_is_not_truth': True}

    def _intent_path(self, run, operation):
        return f"dreaming/runs/{run['id']}/intents/{_digest(operation['key'])}.json"

    def _read_intent(self, run, operation):
        path = self._intent_path(run, operation)
        pointer = read_json(self.store, path)
        if pointer is None:
            return None
        revision = pointer.get('revision')
        if not isinstance(revision, str) or not re.fullmatch('[0-9a-f]{64}', revision):
            _fail('corrupt_intent', 'Intent pointer has an invalid immutable revision')
        intent = read_json(self.store, path[:-5] + '/' + revision + '.json')
        if intent is None or _digest(intent) != revision:
            _fail('corrupt_intent', 'Immutable intended effect failed its digest check')
        return intent

    def _save_intent(self, run, operation, intent):
        path = self._intent_path(run, operation)
        revision = _digest(intent)
        _put(self.store, path[:-5] + '/' + revision + '.json', intent, immutable=True)
        _put(self.store, path, {'version': 1, 'revision': revision})

    def _check_budget(self, run):
        from .core import _utc
        elapsed = (_utc(_now()) - _utc(run['created_at'])).total_seconds()
        if elapsed > run['profile_snapshot']['budgets']['seconds']:
            _fail('run_budget_exhausted', 'Run wall-clock budget exhausted; only observation/reconciliation is permitted')

    def _source_checks(self, run):
        from .dream_sources import check_snapshot
        _, profile = self._policy()
        specs = {s['id']: s for s in self._effective(run)['sources']}
        cost = sum((m.get('version') or {}).get('consumed', 0) - (m.get('version') or {}).get('start', 0) for m in run['materials'].values())
        with self.store._gate():
            current = self._run(run['id'], run['generation'])
            limit = min(profile['budgets']['source_bytes'], run['profile_snapshot']['budgets']['source_bytes'])
            if current.get('read_bytes', 0) + cost > limit:
                _fail('source_budget_exhausted', 'Cumulative source reading and verification exceeded this Run budget')
            current['read_bytes'] = current.get('read_bytes', 0) + cost
            self._save(current)
        return {sid: check_snapshot(specs[sid], material['version']) if sid in specs else 'forbidden'
                for sid, material in run['materials'].items()}

    def _effect(self, run, operation, source_checks):
        policy, profile = self._policy()
        if operation['action'] not in profile['actions']:
            _fail('action_denied', 'Action is not admitted by the trusted profile')
        if operation['action'] == 'view_publish':
            from .dream_views import prepare_view
            return prepare_view(self, run, operation, source_checks)
        scope = 'collaboration' if operation['action'].startswith('collaboration_') else 'research'
        if operation['action'].endswith('_withdraw'):
            review = operation['review']
            if review['decision'] != 'approve' or not review['scope_checked'] or not review['counterexamples_checked']:
                _fail('pending_review', 'Withdrawal requires explicit reviewed evidence')
            events, _ = self._refs(run, review['checked_refs'], scope=scope)
        else:
            active = operation.get('visibility', 'active') == 'active'
            if operation['action'] == 'collaboration_create' and operation['claim']['level'] == 'inferred':
                active = False
            events, _ = self._admit(run, operation['claim'], operation['review'], scope=scope, active=active)
        if operation['action'] == 'record_approve':
            current = next((r for r in projected_records(self.store, run['target']) if r['id'] == operation['record_id']), None)
            if not current or current['effective_status'] != 'candidate' or current.get('recall_retired'):
                _fail('stale_record', 'Approval requires a usable unchanged candidate')
            if current['content_digest'] != operation['expected_content_digest']:
                _fail('stale_record', 'Candidate content differs from the audited approval fence')
            if not record_use_filter(self.store)(current):
                _fail('source_forbidden', 'Original candidate sources are prohibited for reuse')
            checked, _ = self._refs(run, operation['review']['checked_refs'], scope=scope)
            source_specs = {s['id']: s for s in self._effective(run)['sources']}
            for original in current['sources']:
                original_identity = _source_keys(['source-uri:' + original['uri']])
                matching = [event for event in checked.values()
                            if original_identity.intersection(_source_keys(['source-uri:' + Path(source_specs[event['source_id']]['path']).as_uri()]))
                            and (not original.get('locator') or original['locator'] in {event.get('locator'), str(event['event_id'])})]
                if not matching:
                    _fail('unverifiable_source', 'Every original candidate source requires authorized frozen evidence in checked refs')
                events.update({event['key']: event for event in matching})
        if not events:
            _fail('unverifiable_source', 'Publication requires source evidence')
        if any(source_checks.get(e['source_id']) != 'valid' for e in events.values()):
            _fail('stale_source', 'A source snapshot is changed, missing or inaccessible; re-read its owner')
        specs = {s['id']: s for s in self._effective(run)['sources']}
        uris = [{'uri': Path(specs[e['source_id']]['path']).as_uri(),
                 'locator': e.get('locator', str(e['event_id'])),
                 'note': 'dream-source-v1:' + _json({'profile': self.profile_id, 'source_id': e['source_id'],
                                                   'event_key': e['key'], 'lineage': e.get('lineage', []),
                                                   'source_grant': _digest(compact_source_spec(specs[e['source_id']])),
                                                   'source_spec': compact_source_spec(specs[e['source_id']]),
                                                   'claim_level': operation.get('claim', {}).get('level')})}
                for e in events.values()]
        uris = list({_digest(s): s for s in uris}.values())
        if scope == 'collaboration':
            existing = {r['id']: r for r in collaboration(self.store)}
            touched = operation.get('predecessors', []) + ([operation['record_id']] if 'record_id' in operation else [])
            for identifier in touched:
                record = existing.get(identifier)
                if not record or run['target'] not in set(policy['collaboration_projects']).intersection(record['claim']['projects']):
                    _fail('scope_mismatch', 'A collaboration target or predecessor is outside this profile target')
            relative, data = collaboration_effect(self.store, operation, self.caller, source_uris=uris)
        else:
            relative, data = core_effect(self.store, run['target'], operation, self.caller, uris)
        return [(relative, data)]

    def _fault(self, boundary, operation):
        """A deterministic integration-test injection seam; production is a no-op."""

    def _completed_write(self, run, operation, write):
        path = safe_path(self.store, write['path'])
        if not path.is_file():
            return False
        if hashlib.sha256(path.read_bytes()).hexdigest() == write['sha256']:
            return True
        if operation['action'] != 'record_create' or operation.get('visibility', 'active') != 'candidate':
            return False
        # Normal promotion changes lifecycle fields, but preserves the complete
        # proposal and original author. A content digest alone cannot prove this effect.
        planned = parse_markdown(write['data'].encode('utf-8'))
        current = next((r for r in self.store._load(run['target']) if r['id'] == planned['id']), None)
        if not current or planned['status'] != 'candidate' or current['status'] != 'active':
            return False
        lifecycle = {'status', 'review', 'promotion', 'supersedes'}
        return ({k: v for k, v in current.items() if k not in lifecycle} ==
                {k: v for k, v in planned.items() if k not in lifecycle})

    def _apply_one(self, run_id, generation, revision, operation_id, source_checks):
        with self.store._gate():
            run = self._run(run_id, generation)
            if run['phase'] == 'closed' or run['current_draft'] != revision:
                _fail('stale_draft', 'Only the current frozen draft can apply effects')
            draft = self._draft(run, revision)
            operation = next(o for o in draft['operations'] if o['id'] == operation_id)
            if operation['digest'] != _digest({k: v for k, v in operation.items() if k != 'digest'}):
                _fail('corrupt_draft', 'Semantic operation binding failed')
            key = operation['key']
            if key in run['receipts']:
                return {**run['receipts'][key], 'replayed': True}
            policy, profile = self._policy()
            intent = self._read_intent(run, operation)
            if intent is not None:
                if intent['operation_digest'] != operation['digest'] or intent['key'] != key:
                    _fail('unresolved_effect', 'Persisted intent has a different semantic identity')
                complete = all(self._completed_write(run, operation, w) for w in intent['writes'])
            else:
                complete = False
            if not complete:
                if self._basis(self._effective(run)) != run['working_basis']:
                    _fail('stale_basis', 'Canonical namespace, policy, registry or disposition changed after review')
                if draft['basis']['policy'] != _digest(policy):
                    _fail('stale_policy', 'Frozen draft policy is no longer current')
                self._check_budget(run)
                if '_failure' in source_checks:
                    _fail(source_checks['_failure'], 'Source revalidation budget unavailable; completed effects remain recoverable')
                effects = self._effect(run, operation, source_checks)
                if intent is not None and intent['executor'] != self.caller:
                    actual = []
                    for write in intent['writes']:
                        path = safe_path(self.store, write['path'])
                        actual.append(hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else 'absent')
                    if all(digest == write['before_sha256'] for digest, write in zip(actual, intent['writes'])):
                        # No effect exists. Preserve the old immutable intent but
                        # prepare the unfinished operation under the new real executor.
                        intent = None
                    elif operation['action'] == 'view_publish':
                        continued = deepcopy(intent)
                        continued['continued_by'] = self.caller
                        for digest, write in zip(actual, continued['writes']):
                            if digest == write['sha256']:
                                continue
                            if digest != write['before_sha256'] or not write['path'].endswith('/current.json'):
                                _fail('unresolved_effect', 'A partially applied view has an ambiguous effect')
                            pointer = _decode(write['data'])
                            pointer['activated_by'] = self.caller
                            write['data'] = _json(pointer) + '\n'
                            write['sha256'] = hashlib.sha256(write['data'].encode()).hexdigest()
                        intent = continued
                        self._save_intent(run, operation, intent)
                if intent is None:
                    writes, after = [], deepcopy(run['working_basis'])
                    for relative, data in effects:
                        path = safe_path(self.store, relative)
                        if len(data) > MAX_RECORD_BYTES:
                            _fail('dream_limit', 'Canonical effect exceeds its byte bound')
                        before_sha = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else 'absent'
                        if operation['action'] in {'record_create', 'record_supersede', 'record_withdraw', 'collaboration_create'} and before_sha != 'absent':
                            _fail('id_collision', 'Reserved ID already exists; no canonical record is replaced')
                        sha = hashlib.sha256(data).hexdigest()
                        writes.append({'path': relative, 'before_sha256': before_sha, 'sha256': sha, 'data': data.decode('utf-8')})
                        if relative.startswith(('records/', 'curation/', 'collaboration/')):
                            after['namespace'][relative] = sha
                    intent = {'version': 1, 'key': key, 'operation_digest': operation['digest'],
                              'executor': self.caller, 'writes': writes,
                              'before_basis': run['working_basis'], 'after_basis': after}
                    self._save_intent(run, operation, intent)
                    self._fault('intent-saved', operation)
                for index, write in enumerate(intent['writes']):
                    path = safe_path(self.store, write['path'])
                    current = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else 'absent'
                    if current == write['sha256']:
                        continue
                    if current != write['before_sha256']:
                        _fail('unresolved_effect', 'Canonical output is neither the fenced predecessor nor the intended effect')
                    data = write['data'].encode('utf-8')
                    if hashlib.sha256(data).hexdigest() != write['sha256']:
                        _fail('corrupt_intent', 'Intended effect bytes failed integrity validation')
                    if write['path'].startswith('records/'):
                        record = parse_markdown(data)
                        self.store._validate_canonical({k: v for k, v in record.items() if k != 'body'},
                                                       record['body'], path, run['target'])
                        self.store._write(record, create=write['before_sha256'] == 'absent')
                    else:
                        self.store._publish(path, data)
                    self._fault(f'effect-{index}-written', operation)
            # The immutable intended bytes include canonical operation identity and
            # original executor. Receipts are only an acknowledgement of that effect.
            receipt = {'operation_id': operation_id, 'operation_digest': operation['digest'],
                       'paths': [w['path'] for w in intent['writes']], 'executor': intent['executor'],
                       'acknowledged_by': self.caller, 'replayed': complete}
            run['receipts'][key] = receipt
            # Advance ONLY the effects this intent proves; never absorb other writers.
            run['working_basis'] = intent['after_basis']
            run['phase'] = 'applying'
            self._save(run)
            self._fault('receipt-written', operation)
            return receipt

    def publish(self, run_id, generation, revision):
        if not self.publisher:
            _fail('advisory_only', 'This endpoint can draft only; use a separately bound trusted publisher')
        self._policy()
        with self.store._gate():
            run = self._run(run_id, generation)
            draft = self._draft(run, revision)
        # Already acknowledged operations require no source reread. Unknown
        # effects still reconcile from their immutable canonical evidence.
        pending = any(o['key'] not in run['receipts'] for o in draft['operations'])
        try:
            source_checks = self._source_checks(run) if pending else {}
        except MemoryError as exc:
            source_checks = {'_failure': exc.code}
        outcomes, errors = [], []
        for operation in draft['operations']:
            try:
                outcomes.append(self._apply_one(run_id, generation, revision, operation['id'], source_checks))
            except MemoryError as exc:
                errors.append({'operation_id': operation['id'], 'code': exc.code, 'reason': str(exc)})
                if exc.code in {'stale_attempt', 'attempt_identity_mismatch', 'stale_draft'}:
                    raise
        with self.store._gate():
            run = self._run(run_id, generation)
            if run['current_draft'] != revision:
                _fail('stale_draft', 'A concurrent review selected another draft')
            run['unresolved'] = errors
            status = 'partial' if errors and outcomes else 'blocked' if errors else 'applied'
            run.update(phase=status, technical_outcome='ok' if not errors else status)
            self._save(run)
        return {'status': status, 'applied': outcomes, 'unresolved': errors,
                'scientific_validation': 'not implied by publication'}

    def close(self, run_id, generation, *, abandon_reason=None):
        _, profile = self._policy()
        with self.store._gate():
            run = self._run(run_id, generation)
            if run['phase'] == 'closed':
                if run.get('checkpoint') and self._basis(self._effective(run)) == run['working_basis']:
                    _put(self.store, f'dreaming/checkpoints/{self.profile_id}-{run["lane"]}.json', run['checkpoint'])
                return {'status': 'closed', 'replayed': True, 'run_id': run_id}
            outstanding = []
            if run['current_draft']:
                outstanding = [o for o in self._draft(run, run['current_draft'])['operations'] if o['key'] not in run['receipts']]
            if outstanding and not abandon_reason:
                _fail('incomplete_draft', 'Unresolved operations require continuation or explicit partial close')
            for operation in outstanding:
                intent = self._read_intent(run, operation)
                if intent is None:
                    continue
                for write in intent['writes']:
                    path = safe_path(self.store, write['path'])
                    actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else 'absent'
                    if actual == write['before_sha256']:
                        continue
                    if operation['action'] == 'view_publish' and '/revisions/' in write['path'] and actual == write['sha256']:
                        continue  # An unactivated immutable revision is not a visible claim.
                    _fail('unresolved_effect', 'A visible or ambiguous effect must be reconciled before abandonment')
            if abandon_reason:
                _nonempty(abandon_reason, 'abandon_reason')
            current_basis = self._basis(self._effective(run))
            basis_changed = current_basis != run['working_basis']
            if not outstanding and basis_changed and not abandon_reason:
                _fail('stale_basis', 'External changes require review or explicit partial close without a no-change checkpoint')
            missing = set(self._events(run)) - set(run['processed'])
            pending = sum(s == 'pending-review' for s in run['processed'].values())
            if missing:
                run['coverage'] = 'partial'
            run.update(phase='closed', closed_at=_now(), pending_review=pending,
                       technical_outcome='partial' if outstanding or basis_changed else 'ok', abandon_reason=abandon_reason)
            if not outstanding and not basis_changed:
                run['checkpoint'] = {'version': 1, 'run_id': run_id, 'coverage': run['coverage'], 'pending_review': pending,
                                     'fingerprint': _digest({'sources': run['source_revision'], 'basis': current_basis}),
                                     'source_versions': {k: v['version'] for k, v in run['materials'].items()},
                                     'unprocessed_events': len(missing)}
            self._save(run)
            self._fault('run-closed', {'id': 'close'})
            if run.get('checkpoint'):
                _put(self.store, f'dreaming/checkpoints/{self.profile_id}-{run["lane"]}.json', run['checkpoint'])
            return {'status': 'closed', 'run_id': run_id, 'coverage': run['coverage'],
                    'pending_review': pending, 'unprocessed_events': len(missing), 'partial': bool(outstanding or basis_changed)}

    def overview(self, view, *, scenario, max_chars=None, max_bytes=None, historical=None, target_project=None):
        from .dream_views import read_view
        return read_view(self, view, scenario=scenario, max_chars=max_chars,
                         max_bytes=max_bytes, historical=historical, target_project=target_project)

    def suggest_issue(self, run_id, generation, *, topic, relation, note, observations, semantic_reviewed=False):
        self._policy()
        for value in (topic, relation, note):
            _nonempty(value, 'issue text')
            if len(value) > 4096:
                _fail('dream_limit', 'Issue text exceeds its bound')
        if not isinstance(observations, dict) or len(_json(observations)) > 8192 or type(semantic_reviewed) is not bool:
            _fail('invalid_input', 'Invalid bounded issue observation')
        with self.store._gate():
            run = self._run(run_id, generation)
            identity = _digest([run['target'], topic, relation])
            if run['phase'] == 'closed':
                _fail('closed_run', 'Closed Runs cannot accept new issues')
            self._check_budget(run)
            relative = f'dreaming/issues/{identity}.json'
            prior = read_json(self.store, relative)
            semantic = _digest(' '.join(note.split()))
            changed = prior is None or prior['semantic_digest'] != semantic
            notify = semantic_reviewed and (prior is None or prior.get('last_notified_digest') != semantic)
            item = {'id': identity, 'topic': topic, 'relation': relation, 'note': note,
                    'observations': observations, 'notify': notify,
                    'needs_semantic_review': not semantic_reviewed and (changed or prior.get('observations') != observations if prior else True)}
            run['issues'] = [x for x in run['issues'] if x['id'] != identity] + [item]
            self._save(run)
            _put(self.store, relative, {'last_run': run_id, 'semantic_digest': semantic,
                                       'last_notified_digest': semantic if notify else (prior or {}).get('last_notified_digest'),
                                       'observations': observations})
            return item
