"""WP3 lifecycle and governance: caller lineage, task memory, stale/assurance, status search,
write notices, retention (doctor --prune/--sources) and private directories."""
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import threading
import time

import pytest

from shared_memory_mcp import core
from shared_memory_mcp.core import MemoryError, MemoryStore
from shared_memory_mcp.operations import call


@pytest.fixture
def env(tmp_path):
    project = tmp_path / 'project'
    project.mkdir()
    owner = project / 'owner.md'
    owner.write_text('owner evidence\n')
    store = MemoryStore(tmp_path / 'memory')
    store.init()
    store.register('demo', [project])
    ctx = {'cwd': str(project), 'harness': 'codex', 'session_id': 's1', 'actor': 'lead-agent'}
    return store, ctx, owner


def rec(owner, title='Fixture finding', scope='project', body='Fixture owner records coverage 7.', **extra):
    return {'kind': 'observation', 'title': title, 'body': body, 'scope': scope,
            'sources': [{'uri': owner.as_uri(), 'locator': 'L1'}], **extra}


def review(owner):
    return {'reason': 'Checked against the owner', 'evidence': [{'uri': owner.as_uri(), 'locator': 'L1'}]}


def utc(text):
    return datetime.fromisoformat(text.replace('Z', '+00:00'))


def record_path(store, id):
    return store.root / 'records' / 'demo' / f'{id}.md'


def rewrite_header(path, **changes):
    raw = path.read_text('utf-8')
    header, body = raw[8:].split('\n```\n', 1)
    meta = json.loads(header)
    meta.update(changes)
    path.write_text('```json\n' + core._json(meta) + '\n```\n' + body, 'utf-8')


def age_candidate(store, id, days):
    """Controlled timestamps: move creation and every curation event into the past."""
    past = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat().replace('+00:00', 'Z')
    rewrite_header(record_path(store, id), created_at=past)
    journal = store.root / 'curation' / 'demo' / f'{id}.json'
    if journal.exists():
        doc = json.loads(journal.read_text())
        for event in doc['events']:
            event['at'] = past
        journal.write_text(core._json(doc) + '\n')


def tree_bytes(root):
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob('*'))
            if p.is_file() and '.sqlite3' not in p.name}


# --- 3.1 caller lineage and task memory ---------------------------------------

def test_declared_role_grants_no_scope_or_authority(env):
    store, ctx, owner = env
    lead = {**ctx, 'task_id': 'T1', 'role': 'lead', 'model': 'astra', 'parent_session_id': 'root-1'}
    task_record = store.capture(lead, rec(owner, 'Task note', 'task'), 'task-note', review(owner))
    # The resolved scope is identical with or without declared lineage.
    assert store.resolve(lead) == store.resolve({**ctx, 'task_id': 'T1'})
    assert 'role' not in store.resolve(lead)
    # A self-declared lead of another task still cannot see or change the task record.
    intruder = {**ctx, 'session_id': 's9', 'task_id': 'T2', 'role': 'lead'}
    assert store.read(intruder, [task_record['id']], True)['missing_ids'] == [task_record['id']]
    assert store.search(intruder, '', statuses=['active', 'candidate'])['items'] == []
    with pytest.raises(MemoryError) as raised:
        store.delete(intruder, task_record['id'], review(owner), 'withdraw-other-task')
    assert raised.value.code == 'not_found'
    for bad in ({'role': 'admin'}, {'model': ' '}, {'parent_session_id': 'x' * 300}):
        with pytest.raises(MemoryError) as raised:
            store.resolve({**ctx, **bad})
        assert raised.value.code == 'invalid_input'


def test_lineage_is_retained_as_origin_provenance_through_public_dispatch(env):
    store, ctx, owner = env
    caller = {**ctx, 'role': 'worker', 'model': 'luna-max', 'parent_session_id': 'lead-session', 'task_id': 'T1'}
    captured = call(store, 'capture', {'caller': caller, 'record': rec(owner), 'review': review(owner)})
    raw = record_path(store, captured['item']['id']).read_text()
    header = json.loads(raw[8:].split('\n```\n', 1)[0])
    assert {k: header['provenance'][k] for k in core.LINEAGE_FIELDS} == {
        'role': 'worker', 'model': 'luna-max', 'parent_session_id': 'lead-session', 'task_id': 'T1'}
    # Reviewer identity stays the four authenticated-by-nothing caller fields.
    assert set(header['review']['reviewer']) == {'cwd', 'harness', 'session_id', 'actor'}
    marker = call(store, 'withdraw', {'caller': caller, 'id': captured['item']['id'], 'review': review(owner)})
    assert marker['item']['provenance']['role'] == 'worker'


