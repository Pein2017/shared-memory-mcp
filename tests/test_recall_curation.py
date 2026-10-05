"""Behavioral regressions for useful recall, isolation and reversible curation."""
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from shared_memory_mcp.core import MemoryError, MemoryStore


def record(title='pytest collection', body='A bounded historical discovery failure.', **extra):
    return {'kind': 'observation', 'title': title, 'body': body, 'scope': 'project',
            'sources': [{'uri': 'file:///research/owner.md', 'locator': 'L1'}], **extra}


REVIEW = {'reason': 'Source text and applicability checked; not scientific certification.',
          'evidence': [{'uri': 'file:///research/owner.md', 'locator': 'L1'}]}


@pytest.fixture
def env(tmp_path):
    project = tmp_path / 'project'
    project.mkdir()
    store = MemoryStore(tmp_path / 'memory')
    store.init()
    store.register('demo', [project])
    ctx = {'cwd': str(project), 'harness': 'codex', 'session_id': 'real-fixture', 'actor': 'test'}
    return store, ctx, project


def accepted(store, ctx, key, **kwargs):
    r = store.propose(ctx, record(**kwargs), key)['record']
    return store.promote(ctx, r['id'], REVIEW, key + ':review')['record']


def routing(store, project='demo'):
    directory = store.root / 'routing'
    directory.mkdir(exist_ok=True)
    value = {'version': 1, 'description': 'Find original owners; memory is navigation.',
             'topics': [{'id': 'testing', 'title': 'Test discovery',
                         'when': 'When default test collection looks incomplete.',
                         'aliases': ['pytest', '测试收集'], 'search_terms': ['pytest'],
                         'sources': [{'uri': 'file:///research/tests.md'}]}]}
    (directory / (project + '.json')).write_text(json.dumps(value))


def test_startup_is_navigation_not_oldest_record(env):
    store, ctx, _ = env
    routing(store)
    before = store.context(ctx)
    accepted(store, ctx, 'unrelated', title='Old QP study', body='Private experimental narrative.')
    after = store.context(ctx)
    assert after['status'] == 'ok' and after['items'] == []
    assert after['text'] == before['text']
    assert 'Private experimental narrative' not in after['text']
    assert after['routes'][0]['id'] == 'testing'
    assert 'caller_context:' in after['text']


def test_latin_bigrams_are_not_relevance(env):
    store, ctx, _ = env
    wrong = accepted(store, ctx, 'wrong', title='N4 study', body='Best estimates of storage state.')
    right = accepted(store, ctx, 'right')
    result = store.search(ctx, 'pytest')
    assert [r['id'] for r in result['items']] == [right['id']]
    assert wrong['id'] not in str(result)
    assert result['items'][0]['match']['fields']
    assert store.search(ctx, 'qzxvneedle')['items'] == []


def test_title_weight_and_alias_navigation(env):
    store, ctx, _ = env
    routing(store)
    body = accepted(store, ctx, 'body', title='General result', body='pytest ' + 'ordinary words ' * 100)
    title = accepted(store, ctx, 'title', title='pytest collection')
    result = store.search(ctx, 'pytest')
    assert result['items'][0]['id'] == title['id']
    assert body['id'] in [r['id'] for r in result['items']]
    chinese = store.search(ctx, '测试收集')
    assert title['id'] in [r['id'] for r in chinese['items']]
    assert chinese['routes'][0]['id'] == 'testing'
    assert chinese['query_expansion']


def test_cards_are_not_audit_envelopes_and_full_read_is_lossless(env):
    store, ctx, _ = env
    text = 'pytest result. ' + 'Conditions apply; ' * 500
    original = accepted(store, ctx, 'long', body=text)
    card = store.search(ctx, 'pytest')['items'][0]
    assert card['id'] == original['id'] and card['preview_only']
    assert 'proposal' not in card and 'review' not in card and 'promotion' not in card
    full = store.read(ctx, [original['id']])['items'][0]
    assert full['body'] == text and full['sources'] == original['sources']
    assert full['provenance'] == original['provenance']
    assert card['read_required']


