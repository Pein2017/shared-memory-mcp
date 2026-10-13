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
from .dream_sources import check_snapshot, read_source, validate_source

POLICY = 'dreaming/policy.json'
DISPOSITIONS = 'dreaming/dispositions.json'
BUDGET_KEYS = {'source_bytes', 'events', 'operations', 'drafts', 'view_chars', 'view_bytes',
               'model_calls', 'input_tokens', 'output_tokens', 'seconds', 'repair_rounds'}
# Only these invocation bounds are enforced; drafts, seconds, repair_rounds, view_chars and
# view_bytes remain validated historical policy fields that gate nothing.
INVOCATION_BUDGET_KEYS = {'source_bytes', 'events', 'operations'}
REVIEWED_STATES = {'processed', 'excluded', 'no-signal'}


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
          {'version', 'subject', 'collaboration_projects', 'profiles', 'bindings'}, 'dream policy')
    if policy['version'] not in {2, 3} or policy['subject'] != 'Pein':
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
        _keys(profile, fields, fields | {'reader_projects', 'read_access', 'history_roots'}, 'dream profile')
        if profile.get('read_access', 'granted') not in {'granted', 'inherited'}:
            _fail('invalid_policy', 'Unsupported trusted source read boundary')
        roots = profile.get('history_roots', [])
        if not isinstance(roots, list) or len(roots) > 16:
            _fail('invalid_policy', 'History discovery roots must be a bounded list')
        for root in roots:
            _keys(root, {'path', 'format', 'schema'}, {'path', 'format', 'schema', 'native_version', 'native_versions'}, 'history root')
            if profile.get('read_access') != 'inherited' or root['format'] not in {'codex', 'pi', 'claude'}:
                _fail('invalid_policy', 'Native history discovery requires trusted inherited reads')
            validate_source({'id': 'history-discovery', **root})
        if 'reader_projects' in profile:
            bounded_strings(profile['reader_projects'], 'reader_projects')
            if not set(profile['reader_projects']) <= projects:
                _fail('invalid_policy', 'Reader projects must be explicitly registered')
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
        # Prefix verification streams whole transcripts (largest Pi sessions ~90 MiB); pages stay capped at 8 MiB.
        caps = {'source_bytes': 256 * 1048576, 'events': 128, 'operations': 32, 'drafts': 8,
                'view_chars': 16000, 'view_bytes': 64000, 'seconds': 86400, 'repair_rounds': 8}
        if any(not 1 <= profile['budgets'][k] <= cap for k, cap in caps.items()):
            _fail('invalid_policy', 'A local resource budget exceeds its supported bound')
        from .dream_catalog import validate_source_grants
        validate_source_grants(store, profile['source_grants'])
    bindings = policy.get('bindings', {})
    if policy['version'] == 3 and not bindings:
        _fail('invalid_policy', 'Version 3 requires explicit stable project bindings')
    if (not isinstance(bindings, dict) or len(bindings) > 256 or
            any(key not in projects or not isinstance(value, str) or value not in policy['profiles'] for key, value in bindings.items())):
        _fail('invalid_policy', 'Bindings must identify registered projects and existing policy profiles')
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
                if not SourceCatalog(store, binding['profile'], profile).authorized(spec, require_available=False) or binding.get('source_grant') != _digest(spec):
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
    def __init__(self, store, profile_id, caller, *, publisher=False, caller_binding='operator-bound'):
        if caller_binding not in {'operator-bound', 'caller-declared'}:
            _fail('invalid_input', 'Unsupported caller binding')
        self.identity_assurance = caller_binding + '; native-session-unverified'
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
            # Exact lane names: profile `a` must not read profile `a-b` lanes.
            lane = re.compile(re.escape(self.profile_id) + '-[0-9a-f]{64}\\.json')
            paths = sorted(p for p in safe_path(self.store, 'dreaming/active').glob('*.json') if lane.fullmatch(p.name))
            if len(paths) > MAX_RECORDS:
                _fail('dream_limit', 'Active lane inventory exceeds its supported bound')
            for path in paths:
                active = read_json(self.store, path.relative_to(self.store.root))
                run = read_json(self.store, f"dreaming/runs/{active['run_id']}/run.json")
                if not run or run['phase'] == 'closed':
                    continue  # A stale marker of a closed or removed run is not a live lane.
                if run['profile_id'] != self.profile_id:
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
            grant_fields = {'id', 'path', 'kind', 'format', 'schema', 'native_version', 'native_versions', 'leaf_id', 'derived'}
            return {'profile_id': self.profile_id, 'target_projects': profile['target_projects'],
                    'source_grants': [{k: deepcopy(v) for k, v in grant.items() if k in grant_fields} for grant in profile['source_grants']],
                    'actions': profile['actions'], 'publisher': self.publisher, 'active_runs': selected,
                    'revision': revision, 'next_cursor': next_cursor,
                    'read_access': profile.get('read_access', 'granted'),
                    'history_roots': deepcopy(profile.get('history_roots', []))}

    def source_list(self, grant_id, *, relative_dir='', cursor=None, limit=50):
        return self._catalog().list(grant_id, relative_dir=relative_dir, cursor=cursor, limit=limit)

    def source_read(self, selection, *, cursor=None, max_bytes=262144, max_events=128):
        result = self._catalog().read(selection, cursor=cursor, max_bytes=max_bytes, max_events=max_events)
        result.pop('tail_cursor', None)  # Internal objective continuation, not a caller capability.
        return result

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

    def _operation_basis(self, run, operation, created_refs=()):
        """Fence the reviewed inputs and target, leaving unrelated writers independent."""
        policy, profile = self._policy()
        claims = operation.get('claims', []) if operation['action'] == 'view_publish' else [operation['claim']] if 'claim' in operation else []
        refs = set(operation['review']['checked_refs']) | {r for c in claims for r in c['refs']}
        prefix = 'collaboration:' if operation['action'].startswith('collaboration_') else 'record:'
        refs.update(prefix + r for r in operation.get('predecessors', []))
        if operation.get('record_id'):
            refs.add(prefix + operation['record_id'])
        records = {'record:' + r['id']: r for r in projected_records(self.store, run['target'])}
        records.update({'collaboration:' + r['id']: r for r in collaboration(self.store)})
        events = self._events(run)
        selected = {events[r]['source_id'] for r in refs if r in events}
        originals = {s['id']: s for s in run['profile_snapshot']['sources'] if s['id'] in selected}
        current = {s['id']: s for s in self._effective(run)['sources'] if s['id'] in selected}
        topics = {c['topic'] for c in claims} | {records[r]['title'] for r in refs if r in records and r.startswith('record:')}
        scope = operation.get('view', 'collaboration' if prefix == 'collaboration:' else 'research')
        registry = {p['id']: p for p in self.store._registry()['projects']}
        executor = self.store._resolve(self.caller)['project_id']
        source_uris = {Path(originals[s]['path']).as_uri() for s in originals}
        source_uris.update(s['uri'] for r in refs if r in records for s in records[r]['sources'])
        return {'records': {r: _digest(records.get(r)) for r in sorted(refs) if r.startswith(('record:', 'collaboration:')) and r not in created_refs},
                'targets': {prefix + r: _digest(records.get(prefix + r)) for r in
                            [*operation.get('predecessors', []), *([operation['record_id']] if operation.get('record_id') else [])]},
                'related_records': {r: _digest(v) for r, v in records.items() if r not in created_refs and
                                    (v.get('title') in topics or source_uris.intersection(s['uri'] for s in v['sources']))},
                'sources': _digest(current) if current == originals else 'access-changed',
                'policy': {'version': policy['version'], 'subject': policy['subject'],
                           'target_allowed': run['target'] in profile['target_projects'],
                           'executor_allowed': executor in profile['executor_projects'],
                           'action_allowed': operation['action'] in profile['actions'],
                           'scenarios': sorted({s for c in claims for s in c['scenarios']}.intersection(profile['scenarios'])),
                           'collaboration': sorted({p for c in claims for p in c['projects']}.intersection(policy['collaboration_projects'])) if scope == 'collaboration' else None,
                           'allow_inferred': profile['allow_inferred'] if any(c['level'] == 'inferred' for c in claims) else None},
                'registry': {p: registry.get(p) for p in {run['target'], executor}},
                'dispositions': _digest([d for d in dispositions(self.store)['items'] if d['target'] == run['target'] and d['scope'] == scope and d['topic'] in topics | {'*'}])}

    def _progress(self, run):
        from .dream_incremental import load_objective
        value = run.get('objective_progress')
        return load_objective(self.store, value) if value else None

    def _memory_inputs(self, target, policy):
        items = {'record:' + r['id']: r for r in projected_records(self.store, target)}
        items.update({'collaboration:' + r['id']: r for r in collaboration(self.store)
                      if target in set(policy['collaboration_projects']).intersection(r['claim']['projects'])})
        return {ref: {'revision': _digest(record)} for ref, record in items.items()}

    def _increment(self, catalog, progress, memory_inputs):
        """A completed cutoff may start another increment; open cutoffs stay fixed."""
        from .dream_incremental import objective_inventory
        progress = deepcopy(progress)
        progress['inventory_complete'] = False
        progress = objective_inventory(catalog, progress['review_objective'], previous=progress,
                                       binding=progress['binding'])
        for entry in progress['sources'].values():
            try:
                stat = Path(entry['path']).stat()
                epoch = [stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns]
                if entry.get('epoch') == epoch:
                    continue
                frozen = catalog.freeze({k: v for k, v in entry['selection'].items() if k not in {'cutoff', 'page'}})
                appended = (entry.get('tail_cursor') and entry['status'] == 'processed' and frozen['identity'] == entry['identity']
                            and entry['reviewed_offset'] == entry['cutoff'] < frozen['selection']['cutoff'])
                # Same file grown past a fully reviewed cutoff: only the suffix becomes pending; the read
                # verifies the reviewed prefix digest and falls back to a full re-review if it changed.
                entry.update(selection=frozen['selection'], cutoff=frozen['selection']['cutoff'],
                             identity=frozen['identity'], epoch=frozen.get('epoch'),
                             deferred_bytes=frozen['deferred_bytes'],
                             reviewed_offset=entry['reviewed_offset'] if appended else 0,
                             cursor=entry['tail_cursor'] if appended else None, tail_cursor=None,
                             appended=bool(appended), pending_page=None, status='pending', gaps=[])
            except (MemoryError, OSError) as exc:
                if entry['status'] != 'gap-accepted':  # An accepted whole-source gap stays closed until it reappears.
                    entry.update(status='pending', gaps=[{'reason': getattr(exc, 'code', 'source_unavailable')}])
        for ref, supplied in memory_inputs.items():
            prior = progress['memory'].get(ref)
            if not prior or prior['revision'] != supplied['revision']:
                progress['memory'][ref] = {**supplied, 'status': 'pending'}
        return progress

    def _baseline(self, target, previous):
        """Target-keyed reviewed positions: the lane's last durable Run, merged once with legacy
        objective-keyed checkpoints of the same target (minimum position wins; nothing advances)."""
        from .dream_incremental import merge_positions
        base = self._progress(previous) if previous and previous.get('objective_progress') else None
        if base is not None and base.get('target_keyed'):
            return base
        found = [base] if base else []
        legacy = re.compile(re.escape(self.profile_id) + '-[0-9a-f]{64}-objective\\.json')
        for path in sorted(safe_path(self.store, 'dreaming/checkpoints').glob('*-objective.json')):
            index = read_json(self.store, path.relative_to(self.store.root)) if legacy.fullmatch(path.name) else None
            run_id = index.get('run_id') if isinstance(index, dict) else None
            if not isinstance(run_id, str) or not RECORD_ID.fullmatch(run_id) or run_id == (previous or {}).get('id'):
                continue
            run = read_json(self.store, f'dreaming/runs/{run_id}/run.json')
            if not run or run.get('target') != target or run.get('profile_id') != self.profile_id or not run.get('objective_progress'):
                continue
            try:
                found.append(self._progress(run))
            except MemoryError:
                continue  # An unreadable legacy shard contributes no position; its material stays pending.
        return merge_positions(found) if found else None

    def start(self, *, target_project=None, sources=None, reconsider=None, review_objective=None, default_objective=False):
        if default_objective:
            from .dream_incremental import DEFAULT_OBJECTIVE
            if review_objective is not None:
                _fail('invalid_objective', 'Choose an explicit review_objective or the default objective')
            review_objective = deepcopy(DEFAULT_OBJECTIVE)
        if review_objective is not None:
            _keys(review_objective, {'id', 'question'}, {'id', 'question', 'reread'}, 'review objective')
            if (not isinstance(review_objective['id'], str) or not SAFE_ID.fullmatch(review_objective['id']) or
                    not isinstance(review_objective['question'], str) or not review_objective['question'].strip() or
                    len(review_objective['question']) > 2048):
                _fail('invalid_objective', 'A review objective needs a stable id and bounded question')
            reread = review_objective.get('reread', [None])
            if not isinstance(reread, list) or not 1 <= len(reread) <= 16 or 'reread' in review_objective and any(
                    not isinstance(i, dict) or set(i) != {'source_id', 'range'} or not isinstance(i['source_id'], str) or
                    not isinstance(i['range'], list) or len(i['range']) != 2 or any(type(x) is not int for x in i['range']) or
                    not 0 <= i['range'][0] < i['range'][1] for i in reread):
                _fail('invalid_objective', 'reread is a list of at most sixteen {source_id, range: [start, end]} byte ranges')
        question = lambda objective: {k: objective[k] for k in ('id', 'question')} if objective else None
        policy, profile = self._policy()
        target = self._target(profile, target_project)
        catalog = self._catalog(profile)
        profile = {**profile, 'target_project': target}
        lane = _digest({'profile': self.profile_id, 'target': target, 'objective_lane': True}) if review_objective else _digest(
            {'profile': self.profile_id, 'target': target, 'sources': catalog.resolve(sources)})
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
            objective_path = f'dreaming/checkpoints/{self.profile_id}-{_digest([target, review_objective["id"]])}-objective.json' if review_objective else None
            if objective_path:
                # Reviewed positions are keyed by target (the lane checkpoint); an objective identity
                # keeps its question text, so a changed question needs a new identity.
                index = read_json(self.store, objective_path)
                indexed = read_json(self.store, f"dreaming/runs/{index['run_id']}/run.json") if (
                    isinstance(index, dict) and isinstance(index.get('run_id'), str) and RECORD_ID.fullmatch(index['run_id'])) else None
                if indexed and question(indexed.get('review_objective')) not in (None, question(review_objective)):
                    _fail('objective_conflict', 'Changed objective text needs a new objective identity')
        old_objective = previous.get('review_objective') if previous else None
        if review_objective is None and old_objective is not None:
            review_objective = deepcopy(old_objective)
        if (review_objective and old_objective and review_objective['id'] == old_objective['id'] and
                question(review_objective) != question(old_objective)):
            _fail('objective_conflict', 'Changed objective text needs a new objective identity')
        same_objective = review_objective == old_objective and not default_objective
        progress, memory_inputs, staging_bytes, inventory = None, {}, 0, None
        if review_objective:
            from .dream_incremental import (apply_reread, default_inventory, objective_batch, objective_inventory,
                                            objective_observe, rebase, _in_scope)
            with self.store._gate():
                memory_inputs = self._memory_inputs(target, policy)
                base = self._baseline(target, previous)
                if default_objective:
                    inventory = default_inventory(self.store, target, base['memory'] if base else {})
            if base is not None and not base.get('target_keyed'):
                same_objective = False  # A one-time legacy merge starts a fresh objective over merged positions.
            if default_objective:
                # Memory triage only: carried source positions stay out of scope, so no native history is read.
                scope = {'sources': [s['id'] for s in catalog.resolve(sources)] if sources else [], 'memory': inventory['refs']}
                memory_inputs = {r: memory_inputs[r] for r in inventory['refs'] if r in memory_inputs}
                progress = rebase(base, review_objective, scope=scope) if base else None
                for ref, supplied in memory_inputs.items():
                    if progress and ref in progress['memory'] and progress['memory'][ref]['revision'] != supplied['revision']:
                        progress['memory'][ref] = {**supplied, 'status': 'pending'}
            elif same_objective:
                progress = base
                if progress and checkpoint and checkpoint.get('objective_completion') in {'reviewed', 'disposed'}:
                    progress = self._increment(catalog, progress, memory_inputs)
            elif base is not None:
                progress = self._increment(catalog, rebase(base, review_objective), memory_inputs)
            inputs = [{'ref': r, **v} for r, v in memory_inputs.items() if not progress or r not in progress['memory']]
            progress = objective_inventory(catalog, review_objective, previous=progress,
                                           selections=[] if default_objective and sources is None else sources,
                                           memory_refs=inputs, binding={'profile': self.profile_id, 'target': target})
            if default_objective:
                progress['scope'] = scope
            if review_objective.get('reread') and not same_objective:
                apply_reread(progress, review_objective['reread'])
            progress['target_keyed'] = True
            progress, selections = objective_batch(catalog, progress, profile['budgets'])
            staging_bytes = progress['batch_read_bytes']
            profile['sources'] = catalog.resolve(selections)
            # Only pending memory is this batch's input; reviewed records at their reviewed revision stay settled.
            memory_inputs = {r: {'revision': v['revision']} for r, v in progress['memory'].items()
                             if _in_scope(progress, 'memory', r) and v['status'] not in REVIEWED_STATES}
        else:
            profile['sources'] = catalog.resolve(sources)
        materials, processed, read_bytes = self._collect(profile, previous if same_objective and not progress else None,
                                                       reconsider=bool(reconsider))
        read_bytes += staging_bytes
        if progress and previous and same_objective:
            keys = {e['key'] for m in materials.values() for e in m['events']} | set(memory_inputs)
            processed.update({k: v for k, v in previous['processed'].items() if k in keys and
                              (k not in memory_inputs or previous.get('memory_inputs', {}).get(k) == memory_inputs[k])})
        source_revision = _digest({k: v['version'] for k, v in materials.items()})
        source_changes = 'unchanged' if previous and previous['source_revision'] == source_revision else 'changed' if previous else 'initial'
        objective_complete = bool(checkpoint and checkpoint.get('objective_completion') in {'reviewed', 'disposed'})
        if review_objective is None:
            objective_complete = True  # Preserve the pre-objective historical replay contract.
        with self.store._gate():
            current_policy, current_profile = self._policy()
            if _digest(current_policy) != _digest(policy):
                _fail('stale_policy', 'Policy changed during source collection')
            active = read_json(self.store, active_path)
            if active and self._run(active['run_id'], check_caller=False)['phase'] != 'closed':
                return {'status': 'resume-required', 'run_id': active['run_id'], 'model_required': False}
            basis = self._basis(profile)
            fingerprint = _digest({'sources': source_revision, 'basis': basis})
            if (progress and checkpoint and same_objective and objective_complete and not reconsider and
                    objective_observe(progress)['objective_completion'] == 'reviewable-complete'):
                return {'status': 'no-change', 'model_required': False, 'checkpoint': checkpoint,
                        'review_objective': review_objective, 'objective_completion': checkpoint['objective_completion'],
                        'objective_progress': objective_observe(progress), 'source_changes': 'unchanged',
                        'pending_review': 0, 'unresolved_effects': 0}
            if (checkpoint and same_objective and objective_complete and checkpoint['fingerprint'] == fingerprint and not reconsider and
                    not checkpoint.get('unprocessed_events') and not checkpoint.get('pending_review')):
                unchecked = [sid for sid, m in materials.items() if not m.get('snapshot_checked')]
                if unchecked:
                    return {'status': 'blocked', 'model_required': False, 'coverage': 'partial',
                            'reason': 'Some sources could not be reverified within budget; this is not no-change',
                            'unchecked_sources': unchecked}
                return {'status': 'no-change', 'model_required': False, 'checkpoint': checkpoint,
                        'source_changes': 'unchanged', 'review_objective': review_objective,
                        'objective_completion': checkpoint.get('objective_completion', 'legacy-processing-complete'),
                        'pending_review': 0, 'unresolved_effects': 0}
            if reconsider is not None:
                _nonempty(reconsider, 'reconsider reason')
            run_id = uuid.uuid4().hex
            run = {'version': 1, 'id': run_id, 'profile_id': self.profile_id,
                   'target': target, 'lane': lane, 'generation': 1,
                   'attempts': [{'generation': 1, 'caller': self.caller, 'at': _now(),
                                 'identity_assurance': self.identity_assurance}],
                   'phase': 'collecting', 'technical_outcome': 'pending', 'created_at': _now(),
                   'profile_snapshot': profile, 'policy_revision': _digest(policy),
                   'basis': basis, 'working_basis': deepcopy(basis), 'source_revision': source_revision,
                   'materials': materials, 'coverage': 'complete' if all(x['coverage']['complete'] for x in materials.values()) else 'partial',
                   'processed': processed, 'drafts': [], 'current_draft': None, 'receipts': {}, 'unresolved': [],
                   'issues': [], 'reconsider': reconsider, 'model_calls': 0, 'read_bytes': read_bytes,
                   'previous_run': previous['id'] if previous else None,
                   'review_objective': deepcopy(review_objective), 'objective_completion': 'pending',
                   'source_changes': source_changes}
            if progress:
                from .dream_incremental import save_objective
                run.update(objective_progress=save_objective(self.store, progress), memory_inputs=memory_inputs,
                           objective_path=objective_path)
            if inventory is not None:
                run['memory_order'] = [r for r in inventory['refs'] if r in memory_inputs]
            self._save(run)
            _put(self.store, active_path, {'run_id': run_id})
            return {'status': 'created', 'run_id': run_id, 'generation': 1, 'coverage': run['coverage'],
                    'model_required': True, 'execution_mode': 'external-publisher' if self.publisher else 'advisory-draft-only',
                    'provider': profile['provider'], 'transport': profile['transport'],
                    'budgets': {k: v for k, v in profile['budgets'].items() if k in INVOCATION_BUDGET_KEYS},
                    'review_objective': deepcopy(review_objective), 'objective_completion': 'pending',
                    'pending_review': sum(value == 'pending-review' for value in processed.values()),
                    'unresolved_effects': 0, 'source_changes': source_changes,
                    **({'objective_progress': objective_observe(progress)} if progress else {}),
                    **({'inventory': inventory} if inventory is not None else {})}

    def inspect(self, run_id):
        self._policy()
        with self.store._gate():
            run = self._run(run_id, check_caller=False)
            result = {k: deepcopy(run[k]) for k in ('id', 'target', 'generation', 'attempts', 'phase',
                    'technical_outcome', 'coverage', 'processed', 'drafts', 'current_draft', 'receipts', 'unresolved', 'issues', 'model_calls', 'read_bytes')}
            # Served keys stay internal; the caller sees how many were delivered to its attempt.
            result['attempts'] = [{**{k: v for k, v in a.items() if k != 'served'}, 'served_events': len(a.get('served', []))}
                                  for a in result['attempts']]
            result.update(review_objective=run.get('review_objective'),
                          objective_completion=run.get('objective_completion', 'unknown'),
                          source_changes=run.get('source_changes', 'unknown'),
                          pending_review=sum(v == 'pending-review' for v in run['processed'].values()),
                          unresolved_effects=len(run['unresolved']))
            if run.get('objective_progress'):
                from .dream_incremental import objective_observe
                result['objective_progress'] = objective_observe(self._progress(run))
            if (run['policy_revision'] != _digest(read_json(self.store, POLICY)) or
                    run['basis']['dispositions'] != _digest(dispositions(self.store))):
                result.update(issues=[], unresolved=[], access='changed; semantic excerpts withheld')
            return result

    def _admitted(self, run, profile, source_id=None):
        """Currently admitted frozen materials; this lookup serves nothing to the attempt."""
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
        return snapshot, output

    def _serve(self, run, keys):
        """Record material delivered to the current attempt; the caller holds the writer gate."""
        attempt = run['attempts'][-1]
        served = set(attempt.get('served', []))
        if run['phase'] == 'closed' or set(keys) <= served:
            return False
        attempt['served'] = sorted(served | set(keys))
        return True

    def _memory_text(self, run, ref):
        """Exact frozen memory input text, or a stale/forbidden failure; never a substitute."""
        kind, identifier = ref.split(':', 1)
        records = projected_records(self.store, run['target']) if kind == 'record' else collaboration(self.store)
        record = next((r for r in records if r['id'] == identifier), None)
        if record is None or _digest(record) != run['memory_inputs'][ref]['revision']:
            _fail('stale_dependency', 'Memory input changed since this Run froze its revision')
        if kind == 'record' and not record_use_filter(self.store)(record):
            _fail('source_forbidden', 'Memory input sources are prohibited for reuse')
        if kind == 'record':
            return record['title'], record['title'] + '\n\n' + record['body']
        return record['claim']['topic'], record['claim']['topic'] + '\n\n' + record['claim']['text']

    @staticmethod
    def _material_offset(cursor, binding, text_digest, total):
        if cursor is None:
            return 0
        try:
            if not isinstance(cursor, str) or len(cursor) > 512 or not cursor.startswith('material-v1:'):
                raise ValueError('Unbounded cursor')
            position = _decode(cursor[len('material-v1:'):])
            _keys(position, {'binding', 'text_sha256', 'offset'}, {'binding', 'text_sha256', 'offset'}, 'material cursor')
            offset = position['offset']
            if (position['binding'] != binding or position['text_sha256'] != text_digest
                    or type(offset) is not int or not 0 <= offset < total):
                raise ValueError('Cursor is not bound to this frozen text')
            return offset
        except (MemoryError, ValueError, TypeError):
            _fail('invalid_cursor', 'Material cursor does not identify this frozen event and position')

    @staticmethod
    def _read_progress(run, key, offset, end, text_digest, total):
        """Continuous bounded reads of one text; True when this read completed it."""
        reads = run.setdefault('material_reads', {})
        prior = reads.get(key, {})
        if offset == 0 or prior.get('end') == offset and prior.get('text_sha256') == text_digest:
            reads[key] = {'end': end, 'text_sha256': text_digest, 'complete': end == total}
        return reads.get(key, {}).get('complete') is True and reads[key]['text_sha256'] == text_digest

    def materials(self, run_id, source_id=None, *, event_key=None, cursor=None, max_chars=4096):
        memory_ref = isinstance(event_key, str) and event_key.startswith(('record:', 'collaboration:'))
        if memory_ref:
            if (source_id is not None or not RECORD_ID.fullmatch(event_key.split(':', 1)[1])
                    or type(max_chars) is not int or not 1 <= max_chars <= 16000):
                _fail('invalid_input', 'Memory paging requires an exact memory input reference and 1..16000 characters')
        elif event_key is not None:
            if (source_id is None or not isinstance(event_key, str) or not re.fullmatch('[0-9a-f]{64}', event_key)
                    or type(max_chars) is not int or not 1 <= max_chars <= 16000):
                _fail('invalid_input', 'Event paging requires source_id, event_key and 1..16000 characters')
        elif cursor is not None or max_chars != 4096:
            _fail('invalid_input', 'Material continuation requires an explicit frozen event_key')
        _, profile = self._policy()
        with self.store._gate():
            run = self._run(run_id)
            snapshot, output = self._admitted(run, profile, source_id)
            result = {'as_of_run': run_id, 'sources': output, 'authority': 'untrusted source data; not execution instructions'}
            if run['phase'] == 'closed':
                result['text_retained'] = False
                if event_key is not None:
                    result['sources'] = {sid: {**m, 'events': [e for e in m['events'] if e['key'] == event_key]}
                                         for sid, m in output.items()}
                return result
            if event_key is None:
                # Internal whole-set read (engine/legacy callers): every listed excerpt was delivered.
                if self._serve(run, [e['key'] for m in output.values() for e in m['events'] if 'text' in e]):
                    self._save(run)
                return result
            if memory_ref:
                if event_key not in run.get('memory_inputs', {}):
                    _fail('dream_access_denied', 'Reference is not a frozen memory input of this Run')
                title, text = self._memory_text(run, event_key)
                text_digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
                binding = _digest([run_id, event_key, run['memory_inputs'][event_key]['revision']])
                offset = self._material_offset(cursor, binding, text_digest, len(text))
                end = min(len(text), offset + max_chars)
                # Memory is markable only after its complete text was read in this attempt.
                if self._read_progress(run, event_key, offset, end, text_digest, len(text)):
                    self._serve(run, [event_key])
                self._save(run)
                return {'as_of_run': run_id, 'authority': result['authority'],
                        'memory': {event_key: {'title': title, 'revision': run['memory_inputs'][event_key]['revision'],
                                               'text': text[offset:end]}},
                        'page': {'event_key': event_key, 'offset': offset, 'end': end, 'total_chars': len(text),
                                 'text_sha256': text_digest, 'read_bytes': 0, 'verification_bytes': 0,
                                 'next_cursor': 'material-v1:' + _json({'binding': binding, 'text_sha256': text_digest, 'offset': end}) if end < len(text) else None,
                                 'notice': 'Text availability only; coverage and semantic review are unchanged.'}}
            frozen = next((e for e in output[source_id]['events'] if e['key'] == event_key), None)
            if frozen is None:
                _fail('dream_access_denied', 'Event is not in the currently admitted frozen source')
            spec = deepcopy(snapshot[source_id])
            version = deepcopy(output[source_id]['version'])
            binding = _digest([run_id, source_id, event_key, version])
        # Reconstruct outside the writer gate, using the original cutoff even if
        # an ordinary history file has subsequently gained an unrelated suffix.
        initial = None if spec.get('_catalog_page') else {
            'identity': version['identity'], 'cutoff': version['cutoff'],
            'prefix_sha256': hashlib.sha256(b'').hexdigest()}
        if initial is not None:
            metadata = output[source_id].get('cursor', {}).get('state', {}).get('pi_metadata')
            if metadata:
                initial['state'] = {'pi_metadata': deepcopy(metadata)}
        reconstructed = read_source(spec, max_bytes=version['consumed'], max_events=1024, cursor=initial)
        whole = next((e for e in reconstructed['events'] if e['key'] == event_key), None)
        identity = lambda e: {k: v for k, v in e.items() if k not in {'text', 'excerpt_truncated', 'text_chars'}}
        verification = [0]
        if (reconstructed['version'] != version or whole is None or identity(whole) != identity(frozen)
                or check_snapshot(spec, version, verification=verification) != 'valid'):
            _fail('source_changed', 'Source bytes or their public interpretation differ from the frozen event')
        text = whole['text']
        text_digest = hashlib.sha256(text.encode('utf-8')).hexdigest()
        offset = self._material_offset(cursor, binding, text_digest, len(text))
        end = min(len(text), offset + max_chars)
        with self.store._gate():
            current = self._run(run_id)
            if (current['materials'][source_id]['version'] != version or not self._catalog().authorized(spec)
                    or self._forbidden_source(current, frozen)):
                _fail('dream_access_denied', 'Frozen source access changed during material reconstruction')
            if current['phase'] != 'closed':
                self._read_progress(current, event_key, offset, end, text_digest, len(text))
                self._serve(current, [event_key])  # An explicit event read serves it to this attempt.
                self._save(current)
        part = deepcopy(frozen)
        part['text'] = text[offset:end]
        result['sources'][source_id]['events'] = [part]
        page_bytes = reconstructed['coverage']['read_bytes']
        result['page'] = {'event_key': event_key, 'offset': offset, 'end': end, 'total_chars': len(text),
                          'text_sha256': text_digest,
                          'next_cursor': 'material-v1:' + _json({'binding': binding, 'text_sha256': text_digest, 'offset': end}) if end < len(text) else None,
                          'read_bytes': page_bytes,
                          'verification_bytes': reconstructed['coverage']['verification_bytes'] + verification[0],
                          'notice': 'Text availability only; frozen coverage and semantic review are unchanged.'}
        return result

    def material_summary(self, run_id, source_id=None, *, cursor=None, max_bytes=16384, preview_chars=200):
        """Always-paged listing of frozen events and memory inputs within a serialized byte budget."""
        if type(max_bytes) is not int or not 1024 <= max_bytes <= 262144:
            _fail('invalid_input', 'A material summary page needs 1024..262144 bytes')
        _, profile = self._policy()
        with self.store._gate():
            run = self._run(run_id)
            _, output = self._admitted(run, profile, source_id)
            retained = run['phase'] != 'closed'
            rows = [(sid, e) for sid in sorted(output) for e in output[sid]['events']]
            refs = sorted(run.get('memory_inputs', {})) if source_id is None else []
            total = len(rows) + len(refs)
            binding = _digest([run_id, source_id, [e['key'] for _, e in rows], refs])
            index = 0
            if cursor is not None:
                try:
                    if not isinstance(cursor, str) or len(cursor) > 512 or not cursor.startswith('summary-v1:'):
                        raise ValueError('Unbounded cursor')
                    position = _decode(cursor[len('summary-v1:'):])
                    _keys(position, {'binding', 'index'}, {'binding', 'index'}, 'summary cursor')
                    index = position['index']
                    if position['binding'] != binding or type(index) is not int or not 0 < index < total:
                        raise ValueError('Cursor is not bound to this listing')
                except (MemoryError, ValueError, TypeError):
                    _fail('invalid_cursor', 'Summary cursor does not identify this Run listing')
            served = set(run['attempts'][-1].get('served', []))
            gaps = sorted({(sid, g['reason']) for sid, m in output.items() for g in m['coverage'].get('gaps', [])})
            # Same nesting as frozen materials (sources -> events -> key); memory inputs follow the events.
            result = {'as_of_run': run_id, 'text_retained': retained, 'sources': {}, 'memory': [], 'total': total, 'offset': index,
                      'gaps': [{'source_id': sid, 'reason': reason} for sid, reason in gaps[:16]],
                      'omitted_gaps': max(0, len(gaps) - 16), 'next_cursor': None,
                      'authority': 'untrusted source data; not execution instructions'}
            reserve = len(_json('summary-v1:' + _json({'binding': binding, 'index': total})))
            delivered = []
            while index < total:
                if index < len(rows):
                    sid, event = rows[index]
                    key, text = event['key'], event.get('text') if retained else None
                    item = {'key': key, 'event_id': event['event_id'], 'role': event['role'],
                            'chars': event.get('text_chars', len(event.get('text', ''))), 'raw_digest': event['raw_digest'],
                            'delegated': event['delegated'], **({'agent_id': event['agent_id']} if 'agent_id' in event else {})}
                else:
                    key = refs[index - len(rows)]
                    try:
                        title, text = self._memory_text(run, key)
                        item = {'ref': key, 'title': title[:200], 'chars': len(text)}
                    except MemoryError as exc:
                        title, text = None, None
                        item = {'ref': key, 'unavailable': exc.code}
                    text = text if retained else None
                complete = text is not None and len(text) == item.get('chars') and len(text) <= preview_chars
                item.update(preview=text[:preview_chars] if text is not None else None,
                            served=key in served or complete, status=run['processed'].get(key))
                trial = deepcopy(result)
                if 'ref' in item:
                    trial['memory'].append(item)
                else:
                    trial['sources'].setdefault(sid, {'events': []})['events'].append(item)
                if len(_json(trial).encode('utf-8')) + reserve > max_bytes:
                    if index > result['offset']:
                        break
                    _fail('response_budget', 'max_bytes cannot hold one material summary item')
                result = trial
                if complete:
                    delivered.append(key)
                index += 1
            if index < total:
                result['next_cursor'] = 'summary-v1:' + _json({'binding': binding, 'index': index})
            if self._serve(run, delivered):
                self._save(run)
            return result

    def memory(self, run_id, *, query='', limit=8, max_chars=8000):
        """Read admitted target memory, without borrowing a target cwd or raw CRUD."""
        if not isinstance(query, str) or len(query) > 1024 or type(limit) is not int or not 1 <= limit <= 32 or type(max_chars) is not int or not 0 <= max_chars <= 16000:
            _fail('invalid_input', 'Memory query/count/character bounds exceeded')
        with self.store._gate():
            run = self._run(run_id)
            _, profile = self._policy()
            allowed = record_use_filter(self.store)
            records = [r for r in projected_records(self.store, run['target'])
                       if r['scope'] == 'project' and r['effective_status'] == 'active' and allowed(r)]
            records = self.store._rank(records, query) if query else records
            items, used = [], 0
            for record in records[:limit]:
                item = {k: record[k] for k in ('id', 'title', 'body', 'sources', 'content_digest', 'curation_revision')}
                size = len(_json(item))
                if used + size <= max_chars:
                    items.append(item)
                    used += size
            return {'target': run['target'], 'items': items, 'chars': used,
                    'notice': 'Reviewed memory is a qualified consolidation input, not new independent evidence; check a current owner when making current-status or action claims.'}

    def next_hint(self, run_id):
        """Model-free continuation hint for `next`; following it is optional and grants nothing."""
        from .dream_incremental import REVIEWED, UNACCEPTABLE_GAPS
        _, profile = self._policy()
        with self.store._gate():
            run = self._run(run_id, check_caller=False)
            _, output = self._admitted(run, profile)
            served = set(run['attempts'][-1].get('served', []))
            order = run.get('memory_order') or sorted(run.get('memory_inputs', {}))
            rows = [(sid, e['key']) for sid in sorted(output) for e in output[sid]['events']] + [(None, ref) for ref in order]
            unmarked = [(sid, key) for sid, key in rows if run['processed'].get(key) not in REVIEWED]
            empty = ['source:' + sid for sid, m in output.items() if not m['events'] and m.get('version')
                     and run['processed'].get('source:' + sid) not in REVIEWED]
            unserved = [(sid, key) for sid, key in unmarked if key not in served]
            gaps = sorted({(sid, g['reason']) for sid, m in output.items() for g in m['coverage'].get('gaps', [])
                           if g['reason'] not in UNACCEPTABLE_GAPS})
            # Start with the bounded listing; a memory-only batch goes straight to its first input.
            suggestion = None if not served and any(sid for sid, _ in rows) else unserved[0] if unserved else None
            return {'phase': run['phase'], 'listing_first': not served and any(sid for sid, _ in rows),
                    'suggested_source_id': suggestion[0] if suggestion else None,
                    'suggested_event_key': suggestion[1] if suggestion else None,
                    'markable': ([key for _, key in unmarked if key in served] + empty)[:64],
                    'pending_counts': {'unserved': len(unserved), 'unmarked': len(unmarked) + len(empty), 'gaps': len(gaps)},
                    'gaps': [{'source_id': sid, 'reason': reason} for sid, reason in gaps[:16]]}

    def takeover(self, run_id, expected_generation):
        """Explicit operator continuation. Never a model-facing automatic takeover."""
        self._policy()
        with self.store._gate():
            run = self._run(run_id, expected_generation, check_caller=False)
            if run['phase'] == 'closed':
                _fail('closed_run', 'Closed runs cannot be taken over')
            run['generation'] += 1
            run['attempts'].append({'generation': run['generation'], 'caller': self.caller, 'at': _now(),
                                    'identity_assurance': self.identity_assurance})
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
                if (event.get('harness') in {'pi', 'claude'} and event.get('branch') == 'unspecified' or
                        event.get('harness') == 'pi' and event.get('ancestry_verified') is not True):
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
                dependencies[ref] = {'type': 'record', 'id': identifier, 'revision': _digest(record),
                                     'sources': record['sources'],
                                     'level': 'hypothesis' if record['kind'] == 'hypothesis' or
                                     record['details'].get('statement_type') in {'hypothesis', 'interpretation'} else
                                     'report' if record['body'].startswith('[report] ') or any(s.get('note', '').startswith('dream-source-v1:') and
                                                     _decode(s['note'][len('dream-source-v1:'):]).get('claim_level') == 'report'
                                                     for s in record['sources']) else None}
            elif kind == 'collaboration':
                record = next((r for r in collaboration(self.store) if r['id'] == identifier), None)
                if (not record or record['effective_status'] != 'active' or
                        run['target'] not in set(policy['collaboration_projects']).intersection(record['claim']['projects'])):
                    _fail('dependency_inactive', 'Collaboration reference is not active or permitted for this project')
                shaped = {**record, 'project_id': run['target'], 'title': record['claim']['topic']}
                if not record_use_filter(self.store, scope='collaboration')(shaped):
                    _fail('source_forbidden', 'The reviewed collaboration source binding was revoked')
                dependencies[ref] = {'type': 'collaboration', 'id': identifier, 'revision': _digest(record),
                                     'sources': record['sources'],
                                     'level': record['claim']['level'], 'claim': record['claim']}
            else:
                _fail('unverifiable_source', 'Unsupported reference kind')
        return events, dependencies

    def _admit(self, run, claim, review, *, scope, active=True):
        validate_claim(claim)
        policy, profile = self._policy()
        if run['target'] not in claim['projects'] or not set(claim['scenarios']) <= set(profile['scenarios']):
            _fail('scope_mismatch', 'Claim applicability exceeds the selected target or scenarios')
        events, dependencies = self._refs(run, claim['refs'], scope=scope)
        if not events and not dependencies:
            _fail('unverifiable_source', 'A claim needs frozen evidence or an active reviewed memory')
        source_keys = set(events)
        for ref, dependency in dependencies.items():
            source_keys.add(ref)
            for source in dependency['sources']:
                source_keys.add('source-uri:' + source['uri'])
                if source.get('note', '').startswith('dream-source-v1:'):
                    note = _decode(source['note'][len('dream-source-v1:'):])
                    source_keys.update([note['event_key'], 'source:' + note['source_id'], *note.get('lineage', [])])
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
            if any(d['type'] != 'collaboration' for d in dependencies.values()):
                _fail('human_attribution_required', 'Research memories cannot establish personal attribution')
            if claim['level'] == 'explicit' and any(d['level'] != 'explicit' for d in dependencies.values()):
                _fail('evidence_upgrade', 'An inferred preference cannot become an explicit user statement')
            if active and claim['level'] == 'inferred' and not profile['allow_inferred']:
                _fail('pending_review', 'Inferred publication is disabled by policy')
        else:
            if claim['level'] in {'explicit', 'inferred'}:
                _fail('scope_mismatch', 'Personal preferences belong to the collaboration owner')
            if (claim['level'] == 'recorded' and not any(e['evidence'] == 'owner' for e in events.values())
                    and not any(d['type'] == 'record' and d['level'] is None for d in dependencies.values())):
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

    def _check_coverage(self, run, statuses):
        """Marks bind frozen identities; reviewed states require material served to this attempt."""
        if not isinstance(statuses, dict) or len(statuses) > 128:
            _fail('invalid_input', 'Expected a bounded event/status mapping')
        if run['phase'] == 'closed':
            _fail('closed_run', 'Closed coverage cannot be rewritten')
        events = self._events(run)
        empty_sources = {'source:' + sid for sid, m in run['materials'].items() if not m['events'] and m.get('version')}
        memory_inputs = run.get('memory_inputs', {})
        current_inputs = self._memory_inputs(run['target'], self._policy()[0]) if memory_inputs else {}
        served = set(run['attempts'][-1].get('served', []))
        for key, status in statuses.items():
            if key not in set(events) | empty_sources | set(memory_inputs) or status not in {'processed', 'excluded', 'no-signal', 'pending-review'}:
                _fail('invalid_input', 'Coverage must identify frozen events and explicit processing states')
            if key in memory_inputs and current_inputs.get(key) != memory_inputs[key]:
                _fail('stale_dependency', 'Memory review must bind the frozen canonical revision')
            if status != 'pending-review' and key not in served and key not in empty_sources:
                _fail('unserved_event', f'Read `{key}` with dream_materials in this attempt before marking it {status}')
        return statuses

    def mark_processed(self, run_id, generation, statuses):
        self._policy()
        with self.store._gate():
            run = self._run(run_id, generation)
            self._check_coverage(run, statuses)
            run['processed'].update(statuses)
            self._save(run)
            return {'status': 'recorded', 'processed': run['processed']}

    def freeze(self, run_id, generation, operations, *, reconsider_reason=None, coverage=None):
        """Freeze operations and optional verified coverage marks; both take effect only at publish."""
        policy, profile = self._policy()
        if not isinstance(operations, list) or not int(coverage is None) <= len(operations) <= profile['budgets']['operations']:
            _fail('draft_limit', 'Operations exceed the selected working-set bound')
        with self.store._gate():
            run = self._run(run_id, generation)
            if run['phase'] == 'closed':
                _fail('draft_limit', 'Closed Runs cannot accept replacement drafts')
            if coverage is not None:
                self._check_coverage(run, coverage)
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
            if coverage is not None:
                draft['coverage'] = dict(coverage)
            created_refs = list(resolved_refs.values())
            draft['created_refs'] = created_refs
            draft['operation_bases'] = {o['id']: self._operation_basis(run, o, created_refs) for o in ops}
            revision = _digest(draft)
            _put(self.store, f'dreaming/runs/{run_id}/drafts/{revision}.json', draft, immutable=True)
            run.update(current_draft=revision, phase='draft-ready', working_basis=basis, unresolved=[])
            run['closure_bases'] = deepcopy(draft['operation_bases'])
            run['drafts'].append(revision)
            self._save(run)
            return {'status': 'frozen', 'run_id': run_id, 'generation': generation, 'draft_revision': revision,
                    'operations': [{'id': o['id'], 'action': o['action'], 'reserved_id': o['reserved_id']} for o in ops],
                    **({'coverage': {'status': 'staged-until-publish', 'processed': dict(coverage)}} if coverage is not None else {})}

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
                    **({'coverage': draft['coverage']} if 'coverage' in draft else {}),
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

    def _source_checks(self, run):
        from .dream_sources import check_snapshot
        _, profile = self._policy()
        specs = {s['id']: s for s in self._effective(run)['sources']}
        cost = 0
        for sid, material in run['materials'].items():
            version = material.get('version') or {}
            consumed = version.get('consumed', 0)
            if specs.get(sid, {}).get('_catalog_page'):
                cost += consumed - version.get('start', 0) + (consumed if 'prefix_sha256' in version else 0)
                cost += version.get('cutoff', 0) if version.get('structure_sha256') else 0
            else:
                cost += consumed + (version.get('cutoff', 0) if version.get('structure_raw_sha256') else 0)
        limit = min(profile['budgets']['source_bytes'], run['profile_snapshot']['budgets']['source_bytes'])
        if cost > limit:
            _fail('source_budget_exhausted', 'Source verification exceeds the per-transaction byte bound')
        verification = [0]
        checks = {sid: check_snapshot(specs[sid], material['version'], verification=verification) if sid in specs else 'forbidden'
                  for sid, material in run['materials'].items()}
        with self.store._gate():
            current = self._run(run['id'], run['generation'])
            current['read_bytes'] = current.get('read_bytes', 0) + verification[0]
            self._save(current)
        if verification[0] > limit:
            _fail('source_budget_exhausted', 'Concurrent source verification exceeded its transaction bound')
        return checks

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
            events, dependencies = self._refs(run, review['checked_refs'], scope=scope)
        else:
            active = operation.get('visibility', 'active') == 'active'
            if operation['action'] == 'collaboration_create' and operation['claim']['level'] == 'inferred':
                active = False
            events, dependencies = self._admit(run, operation['claim'], operation['review'], scope=scope, active=active)
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
        if not events and not dependencies:
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
                                                   'claim_level': operation.get('claim', {}).get('level'),
                                                   **({'selection_assurance': e['assurance']} if e.get('assurance') else {})})}
                for e in events.values()]
        uris.extend(source for dependency in dependencies.values() for source in dependency['sources'])
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
                if 'operation_bases' in draft:
                    if self._operation_basis(run, operation, draft['created_refs']) != draft['operation_bases'][operation_id]:
                        _fail('stale_basis', 'A reviewed input, target binding or applicable policy changed')
                elif self._basis(self._effective(run)) != run['working_basis']:
                    _fail('stale_basis', 'Canonical namespace, policy, registry or disposition changed after review')
                if 'operation_bases' not in draft and draft['basis']['policy'] != _digest(policy):
                    _fail('stale_policy', 'Frozen draft policy is no longer current')
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
            if 'operation_bases' in draft:
                run['closure_bases'][operation_id] = self._operation_basis(run, operation, draft['created_refs'])
            run['phase'] = 'applying'
            self._save(run)
            self._fault('receipt-written', operation)
            return receipt

    def publish(self, run_id, generation, revision):
        self._policy()
        with self.store._gate():
            run = self._run(run_id, generation)
            try:
                draft = self._draft(run, revision)
            except MemoryError:
                draft = None
                if self.publisher:
                    raise
        # Only an existing coverage-only draft, which changes no canonical memory, is open to advisory executors.
        if not self.publisher and (draft is None or draft['operations']):
            _fail('advisory_only', 'This endpoint can draft only; use a separately bound trusted publisher')
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
            if run['current_draft'] != revision or run['phase'] == 'closed':
                _fail('stale_draft', 'A concurrent review selected another draft')
            run['unresolved'] = errors
            status = 'partial' if errors and outcomes else 'blocked' if errors else 'applied'
            run.update(phase=status, technical_outcome='ok' if not errors else status)
            coverage_key = f"dream:{run_id}:{draft['serial']}:coverage"
            if 'coverage' in draft and not errors and coverage_key not in run['receipts']:
                # Marks land in the same durable write that acknowledges the draft's effects.
                run['processed'].update(draft['coverage'])
                run['receipts'][coverage_key] = {'operation_id': 'coverage', 'operation_digest': _digest(draft['coverage']),
                                                 'paths': [], 'executor': draft['review_executor'],
                                                 'acknowledged_by': self.caller, 'replayed': False}
            self._save(run)
        return {'status': status, 'applied': outcomes, 'unresolved': errors,
                **({'coverage': 'applied' if coverage_key in run['receipts'] else 'not-applied'} if 'coverage' in draft else {}),
                'scientific_validation': 'not implied by publication'}

    def _accepted_gaps(self, run, accept_gaps):
        """Each accepted gap names a permanent gap this Run actually observed for that source."""
        from .dream_incremental import UNACCEPTABLE_GAPS
        if not run.get('objective_progress'):
            _fail('invalid_input', 'Accepted gaps belong to objective review Runs')
        if not isinstance(accept_gaps, list) or not 1 <= len(accept_gaps) <= 16:
            _fail('invalid_input', 'accept_gaps is a list of one to sixteen {source_id, reason, note} entries')
        progress, accepted = self._progress(run), {}
        for gap in accept_gaps:
            _keys(gap, {'source_id', 'reason', 'note'}, {'source_id', 'reason', 'note'}, 'accepted gap')
            for field in ('source_id', 'reason', 'note'):
                _nonempty(gap[field], 'accepted gap ' + field)
                if len(gap[field]) > 2048:
                    _fail('invalid_input', 'Accepted gap fields are bounded text')
            observed = {g['reason'] for g in run['materials'].get(gap['source_id'], {}).get('coverage', {}).get('gaps', [])}
            observed |= {g['reason'] for g in progress['sources'].get(gap['source_id'], {}).get('gaps', [])}
            if gap['reason'] in UNACCEPTABLE_GAPS or gap['reason'] not in observed:
                _fail('invalid_input', f"No outstanding permanent gap `{gap['reason']}` for source `{gap['source_id']}`")
            accepted.setdefault(gap['source_id'], []).append({'reason': gap['reason'], 'note': gap['note']})
        return accepted

    def close(self, run_id, generation, *, abandon_reason=None, objective_outcome=None, accept_gaps=None):
        if objective_outcome is not None and objective_outcome not in {'reviewed', 'disposed'}:
            _fail('invalid_objective', 'Objective outcome must be reviewed, disposed, or remain pending')
        _, profile = self._policy()
        with self.store._gate():
            run = self._run(run_id, generation)
            if run['phase'] == 'closed':
                if run.get('checkpoint') and (run.get('objective_progress') or self._basis(self._effective(run)) == run['working_basis']):
                    _put(self.store, f'dreaming/checkpoints/{self.profile_id}-{run["lane"]}.json', run['checkpoint'])
                    if run.get('objective_path'):
                        _put(self.store, run['objective_path'], {'run_id': run_id})
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
            if accept_gaps is not None:
                run['accepted_gaps'] = self._accepted_gaps(run, accept_gaps)
            current_basis = self._basis(self._effective(run))
            basis_changed = current_basis != run['working_basis']
            if run.get('closure_bases'):
                draft = self._draft(run, run['current_draft'])
                basis_changed = any(self._operation_basis(run, op, draft['created_refs']) != run['closure_bases'][op['id']]
                                    for op in draft['operations'])
            if not outstanding and basis_changed and not abandon_reason:
                _fail('stale_basis', 'External changes require review or explicit partial close without a no-change checkpoint')
            missing = set(self._events(run)) - set(run['processed'])
            pending = sum(s == 'pending-review' for s in run['processed'].values())
            if objective_outcome is not None and (pending or missing or outstanding or basis_changed):
                _fail('pending_objective', 'An objective with pending material or unresolved effects cannot be completed')
            run['objective_completion'] = objective_outcome or ('legacy-processing-complete' if run.get('review_objective') is None and not pending and not missing else 'pending')
            if missing:
                run['coverage'] = 'partial'
            run.update(phase='closed', closed_at=_now(), pending_review=pending,
                       technical_outcome='partial' if outstanding or basis_changed else 'ok', abandon_reason=abandon_reason)
            if not outstanding and not basis_changed:
                run['checkpoint'] = {'version': 1, 'run_id': run_id, 'coverage': run['coverage'], 'pending_review': pending,
                                     'fingerprint': _digest({'sources': run['source_revision'], 'basis': current_basis}),
                                     'source_versions': {k: v['version'] for k, v in run['materials'].items()},
                                     'unprocessed_events': len(missing), 'review_objective': run.get('review_objective'),
                                     'objective_completion': run['objective_completion'],
                                     **({'accepted_gaps': run['accepted_gaps']} if run.get('accepted_gaps') else {})}
                if run.get('objective_progress'):
                    from .dream_incremental import objective_close, objective_observe, save_objective
                    progress = objective_close(self._progress(run), run)
                    # Reviewed effects are already included in this objective;
                    # do not manufacture another increment from our own outputs.
                    current_inputs = self._memory_inputs(run['target'], self._policy()[0])
                    for ref in progress['memory']:
                        if progress['memory'][ref]['status'] in {'processed', 'excluded', 'no-signal'} and ref in current_inputs:
                            progress['memory'][ref]['revision'] = current_inputs[ref]['revision']
                    for receipt in run['receipts'].values():
                        for path in receipt['paths']:
                            ref = ('record:' if path.startswith('records/') else 'collaboration:' if path.startswith('collaboration/') else '') + Path(path).stem
                            if ref in current_inputs:
                                progress['memory'][ref] = {**current_inputs[ref], 'status': 'processed'}
                    observed = objective_observe(progress)
                    if objective_outcome and observed['objective_completion'] != 'reviewable-complete':
                        named = ', '.join(f"{g.get('source_id', g.get('root'))}: {g['reason']}" for g in observed['gaps'][:4])
                        _fail('pending_objective', 'Historical sources, memories or explicit gaps still need review'
                              + (f' (unaccepted gaps: {named}; accept them with a note or keep the objective pending)' if named else ''))
                    run['objective_progress'] = save_objective(self.store, progress)
            # Receipts were sealed at publication; the original sources stay the text owner.
            for material in run['materials'].values():
                for event in material['events']:
                    event.pop('text', None)
            self._save(run)
            self._fault('run-closed', {'id': 'close'})
            if run.get('checkpoint'):
                _put(self.store, f'dreaming/checkpoints/{self.profile_id}-{run["lane"]}.json', run['checkpoint'])
                if run.get('objective_path'):
                    _put(self.store, run['objective_path'], {'run_id': run_id})
            return {'status': 'closed', 'run_id': run_id, 'coverage': run['coverage'],
                    'pending_review': pending, 'unprocessed_events': len(missing), 'partial': bool(outstanding or basis_changed),
                    'review_objective': run.get('review_objective'), 'objective_completion': run['objective_completion'],
                    'unresolved_effects': len(outstanding),
                    **({'objective_progress': observed, 'outstanding_gaps': observed['gaps']}
                       if run.get('objective_progress') and run.get('checkpoint') else {})}

    def changes(self, run_id, *, max_bytes=12000):
        """Readable bounded differences within the current objective and source grants."""
        from .dream_incremental import change_set
        return change_set(self, run_id, max_bytes=max_bytes)

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
            relative = f'dreaming/issues/{identity}.json'
            prior = read_json(self.store, relative)
            semantic = _digest(' '.join(note.split()))
            changed = prior is None or prior['semantic_digest'] != semantic
            notify = semantic_reviewed and (prior is None or prior.get('last_notified_digest') != semantic)
            item = {'id': identity, 'topic': topic, 'relation': relation, 'note': note,
                    'observations': observations, 'notify': notify,
                    'needs_semantic_review': not semantic_reviewed and (changed or prior.get('observations') != observations if prior else True)}
            selected_refs = observations.get('refs', [])
            if selected_refs:
                events, _ = self._refs(run, selected_refs, scope='research')
            else:
                events = self._events(run)
            used_sources = {e['source_id'] for e in events.values()}
            specs = [compact_source_spec(s) for s in self._effective(run)['sources'] if s['id'] in used_sources]
            disposition = (prior or {}).get('disposition', 'pending') if not changed else 'pending'
            item.update(target=run['target'], disposition=disposition, as_of=_now(),
                        source_pointers=[{'uri': Path(s['path']).as_uri()} for s in specs])
            if disposition != 'pending':
                item['notify'] = False
            run['issues'] = [x for x in run['issues'] if x['id'] != identity] + [item]
            self._save(run)
            _put(self.store, relative, {**(prior or {}), **item, 'last_run': run_id, 'semantic_digest': semantic,
                                       'last_notified_digest': semantic if notify else (prior or {}).get('last_notified_digest'),
                                       'source_bindings': specs, 'evidence_keys': sorted(events),
                                       'observations': observations})
            return item