def test_task_records_default_to_fourteen_day_expiry(env):
    store, ctx, owner = env
    task = {**ctx, 'task_id': 'T1'}
    created = store.propose(task, rec(owner, scope='task'), 'task-default')['record']
    assert utc(created['expires_at']) - utc(created['created_at']) == timedelta(days=14)
    explicit = store.propose(task, rec(owner, 'Explicit', 'task', expires_at='2999-01-01T00:00:00Z'), 'task-explicit')['record']
    assert explicit['expires_at'] == '2999-01-01T00:00:00Z'
    assert 'expires_at' not in store.propose(ctx, rec(owner, 'Project'), 'project-default')['record']
    # Replay recovers the same record rather than recomputing a new expiry.
    assert store.propose(task, rec(owner, scope='task'), 'task-default')['record']['expires_at'] == created['expires_at']


def test_task_members_share_task_context_and_other_tasks_do_not(env):
    store, ctx, owner = env
    lead = {**ctx, 'task_id': 'T1', 'role': 'lead'}
    worker = {**ctx, 'session_id': 'w1', 'task_id': 'T1', 'role': 'worker', 'parent_session_id': 's1'}
    other = {**ctx, 'session_id': 'w2', 'task_id': 'T2', 'role': 'worker'}
    shared = store.capture(lead, rec(owner, 'Task T1 working note', 'task'), 'task-shared', review(owner))
    for member in (lead, worker):
        packet = store.context(member)
        assert packet['status'] == 'ok'
        assert shared['id'] in {item['id'] for item in packet['items']}
        assert 'Task T1 working note' in packet['text'] or 'Fixture owner records' in packet['text']
    packet = store.context(other)
    assert shared['id'] not in {item['id'] for item in packet['items']}
    assert 'Fixture owner records' not in packet['text']


# --- 3.2 stale and assurance ----------------------------------------------------

def test_untouched_candidate_is_stale_at_read_time_without_rewrite(env):
    store, ctx, owner = env
    old = store.capture(ctx, rec(owner, 'Old candidate'), 'old')
    fresh = store.capture(ctx, rec(owner, 'Fresh candidate'), 'fresh')
    age_candidate(store, old['id'], 8)
    age_candidate(store, fresh['id'], 6)
    before = tree_bytes(store.root)
    listed = store.search(ctx, '', statuses=['stale', 'candidate'])['items']
    assert {r['id']: r['effective_status'] for r in listed} == {old['id']: 'stale', fresh['id']: 'candidate'}
    assert store.search(ctx, '', statuses=['stale'])['items'][0]['id'] == old['id']
    assert store.read(ctx, [old['id']], True)['items'][0]['effective_status'] == 'stale'
    assert store.search(ctx, '')['items'] == []  # never default recall
    assert tree_bytes(store.root) == before  # derived, not stored
    # Any lifecycle operation (an annotation) refreshes it; approval still succeeds.
    store.curate(ctx, old['id'], review(owner), 'touch', details={'summary': 'Touched'})
    assert store.read(ctx, [old['id']], True)['items'][0]['effective_status'] == 'candidate'
    age_candidate(store, old['id'], 9)
    approved = store.promote(ctx, old['id'], review(owner), 'approve-stale')['record']
    assert approved['effective_status'] == 'active'