def test_pagination_is_bounded_and_revision_fenced(env):
    store, ctx, _ = env
    for i in range(6):
        accepted(store, ctx, f'item:{i}', title=f'pytest {i}')
    first = store.search(ctx, 'pytest', limit=2)
    second = store.search(ctx, 'pytest', limit=2, offset=first['next_offset'],
                          expected_revision=first['corpus_revision'])
    assert not {r['id'] for r in first['items']} & {r['id'] for r in second['items']}
    assert first['omitted'] == 4 and second['next_offset'] == 4
    assert len(json.dumps(first, ensure_ascii=True, indent=2).encode()) <= 12000
    accepted(store, ctx, 'new', title='pytest new')
    with pytest.raises(MemoryError, match='changed'):
        store.search(ctx, 'pytest', offset=first['next_offset'], expected_revision=first['corpus_revision'])


def test_oversized_card_still_has_read_path_and_progress(env):
    store, ctx, _ = env
    large = accepted(store, ctx, 'oversized', title='pytest',
                     sources=[{'uri': 'file:///research/owner.md', 'note': 'X' * 100000}])
    accepted(store, ctx, 'small', title='pytest ordinary')
    result = store.search(ctx, 'pytest')
    assert large['id'] in [r['id'] for r in result['items']]
    assert len(json.dumps(result, ensure_ascii=True, indent=2).encode()) <= 12000
    assert len(store.read(ctx, [large['id']])['items'][0]['sources'][0]['note']) == 100000


def test_reviewed_capture_is_one_call_and_payload_replay_is_exact(env):
    store, ctx, _ = env
    data = record(kind='hypothesis')
    details = {'summary': 'A possible explanation on this fixture only.', 'conditions': 'No causal conclusion.',
               'domain': 'research', 'statement_type': 'hypothesis'}
    first = store.capture(ctx, data, 'capture', review=REVIEW, details=details)
    again = store.capture(ctx, data, 'capture', review=REVIEW, details=details)
    assert first['id'] == again['id'] and again['replayed']
    full = store.read(ctx, [first['id']])['items'][0]
    assert full['kind'] == 'hypothesis' and full['effective_status'] == 'active'
    assert full['details']['conditions'] == 'No causal conclusion.'
    for change in [{'details': {**details, 'domain': 'engineering'}},
                   {'review': {**REVIEW, 'reason': 'different'}}]:
        args = {'review': REVIEW, 'details': details, **change}
        with pytest.raises(MemoryError, match='different'):
            store.capture(ctx, data, 'capture', **args)
    candidate = store.capture(ctx, record(title='uncertain'), 'candidate')
    assert store.read(ctx, [candidate['id']])['missing_ids'] == [candidate['id']]


def test_capture_validates_metadata_before_writing(env):
    store, ctx, _ = env
    with pytest.raises(MemoryError):
        store.capture(ctx, record(), 'bad', review=REVIEW, details={'share_with': ['other']})
    assert store.doctor()['projects']['demo'] == 0


def test_capture_recovery_after_published_curation(env, monkeypatch):
    store, ctx, _ = env
    publish = store._publish
    def interrupted(path, data):
        publish(path, data)
        if 'curation' in path.parts:
            raise RuntimeError('simulated transport loss after publication')
    monkeypatch.setattr(store, '_publish', interrupted)
    with pytest.raises(RuntimeError):
        store.capture(ctx, record(), 'crash', review=REVIEW, details={'domain': 'engineering'})
    monkeypatch.setattr(store, '_publish', publish)
    resumed = store.capture(ctx, record(), 'crash', review=REVIEW, details={'domain': 'engineering'})
    assert resumed['effective_status'] == 'active'
    assert store.doctor()['projects']['demo'] == 1


