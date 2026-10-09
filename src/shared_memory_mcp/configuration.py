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