def test_assurance_labels_follow_reviewer_provenance(env):
    store, ctx, owner = env
    selfish = store.capture(ctx, rec(owner, 'Self'), 'self', review(owner))
    candidate = store.capture(ctx, rec(owner, 'Cross'), 'cross')
    store.promote({**ctx, 'session_id': 's2'}, candidate['id'], review(owner), 'cross-review')
    extracted = store.capture(ctx, rec(owner, 'Extracted'), 'extracted', details={'assurance': 'model-extracted'})
    plain = store.capture(ctx, rec(owner, 'Plain'), 'plain')
    dreamt = store.capture(ctx, rec(owner, 'Dreamt'), 'dreamt', review(owner))
    path = record_path(store, dreamt['id'])
    header = json.loads(path.read_text()[8:].split('\n```\n', 1)[0])
    rewrite_header(path, promotion={**header['promotion'], 'key': 'dream:' + 'a' * 32 + ':1:op'})
    # Ordinary writers cannot forge the Dreaming review marker.
    for forge in (lambda: store.promote(ctx, plain['id'], review(owner), 'dream:forged'),
                  lambda: store.delete(ctx, plain['id'], review(owner), 'dream:forged')):
        with pytest.raises(MemoryError) as raised:
            forge()
        assert raised.value.code == 'invalid_input'
    expected = {selfish['id']: 'self-reviewed', candidate['id']: 'cross-session-reviewed',
                extracted['id']: 'model-extracted', plain['id']: 'candidate', dreamt['id']: 'dreaming-reviewed'}
    assert selfish['assurance'] == 'self-reviewed' and extracted['assurance'] == 'model-extracted'
    cards = store.search(ctx, '', include_inactive=True)['items']
    assert {c['id']: c['assurance'] for c in cards} == expected
    reads = store.read(ctx, list(expected), True)['items']
    assert {r['id']: r['assurance'] for r in reads} == expected
    public = call(store, 'read', {'caller': ctx, 'ids': [selfish['id']]})
    assert public['items'][0]['assurance'] == 'self-reviewed'
    # Extraction assurance is fixed at capture; annotate cannot add or remove it.
    for target, details in ((plain['id'], {'assurance': 'model-extracted'}), (selfish['id'], {'assurance': 'model-extracted'})):
        with pytest.raises(MemoryError) as raised:
            store.curate(ctx, target, review(owner), 'forge-' + target, details=details)
        assert raised.value.code == 'immutable_assurance'
    with pytest.raises(MemoryError):
        store.capture(ctx, rec(owner, 'Bad'), 'bad', details={'assurance': 'self-reviewed'})


def test_assurance_breaks_only_exact_relevance_ties(env, monkeypatch):
    store, ctx, owner = env
    ids = iter(['0' * 31 + str(i) for i in range(1, 9)])
    monkeypatch.setattr(core.uuid, 'uuid4', lambda: type('U', (), {'hex': next(ids)})())
    selfish = store.capture(ctx, rec(owner, 'Tie topic'), 'tie-self', review(owner))  # lower id
    cross = store.capture(ctx, rec(owner, 'Tie topic'), 'tie-cross')
    store.promote({**ctx, 'session_id': 's2'}, cross['id'], review(owner), 'tie-cross-review')
    assert selfish['id'] < cross['id']
    ranked = store.search(ctx, 'tie topic')['items']
    assert [r['id'] for r in ranked] == [cross['id'], selfish['id']]
    # A better match still wins regardless of assurance.
    better = store.capture(ctx, rec(owner, 'Tie topic tie topic', body='tie topic everywhere tie topic'), 'better', review(owner))
    assert store.search(ctx, 'tie topic')['items'][0]['id'] == better['id']


# --- 3.3 status search absorbs audit ------------------------------------------------

