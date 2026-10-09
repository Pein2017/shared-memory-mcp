"""Foreground current-owner reads use configured grants, not generic source search."""
from copy import deepcopy
import json

from dreaming_helpers import environment
from shared_memory_mcp.core import _digest
from shared_memory_mcp.dreaming import configure_policy


def bind_owner(store):
    routing = {
        'version': 1,
        'description': 'Synthetic owner routing; never a production policy.',
        'topics': [{'id':'research-entry','title':'Current research',
                    'when':'Research status and airport progress',
                    'aliases':['airport', 'research status'],
                    'sources':[{'uri':'file:///fixture/research-index.md'}]}],
        'context': {'version': 1, 'owners': [
            {'id':'research-index','topic_ids':['research-entry'], 'grant_id':'owner',
             'role':'index'}]},
    }
    store._publish(store.root/'routing/demo.json', (json.dumps(routing)+'\n').encode())


def test_foreground_reads_real_current_owner_and_rechecks_changed_bytes(tmp_path, monkeypatch):
    engine, store, _, caller, _, owner, _ = environment(tmp_path)
    bind_owner(store)
    from shared_memory_mcp import dream_sources
    original = dream_sources._open_source
    opened = []
    def observe(source):
        opened.append(source['path'])
        return original(source)
    monkeypatch.setattr(dream_sources, '_open_source', observe)
    first = store.context(caller, query='airport research status')
    assert first['status'] == 'ok' and not opened
    assert 'CURRENT_OWNER_NEW_DECISION' not in first['text']
    owner.write_text('Current decision: CURRENT_OWNER_NEW_DECISION; airport closed; no checkpoint promoted.\n')
    result = store.context(caller, query='airport research status', current_status=True)
    assert result['status'] == 'ok'
    assert opened == [str(owner)]
    assert 'CURRENT_OWNER_NEW_DECISION' in result['text']
    assert result['owner_checks']['status'] == 'checked'
    assert result['owner_checks']['items'][0]['id'] == 'research-index'
    assert result['owner_checks']['items'][0]['source_version']
    assert 'current-state' in result['owner_checks']['notice'].lower() or 'as-of' in result['owner_checks']['notice'].lower()
    assert len(json.dumps(result,ensure_ascii=False).encode()) <= 8000
    owner.write_text('Current decision: OWNER_SUCCESSOR_UPDATE; separate experiment is preparing.\n')
    updated = store.context(caller, query='airport research status', current_status=True)
    assert updated['status'] == 'ok' and 'OWNER_SUCCESSOR_UPDATE' in updated['text']
    assert 'CURRENT_OWNER_NEW_DECISION' not in updated['text']
    assert updated['packet_revision'] != result['packet_revision']


def test_foreground_revocation_omits_text_and_reports_gap(tmp_path):
    engine, store, _, caller, _, owner, _ = environment(tmp_path)
    bind_owner(store)
    owner.write_text('SECRET_CURRENT_OWNER_CANARY\n')
    ok = store.context(caller, query='airport research status', current_status=True)
    assert 'SECRET_CURRENT_OWNER_CANARY' in ok['text']
    policy, _ = engine._policy()
    updated = deepcopy(policy)
    updated['profiles']['fixture']['source_grants'] = [
        g for g in updated['profiles']['fixture']['source_grants'] if g['id'] != 'owner']
    configure_policy(store, updated, expected_revision=_digest(policy))
    denied = store.context(caller, query='airport research status', current_status=True)
    assert 'SECRET_CURRENT_OWNER_CANARY' not in json.dumps(denied)
    assert denied['owner_checks']['status'] in ('gap','unavailable')
    assert denied['owner_checks']['gaps']
    assert 'SECRET_CURRENT_OWNER_CANARY' not in store.context(caller)['text']


def test_current_status_requires_task_question_and_grant_binding(tmp_path):
    _, store, _, caller, _, owner, _ = environment(tmp_path)
    bind_owner(store)
    owner.write_text('CURRENT_OWNER_UNQUOTED\n')
    default = store.context(caller)
    assert 'CURRENT_OWNER_UNQUOTED' not in json.dumps(default)
    blank = store.context(caller, current_status=True)
    assert 'CURRENT_OWNER_UNQUOTED' not in json.dumps(blank)
    assert blank['owner_checks']['status'] == 'gap'
    foreign = {**caller, 'cwd': str(tmp_path / 'not-registered')}
    other = store.context(foreign, query='airport research status', current_status=True)
    assert other['status'] in ('unmapped','invalid') and not other.get('text')


def test_owner_limit_reserves_roles_ranks_task_topic_and_returns_only_authorized_pointers(tmp_path, monkeypatch):
    engine, store, _, caller, _, owner, _ = environment(tmp_path)
    bind_owner(store)
    from shared_memory_mcp.recall import load_routing
    from shared_memory_mcp.owner_checks import check
    from shared_memory_mcp import dream_sources
    routing = load_routing(store, 'demo')
    routing['topics'].append({'id':'general-status', 'title':'Research status',
                             'when':'General status', 'aliases':['research status'],
                             'sources':[{'uri':'file:///fixture/story.md'}]})
    policy, _ = engine._policy()
    updated = deepcopy(policy)
    paths = {'research-index': owner}
    for identifier, role, topic, priority in (
            ('recent-result', 'result', 'research-entry', 90),
            ('older-result', 'result', 'research-entry', 10),
            ('airport-question', 'question', 'research-entry', 0),
            ('general-question', 'question', 'general-status', 100)):
        path = owner.parent/(identifier+'.md')
        path.write_text(identifier+' current decision.\n')
        paths[identifier] = path
        routing['context']['owners'].append({'id':identifier, 'role':role,
            'topic_ids':[topic], 'grant_id':identifier, 'priority':priority})
        updated['profiles']['fixture']['source_grants'].append({'id':identifier,
            'kind':'file', 'path':str(path), 'format':'document', 'schema':'document-v1'})
    configure_policy(store, updated, expected_revision=_digest(policy))
    original = dream_sources._open_source
    opened = []
    def observe(source):
        opened.append(source['path'])
        return original(source)
    monkeypatch.setattr(dream_sources, '_open_source', observe)
    units, status = check(store, caller, store._resolve(caller), routing, 'airport research status')
    assert status['status'] == 'partial'
    selected = {'research-index', 'recent-result', 'airport-question'}
    assert {unit['unit_id'] for unit in units} == selected
    assert set(opened) == {str(paths[identifier]) for identifier in selected} and len(opened) == 3
    assert {gap['id'] for gap in status['gaps']} == {'older-result', 'general-question'}
    for gap in status['gaps']:
        assert gap['reason'] == 'owner_selection_limit'
        assert gap['read_hint'] == {'path':str(paths[gap['id']])}
    # An unresolved owner loses its pointer when the grant is withdrawn.
    policy, _ = engine._policy()
    updated = deepcopy(policy)
    updated['profiles']['fixture']['source_grants'] = [
        grant for grant in updated['profiles']['fixture']['source_grants']
        if grant['id'] != 'general-question']
    configure_policy(store, updated, expected_revision=_digest(policy))
    _, denied = check(store, caller, store._resolve(caller), routing, 'airport research status')
    gap = next(gap for gap in denied['gaps'] if gap['id'] == 'general-question')
    assert gap == {'id':'general-question', 'reason':'dream_access_denied'}
    assert str(paths['general-question']) not in json.dumps(denied)
