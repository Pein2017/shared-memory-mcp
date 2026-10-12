"""Stable project binding over the existing policy owner, never caller-selected roles.

Version-2 policies remain readable for historical receipts. A version-3 policy
adds explicit project bindings without rewriting profile/source identities. Read
access is independent of batch execution budgets and executor membership.
"""
from __future__ import annotations

from copy import deepcopy

from .core import _fail
from .curation import read_json


def configured_profile(store, caller, *, reading=False):
    from .dreaming import POLICY, validate_policy
    scope = store._resolve(caller)
    policy = read_json(store, POLICY)
    if policy is None:
        _fail('unconfigured_dreaming', 'Install the stable project/source configuration before consolidation')
    validate_policy(store, policy)
    identifier = policy.get('bindings', {}).get(scope['project_id'])
    if identifier is None and policy['version'] == 2:
        # A unique retained binding can be projected without silently combining grants.
        eligible = [key for key, p in policy['profiles'].items()
                    if scope['project_id'] in p.get('reader_projects', p['target_projects'])] if reading else [
                        key for key, p in policy['profiles'].items() if scope['project_id'] in p['executor_projects']]
        if len(eligible) == 1:
            identifier = eligible[0]
    if identifier is None:
        _fail('unconfigured_binding', 'No unique stable binding for the actual caller project')
    profile = policy['profiles'].get(identifier)
    allowed = profile.get('reader_projects', profile['target_projects']) if reading and profile else profile['executor_projects'] if profile else []
    if profile is None or scope['project_id'] not in allowed:
        _fail('dream_access_denied', 'Actual caller project is outside the configured access scope')
    return identifier, policy, profile, scope


def configured_engine(store, caller):
    """One source of action authority, with no Agent-provided publisher switch."""
    from .dreaming import Dreaming
    identifier, _, profile, _ = configured_profile(store, caller)
    return Dreaming(store, identifier, caller, publisher=bool(profile['actions']), caller_binding='caller-declared')


class ViewReader:
    """Read-only view adapter. No Run, publication capability, or execution-profile input."""
    def __init__(self, store, caller):
        self.store = store
        self.caller = deepcopy(caller)
        self.profile_id, _, _, scope = configured_profile(store, caller, reading=True)
        self.caller.update(cwd=scope['cwd'], project_id=scope['project_id'])

    def _policy(self):
        identifier, policy, profile, _ = configured_profile(self.store, self.caller, reading=True)
        if identifier != self.profile_id:
            _fail('stale_policy', 'Reader binding changed during this bounded read')
        return policy, profile

    def _target(self, profile, target_project=None):
        target = target_project or self.caller['project_id']
        if target != self.caller['project_id'] or target not in profile['target_projects']:
            _fail('dream_access_denied', 'Ordinary overview reads retain actual project scope')
        return target

    def _catalog(self, profile=None):
        from .dream_catalog import SourceCatalog
        return SourceCatalog(self.store, self.profile_id, profile or self._policy()[1])

    def overview(self, view, **kwargs):
        from .dream_views import read_view
        return read_view(self, view, **kwargs)


EXTRACTION = 'extraction.json'
EXTRACTION_DEFAULTS = {'version': 1, 'enabled': False, 'models': {}, 'idle_hours': 1, 'max_sessions_per_startup': 2,
                       'max_age_days': 10, 'window_bytes': 204800, 'history_roots': []}


def load_extraction(store):
    """Store-owned extraction settings; any invalid or model-less configuration disables extraction.

    Returns the normalized settings plus `model` ({name, argv, harness}) and a `diagnostic`
    string when extraction cannot run. Callers report the diagnostic once and start nothing.
    """
    import shutil
    from .core import MemoryError, _keys
    from .dream_sources import validate_source
    try:
        raw = read_json(store, EXTRACTION)
        config = {**EXTRACTION_DEFAULTS, **(raw or {})}
        _keys(config, set(EXTRACTION_DEFAULTS), set(EXTRACTION_DEFAULTS) | {'preferred'}, 'extraction')
        if config['version'] != 1 or type(config['enabled']) is not bool:
            _fail('invalid_extraction', 'extraction.version must be 1 and enabled a boolean')
        for name, low, high in (('idle_hours', 0, 24 * 30), ('max_sessions_per_startup', 1, 16),
                                ('max_age_days', 1, 365), ('window_bytes', 4096, 8 * 1024 * 1024)):
            if type(config[name]) not in (int, float) or isinstance(config[name], bool) or not low <= config[name] <= high:
                _fail('invalid_extraction', f'extraction.{name} must be a number in [{low}, {high}]')
        models = config['models']
        if not isinstance(models, dict) or any(
                not isinstance(argv, list) or not argv or not argv[0] or len(argv) > 64 or
                any(not isinstance(x, str) or '\x00' in x for x in argv) for argv in models.values()):
            _fail('invalid_extraction', 'extraction.models maps a harness to a nonempty argv list')
        roots = config['history_roots']
        if not isinstance(roots, list) or len(roots) > 16:
            _fail('invalid_extraction', 'extraction.history_roots must be a bounded list')
        for root in roots:
            _keys(root, {'path', 'format', 'schema'}, {'path', 'format', 'schema', 'native_version', 'native_versions'}, 'history root')
            if root['format'] not in {'codex', 'pi', 'claude'}:
                _fail('invalid_extraction', 'Extraction history roots are native codex, pi or claude histories')
            validate_source({'id': 'history-discovery', **root})
        preferred = config.get('preferred')
        if preferred is not None and preferred not in models:
            _fail('invalid_extraction', 'extraction.preferred must name a configured model template')
        names = [preferred] if preferred is not None else list(models)
        # One selected model per run; a missing preferred binary never falls back to another template.
        selected = next((name for name in names if shutil.which(models[name][0])), None)
        if selected is None:
            if not config['enabled']:
                return {**config, 'model': None, 'diagnostic': None}
            _fail('extraction_model_missing', 'No configured extraction model command is available on PATH')
        argv = models[selected]
        name = argv[argv.index('--model') + 1] if '--model' in argv[:-1] else selected
        return {**config, 'model': {'harness': selected, 'name': name, 'argv': list(argv)}, 'diagnostic': None}
    except MemoryError as exc:
        return {**EXTRACTION_DEFAULTS, 'enabled': False, 'model': None, 'diagnostic': f'{exc.code}: {exc}'[:300]}