def test_status_search_lists_every_state_without_dreaming_profile(env):
    store, ctx, owner = env
    old = store.capture(ctx, rec(owner, 'Old state'), 'old-state', review(owner))
    new = store.capture(ctx, rec(owner, 'New state'), 'new-state')
    store.supersede(ctx, new['id'], [old['id']], review(owner), 'supersede-state')
    expired = store.capture(ctx, rec(owner, 'Expired state', expires_at='2000-01-01T00:00:00Z'), 'expired-state')
    stale = store.capture(ctx, rec(owner, 'Stale state'), 'stale-state')
    age_candidate(store, stale['id'], 10)
    retired = store.capture(ctx, rec(owner, 'Retired state'), 'retired-state', review(owner))
    store.curate(ctx, retired['id'], review(owner), 'retire', retired=True)
    assert not (store.root / 'dreaming').exists()
    result = call(store, 'search', {'caller': ctx, 'statuses': ['superseded', 'expired', 'stale', 'retired']})
    assert result['status'] == 'ok' and result['notices'] == []
    assert {i['id']: i['effective_status'] for i in result['items']} == {
        old['id']: 'superseded', expired['id']: 'expired', stale['id']: 'stale', retired['id']: 'retired'}
    assert all('assurance' in i for i in result['items'])
    # Listing changes no recall eligibility.
    assert {i['id'] for i in store.search(ctx, '')['items']} == {new['id']}
    scoped = call(store, 'search', {'caller': ctx, 'scopes': ['task']})
    assert scoped['items'] == []
    paged = call(store, 'search', {'caller': ctx, 'statuses': ['superseded', 'expired', 'stale', 'retired'], 'limit': 2})
    assert len(paged['items']) == 2 and paged['next_cursor']
    rest = call(store, 'search', {'caller': ctx, 'statuses': ['superseded', 'expired', 'stale', 'retired'], 'limit': 2,
                                  'cursor': paged['next_cursor']})
    assert {i['id'] for i in paged['items'] + rest['items']} == {old['id'], expired['id'], stale['id'], retired['id']}
    with pytest.raises(MemoryError):
        store.search(ctx, '', statuses=['bogus'])


def hold_gate(root, seconds, ready):
    with sqlite3.connect(root / '.writer-gate.sqlite3', timeout=30) as connection:
        connection.execute('BEGIN IMMEDIATE')
        ready.set()
        time.sleep(seconds)


def test_status_search_waits_for_a_held_writer_gate_within_its_bound(env, monkeypatch):
    store, ctx, owner = env
    candidate = store.capture(ctx, rec(owner, 'Waiting'), 'waiting')
    ready = threading.Event()
    holder = threading.Thread(target=hold_gate, args=(store.root, 1.0, ready))
    holder.start()
    ready.wait(5)
    started = time.monotonic()
    result = call(store, 'search', {'caller': ctx, 'statuses': ['candidate']})
    elapsed = time.monotonic() - started
    holder.join()
    assert result['items'][0]['id'] == candidate['id']
    assert 0.5 <= elapsed < core.READ_WAIT_SECONDS
    # A gate held past the bound returns a typed diagnostic within the bound, not a hang.
    monkeypatch.setattr(core, 'READ_WAIT_SECONDS', 0.3)
    ready.clear()
    holder = threading.Thread(target=hold_gate, args=(store.root, 2.0, ready))
    holder.start()
    ready.wait(5)
    started = time.monotonic()
    with pytest.raises(MemoryError) as raised:
        call(store, 'search', {'caller': ctx, 'statuses': ['candidate']})
    assert raised.value.code == 'writer_busy' and time.monotonic() - started < 1.5
    holder.join()


# --- 3.4 write notices ------------------------------------------------------------

SECRETS = {
    'private-key': '-----BEGIN RSA PRIVATE KEY-----',
    'openai-key': 'sk-' + 'A1b2C3d4E5f6G7h8I9j0K',
    'aws-access-key': 'AKIA' + 'ABCDEFGHIJKLMNOP',
    'github-token': 'ghp_' + 'a' * 36,
    'slack-token': 'xoxb-' + '1234567890-abcdef',
    'google-api-key': 'AIza' + 'B' * 35,
    'jwt': 'eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U',
    'bearer-token': 'Authorization: Bearer ' + 'abcDEF123456789xyzQRS0',
}


@pytest.mark.parametrize('name', sorted(SECRETS))
def test_secret_like_capture_is_written_unchanged_with_a_notice(env, name):
    store, ctx, owner = env
    body = 'Observed config line: ' + SECRETS[name]
    result = call(store, 'capture', {'caller': ctx, 'record': rec(owner, 'Secret ' + name, body=body)})
    assert {'code': 'secret_pattern', 'pattern': name} in result['notices']
    assert record_path(store, result['item']['id']).read_text().endswith(body)