@pytest.mark.parametrize('boundary', ['request', 'candidate'])
def test_capture_first_publication_fences_complete_payload(env, monkeypatch, boundary):
    store, ctx, _ = env
    publish = store._publish
    def interrupted(path, data):
        publish(path, data)
        if (boundary == 'candidate' and path.suffix == '.md') or (boundary == 'request' and 'capture' in path.parts):
            raise RuntimeError('transport loss after first publication')
    monkeypatch.setattr(store, '_publish', interrupted)
    with pytest.raises(RuntimeError):
        store.capture(ctx, record(), 'first-write', review=REVIEW, details={'domain': 'research'})
    monkeypatch.setattr(store, '_publish', publish)
    for changed in [{'review': {**REVIEW, 'reason': 'different'}}, {'details': {'domain': 'engineering'}}]:
        args = {'review': REVIEW, 'details': {'domain': 'research'}, **changed}
        with pytest.raises(MemoryError) as error:
            store.capture(ctx, record(), 'first-write', **args)
        assert error.value.code == 'idempotency_conflict'
    resumed = store.capture(ctx, record(), 'first-write', review=REVIEW, details={'domain': 'research'})
    assert resumed['effective_status'] == 'active'
    assert store.doctor()['projects']['demo'] == 1


def test_capture_legacy_binding_recovers_or_fails_closed(env):
    store, ctx, _ = env
    captured = store.capture(ctx, record(), 'legacy', review=REVIEW)
    # Simulate a completed pre-repair capture: its curation journal binds the full request.
    for path in (store.root / 'capture').rglob('*.json'):
        path.unlink()
    with pytest.raises(MemoryError) as error:
        store.capture(ctx, record(), 'legacy', review={**REVIEW, 'reason': 'different'})
    assert error.value.code == 'idempotency_conflict'
    assert store.capture(ctx, record(), 'legacy', review=REVIEW)['id'] == captured['id']
    store.propose(ctx, record(title='orphan'), 'capture:unbound')
    with pytest.raises(MemoryError) as error:
        store.capture(ctx, record(title='orphan'), 'unbound', review=REVIEW)
    assert error.value.code == 'incomplete_capture'


def test_capture_concurrent_changed_payload_has_one_winner(env):
    store, ctx, _ = env
    def work(domain):
        try:
            return MemoryStore(store.root).capture(ctx, record(), 'race', review=REVIEW, details={'domain': domain})
        except MemoryError as error:
            return error.code
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(work, ['research', 'engineering']))
    assert results.count('idempotency_conflict') == 1
    assert sum(isinstance(x, dict) and x['effective_status'] == 'active' for x in results) == 1
    assert store.doctor()['projects']['demo'] == 1


@pytest.mark.parametrize('damage', ['null', 'version', 'project', 'digest'])
def test_capture_damaged_receipt_fails_before_replay(env, damage):
    store, ctx, _ = env
    store.capture(ctx, record(), 'bound', review=REVIEW)
    path = next((store.root / 'capture').rglob('*.json'))
    value = json.loads(path.read_text())
    if damage == 'null':
        value = None
    elif damage == 'version':
        value['version'] = True
    elif damage == 'project':
        value['project_id'] = 'other'
    else:
        value['digest'] = 'invalid'
    path.write_text(json.dumps(value))
    before = path.read_bytes()
    with pytest.raises(MemoryError):
        store.capture(ctx, record(), 'bound', review=REVIEW)
    assert path.read_bytes() == before


def test_retirement_is_reversible_without_rewriting_or_resurrecting(env):
    store, ctx, _ = env
    old = accepted(store, ctx, 'old')
    path = store.root / 'records/demo' / (old['id'] + '.md')
    before = path.read_bytes()
    store.curate(ctx, old['id'], REVIEW, 'retire', retired=True)
    assert path.read_bytes() == before
    assert store.read(ctx, [old['id']])['missing_ids'] == [old['id']]
    history = store.read(ctx, [old['id']], True)['items'][0]
    assert history['recall_retired'] and history['status'] == 'active'
    new = store.propose(ctx, record(title='corrected pytest'), 'new')['record']
    store.supersede(ctx, new['id'], [old['id']], REVIEW, 'correction')
    store.curate(ctx, old['id'], REVIEW, 'unretire', retired=False)
    assert store.read(ctx, [old['id']], True)['items'][0]['effective_status'] == 'superseded'
    assert path.read_bytes() == before