def test_annotate_notices_and_volatile_sources(env, tmp_path):
    store, ctx, owner = env
    clean = call(store, 'capture', {'caller': ctx, 'record': rec(owner, 'Clean note')})
    assert not [n for n in clean['notices'] if isinstance(n, dict) and n.get('code') == 'secret_pattern']
    annotated = call(store, 'annotate', {'caller': ctx, 'id': clean['item']['id'], 'review': review(owner),
                                         'details': {'summary': 'token ghp_' + 'b' * 36}})
    assert {'code': 'secret_pattern', 'pattern': 'github-token'} in annotated['notices']
    for uri in ('file:///tmp/scratch.md', 'file:///var/tmp/run.log', 'file:///home/u/.tmpXYZ/a.md'):
        result = store.capture(ctx, {**rec(owner, 'Volatile ' + uri), 'sources': [{'uri': uri}]}, 'volatile-' + uri)
        assert [n['code'] for n in result['notices']] == ['volatile_source']
    durable = store.capture(ctx, {**rec(owner, 'Durable'), 'sources': [{'uri': 'file:///data/owner.md'}]}, 'durable')
    assert 'notices' not in durable


# --- 3.5 retention and permissions -------------------------------------------------

def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(core._json(value) + '\n')


def synthetic_dreaming(store):
    d = store.root / 'dreaming'
    closed, open_, recovering = 'c' * 32, 'd' * 32, 'e' * 32
    shard = {'version': 1, 'kind': 'sources', 'entries': []}
    shard_digest = core._digest(shard)
    manifest = {'version': 1, 'header': {}, 'shards': [{'kind': 'sources', 'digest': shard_digest, 'count': 0}], 'counts': {}}
    manifest_digest = core._digest(manifest)
    orphan = {'version': 1, 'kind': 'memory', 'entries': [['x', {}]]}
    put(d / 'checkpoints/objectives' / f'{shard_digest}.json', shard)
    put(d / 'checkpoints/objectives' / f'{manifest_digest}.json', manifest)
    put(d / 'checkpoints/objectives' / f'{core._digest(orphan)}.json', orphan)
    published_key, unpublished_key = f'dream:{closed}:1:a', f'dream:{closed}:2:b'
    checkpoint = {'version': 1, 'run_id': closed}
    put(d / f'runs/{closed}/run.json', {'id': closed, 'profile_id': 'p', 'lane': 'L1', 'phase': 'closed',
                                         'checkpoint': checkpoint, 'receipts': {published_key: {'paths': []}},
                                         'objective_progress': {'version': 1, 'manifest': manifest_digest}})
    put(d / 'checkpoints/p-L1.json', checkpoint)
    put(d / f'runs/{closed}/drafts/{"1" * 64}.json', {'operations': [{'key': published_key}]})
    put(d / f'runs/{closed}/drafts/{"2" * 64}.json', {'operations': [{'key': unpublished_key}]})
    intent_key = f'dream:{closed}:3:c'
    put(d / f'runs/{closed}/drafts/{"3" * 64}.json', {'operations': [{'key': intent_key}]})
    put(d / f'runs/{closed}/intents/{core._digest(intent_key)}.json', {'revision': '4' * 64})
    put(d / f'runs/{open_}/run.json', {'id': open_, 'profile_id': 'p', 'lane': 'L2', 'phase': 'draft-ready', 'receipts': {}})
    put(d / f'runs/{open_}/drafts/{"5" * 64}.json', {'operations': [{'key': f'dream:{open_}:1:a'}]})
    # Closed, but its checkpoint index was never published: the marker is still needed for recovery.
    put(d / f'runs/{recovering}/run.json', {'id': recovering, 'profile_id': 'p', 'lane': 'L3', 'phase': 'closed',
                                             'checkpoint': {'version': 1, 'run_id': recovering}, 'receipts': {}})
    put(d / 'active/p-L1.json', {'run_id': closed})
    put(d / 'active/p-L2.json', {'run_id': open_})
    put(d / 'active/p-L3.json', {'run_id': recovering})
    put(d / 'receipts/keep.json', {'sealed': True})
    put(d / f'views/demo/research/current.json', {'revision': 'v'})
    put(d / 'issues/keep.json', {'issue': True})
    backups = store.root / '.state' / 'config-backups'
    for stamp in ('20260101', '20260102', '20260103', '20260104', '20260105'):
        put(backups / f'{stamp}T000000Z-abcd' / 'config.toml.bak', {'stamp': stamp})
    return {f'dreaming/active/p-L1.json', f'dreaming/checkpoints/objectives/{core._digest(orphan)}.json',
            f'dreaming/runs/{closed}/drafts/{"2" * 64}.json',
            '.state/config-backups/20260101T000000Z-abcd', '.state/config-backups/20260102T000000Z-abcd'}