def test_curation_fences_and_integrity(env):
    store, ctx, _ = env
    r = accepted(store, ctx, 'target')
    first = store.curate(ctx, r['id'], REVIEW, 'annotate', details={'domain': 'engineering'})
    with pytest.raises(MemoryError):
        store.curate(ctx, r['id'], REVIEW, 'stale', details={'summary': 'new'}, expected_revision='absent')
    with pytest.raises(MemoryError):
        store.curate(ctx, r['id'], REVIEW, 'wrong-body', retired=True, expected_content_digest='0' * 64)
    path = store.root / 'curation/demo' / (r['id'] + '.json')
    doc = json.loads(path.read_text())
    doc['events'][0]['payload']['details']['domain'] = 'research'
    path.write_text(json.dumps(doc))
    with pytest.raises(MemoryError):
        store.search(ctx, 'pytest')
    assert first['curation_revision'] != 'absent'


def test_curation_concurrent_patches_keep_both_events(env):
    store, ctx, _ = env
    r = accepted(store, ctx, 'target')
    def work(pair):
        field, value = pair
        return MemoryStore(store.root).curate(ctx, r['id'], REVIEW, field, details={field: value})
    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(work, [('summary', 'Historical fixture only.'), ('conditions', 'No live bug claim.')]))
    full = store.read(ctx, [r['id']])['items'][0]
    assert full['details']['summary'] and full['details']['conditions']
    assert len(full['curation_audit']) == 2


def test_engineering_import_needs_both_opt_ins_and_is_read_only(env, tmp_path):
    store, ctx, _ = env
    other = tmp_path / 'other'
    other.mkdir()
    store.register('other', [other])
    target = {**ctx, 'cwd': str(other)}
    r = accepted(store, ctx, 'shared')
    store.curate(ctx, r['id'], REVIEW, 'share', details={'domain': 'engineering', 'share_with': ['other']})
    assert not store.search(target, 'pytest')['items']
    (store.root / 'sharing.json').write_text(json.dumps({'version': 1,
        'allow': [{'from': 'demo', 'to': 'other', 'domain': 'engineering'}]}))
    imported = store.search(target, 'pytest')['items'][0]
    assert imported['project_id'] == 'demo' and imported['imported']
    assert store.read(target, [r['id']])['items'][0]['body'] == r['body']
    with pytest.raises(MemoryError):
        store.curate(target, r['id'], REVIEW, 'foreign-write', retired=True)
    store.curate(ctx, r['id'], REVIEW, 'retire', retired=True)
    assert not store.search(target, 'pytest', include_inactive=True)['items']


def test_worktree_and_research_cannot_be_shared(env):
    store, ctx, _ = env
    for scope in ['project', 'worktree']:
        r = accepted(store, ctx, scope, scope=scope)
        with pytest.raises(MemoryError):
            store.curate(ctx, r['id'], REVIEW, scope + ':share',
                         details={'domain': 'research' if scope == 'project' else 'engineering', 'share_with': ['other']})


def test_webcodex_curation_uses_actual_identity_without_changing_legacy_bytes(env):
    store, ctx, _ = env
    r = accepted(store, ctx, 'native-origin')
    real = {**ctx, 'harness': 'webcodex', 'session_id': 'wc_sess_actual_fixture'}
    store.curate(real, r['id'], REVIEW, 'web-review', details={'domain': 'engineering'})
    full = store.read(real, [r['id']])['items'][0]
    assert full['provenance']['harness'] == 'codex'
    assert full['curation_audit'][0]['payload']['context']['harness'] == 'webcodex'