def test_prune_dry_run_lists_and_apply_removes_only_listed_paths(env):
    from shared_memory_mcp.cli import main
    store, ctx, owner = env
    active = store.capture(ctx, rec(owner, 'Kept'), 'kept', review(owner))
    store.curate(ctx, active['id'], review(owner), 'kept-note', details={'summary': 'Kept'})
    expected = synthetic_dreaming(store)
    before = tree_bytes(store.root)
    dry = core.MemoryStore(store.root)
    from shared_memory_mcp.maintenance import prune
    listed = prune(dry)
    assert listed['applied'] is False
    assert {i['path'] for i in listed['items']} == expected and all(i['reason'] for i in listed['items'])
    assert tree_bytes(store.root) == before
    assert main(['--root', str(store.root), 'doctor', '--prune', '--apply']) == 0
    after = tree_bytes(store.root)
    removed = {p for p in before if p not in after}
    assert all(any(p == e or p.startswith(e + '/') for e in expected) for p in removed)
    assert all(not os.path.exists(store.root / e) for e in expected)
    canonical = [p for p in before if p.startswith(('records/', 'curation/', 'capture/', 'registry.json')) or
                 '/receipts/' in '/' + p or '/views/' in p or '/issues/' in p or p.endswith('run.json') or '/intents/' in p]
    assert canonical and all(after[p] == before[p] for p in canonical)
    assert prune(dry)['items'] == []
    with pytest.raises(SystemExit):
        main(['--root', str(store.root), 'doctor', '--bogus'])


def test_doctor_sources_and_private_directory_permissions(env, capsys):
    from shared_memory_mcp.cli import main
    store, ctx, owner = env
    gone = owner.parent / 'moved.md'
    gone.write_text('x')
    lost = store.capture(ctx, {**rec(owner, 'Lost'), 'sources': [{'uri': gone.as_uri()}]}, 'lost')
    store.capture(ctx, rec(owner, 'Present'), 'present')
    gone.unlink()
    for directory in (store.root, store.root / 'records', store.root / 'records' / 'demo', store.root / 'curation' / 'demo'):
        assert directory.stat().st_mode & 0o777 == 0o700, directory
    os.chmod(store.root / 'records' / 'demo', 0o755)
    assert main(['--root', str(store.root), 'doctor', '--sources']) == 0
    report = json.loads(capsys.readouterr().out)
    assert [i['id'] for i in report['sources']['items']] == [lost['id']]
    assert report['sources']['items'][0]['missing'] == [gone.as_uri()]
    assert [d['path'] for d in report['permissions']['deviations']] == [str(store.root / 'records' / 'demo')]
    assert (store.root / 'records' / 'demo').stat().st_mode & 0o777 == 0o755  # reported, never changed
    assert main(['--root', str(store.root), 'doctor', '--apply']) == 2


# --- 3.6 startup units and live-correction locator guidance ------------------------

def test_startup_units_carry_assurance_and_task_units(env):
    store, ctx, owner = env
    task = {**ctx, 'task_id': 'T1'}
    shared = store.capture(task, rec(owner, 'Task unit', 'task'), 'task-unit', review(owner))
    packet = store.context(task)
    unit = next(i for i in packet['items'] if i['id'] == shared['id'])
    assert unit['assurance'] == 'self-reviewed'
    assert 'self-reviewed] ' in packet['text']


def test_live_correction_without_locator_suggests_transcript_file(env):
    store, ctx, owner = env
    basis = {'kind': 'direct-current-user', 'excerpt': 'Use path B, not A.', 'original_locator': None,
             'history_gap': '', 'review_method': 'foreground agent observed the message'}
    with pytest.raises(MemoryError) as raised:
        store.capture(ctx, rec(owner, 'Correction'), 'live-empty', review(owner), live_correction=basis)
    assert 'transcript' in str(raised.value) and 'file:///' in str(raised.value)
    result = store.capture(ctx, rec(owner, 'Correction'), 'live-ok', review(owner),
                           live_correction={**basis, 'history_gap': 'Native history not yet flushed'})
    hint = next(n for n in result['notices'] if n['code'] == 'live_locator_missing')
    assert 'transcript' in hint['message']
