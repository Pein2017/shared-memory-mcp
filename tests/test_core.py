import json
import multiprocessing
import os
from pathlib import Path
import subprocess
import pytest
from shared_memory_mcp.core import MemoryStore, MemoryError


@pytest.fixture
def environment(tmp_path):
    project = tmp_path / 'project'
    project.mkdir()
    store = MemoryStore(tmp_path / 'memory')
    store.init()
    store.register('demo',[project])
    ctx = {'cwd':str(project),'harness':'codex','session_id':'s1','actor':'researcher'}
    return store,ctx,project


def rec(scope='project',kind='observation',body='可重复的观察，待检验。',**kwargs):
    return {'kind':kind,'scope':scope,'title':'观测机制','body':body,'sources':[{'uri':'file:///research/evidence.md','locator':'L10','note':'original evidence'}],**kwargs}


REVIEW = {'reason':'reviewed against linked evidence','evidence':[{'uri':'file:///research/review.md','locator':'L12'}]}


def active(store,ctx,key,record=None):
    proposed = store.propose(ctx,record or rec(),key)
    return store.promote(ctx,proposed['record']['id'],REVIEW,key+'-review')['record']


def test_delete_hides_active_knowledge_preserves_history_and_target_bytes(environment,monkeypatch):
    store,ctx,_ = environment
    target = active(store,ctx,'withdraw-active')
    path = store.root/'records/demo'/f'{target["id"]}.md'
    before = path.read_bytes()
    writes = []
    publish = store._publish
    def track(path,data):
        writes.append(path)
        publish(path,data)
    monkeypatch.setattr(store,'_publish',track)
    result = store.delete(ctx,target['id'],REVIEW,'withdraw-review')
    marker = result['record']
    assert len(writes) == 1 and writes[0] != path
    assert marker['withdraws'] == target['id'] and marker['effective_status'] == 'withdrawal'
    assert marker['kind'] == 'decision' and marker['review']['reason'] == REVIEW['reason']
    assert marker['sources'] == REVIEW['evidence']
    assert not {'proposal','expires_at','supersedes'} & marker.keys()
    assert path.read_bytes() == before
    assert store.search(ctx,'')['items'] == store.context(ctx)['items'] == []
    assert store.read(ctx,[target['id'],marker['id']])['missing_ids'] == [target['id'],marker['id']]
    history = store.read(ctx,[target['id'],marker['id']],True)['items']
    assert [r['effective_status'] for r in history] == ['withdrawn','withdrawal']
    assert store.delete(ctx,target['id'],REVIEW,'withdraw-review')['replayed']
    assert len(writes) == 1


@pytest.mark.parametrize('operation',['promote','supersede'])
def test_withdrawn_candidate_cannot_be_published(environment,operation):
    store,ctx,_ = environment
    predecessor = active(store,ctx,'candidate-predecessor')
    candidate = store.propose(ctx,rec(),'withdraw-candidate')['record']
    store.delete(ctx,candidate['id'],REVIEW,'candidate-delete')
    before = {p.name:p.read_bytes() for p in (store.root/'records/demo').glob('*.md')}
    with pytest.raises(MemoryError) as error:
        if operation == 'promote':
            store.promote(ctx,candidate['id'],REVIEW,'candidate-review')
        else:
            store.supersede(ctx,candidate['id'],[predecessor['id']],REVIEW,'candidate-review')
    assert error.value.code == 'immutable_record'
    assert {p.name:p.read_bytes() for p in (store.root/'records/demo').glob('*.md')} == before


def test_successor_withdrawal_never_restores_predecessor(environment,monkeypatch):
    from datetime import datetime,timezone
    import shared_memory_mcp.core as core
    store,ctx,_ = environment
    old = active(store,ctx,'withdraw-predecessor')
    successor = store.propose(ctx,rec(expires_at='2099-01-01T00:00:00Z'),'withdraw-successor')['record']
    store.supersede(ctx,successor['id'],[old['id']],REVIEW,'withdraw-successor-review')
    store.delete(ctx,successor['id'],REVIEW,'withdraw-successor-delete')
    class Future(datetime):
        @classmethod
        def now(cls,tz=None): return datetime(2100,1,1,tzinfo=timezone.utc)
    monkeypatch.setattr(core,'datetime',Future)
    assert store.search(ctx,'')['items'] == []
    assert [r['effective_status'] for r in store.read(ctx,[old['id'],successor['id']],True)['items']] == ['superseded','withdrawn']
    fresh = store.propose(ctx,rec(),'withdraw-fresh')['record']
    with pytest.raises(MemoryError) as error:
        store.supersede(ctx,fresh['id'],[successor['id']],REVIEW,'withdraw-fresh-review')
    assert error.value.code == 'scope_mismatch'


@pytest.mark.parametrize('state',['candidate','expired','superseded'])
def test_delete_accepts_visible_ordinary_history(environment,state):
    store,ctx,_ = environment
    if state == 'candidate':
        target = store.propose(ctx,rec(),'history-target')['record']
    elif state == 'expired':
        target = store.propose(ctx,rec(expires_at='2000-01-01T00:00:00Z'),'history-target')['record']
    else:
        target = active(store,ctx,'history-target')
        successor = store.propose(ctx,rec(),'history-successor')['record']
        store.supersede(ctx,successor['id'],[target['id']],REVIEW,'history-update')
    store.delete(ctx,target['id'],REVIEW,'history-delete')
    assert store.read(ctx,[target['id']],True)['items'][0]['effective_status'] == 'withdrawn'


@pytest.mark.parametrize('scope',['project','worktree','task'])
def test_delete_preserves_exact_qualifiers_and_rejects_invisible_targets(environment,tmp_path,scope):
    store,ctx,project = environment
    ctx = {**ctx,'task_id':'owned'}
    target = active(store,ctx,'scoped-delete',rec(scope))
    if scope == 'project':
        other = tmp_path/'other-project';other.mkdir()
        store.register('other',[other])
        wrong = {**ctx,'cwd':str(other)}
    elif scope == 'worktree':
        other = tmp_path/'other-worktree';other.mkdir()
        store.register('demo',[other])
        wrong = {**ctx,'cwd':str(other)}
    else:
        wrong = {**ctx,'task_id':'other'}
    with pytest.raises(MemoryError) as error:
        store.delete(wrong,target['id'],REVIEW,'invisible-delete')
    assert error.value.code == 'not_found'
    marker = store.delete(ctx,target['id'],REVIEW,'scoped-withdrawal-review')['record']
    assert store._qualifier(marker) == store._qualifier(target)
    if scope == 'project':
        assert not {'worktree_id','task_id'} & marker.keys()
    assert store.read(wrong,[marker['id']],True)['items'] == []


def test_delete_replay_conflicts_and_marker_targets_fail_closed(environment):
    store,ctx,_ = environment
    target = active(store,ctx,'key-target')
    with pytest.raises(MemoryError) as error:
        store.delete(ctx,target['id'],REVIEW,'key-target-review')
    assert error.value.code == 'idempotency_conflict'
    marker = store.delete(ctx,target['id'],REVIEW,'delete-key')['record']
    for review,key,code in [({**REVIEW,'reason':'changed'},'delete-key','idempotency_conflict'),(REVIEW,'new-delete-key','already_withdrawn')]:
        with pytest.raises(MemoryError) as error:
            store.delete(ctx,target['id'],review,key)
        assert error.value.code == code
    candidate = store.propose(ctx,rec(),'key-candidate')['record']
    with pytest.raises(MemoryError) as error:
        store.promote(ctx,candidate['id'],REVIEW,'delete-key')
    assert error.value.code == 'idempotency_conflict'
    with pytest.raises(MemoryError) as error:
        store.delete(ctx,marker['id'],REVIEW,'marker-delete')
    assert error.value.code == 'invalid_target'
    assert store.doctor()['projects']['demo'] == 3


@pytest.mark.parametrize('change',['missing','scope','marker_target','duplicate','proposal','expiry','supersedes','candidate','kind','ordinary_without_proposal','link_digest'])
def test_malformed_withdrawal_corpus_fails_closed(environment,change):
    import uuid
    from shared_memory_mcp.core import _digest
    store,ctx,_ = environment
    target = active(store,ctx,'malformed-target')
    other = active(store,ctx,'malformed-other')
    marker = store.delete(ctx,target['id'],REVIEW,'malformed-delete')['record']
    if change == 'missing': marker['withdraws'] = 'a'*32
    elif change == 'scope': marker.update(scope='task',worktree_id=store.resolve(ctx)['worktree_id'],task_id='invisible')
    elif change == 'marker_target': marker['withdraws'] = marker['id']
    elif change == 'duplicate':
        marker.update(id=uuid.uuid4().hex,promotion={**marker['promotion'],'key':'duplicate-delete'})
    elif change == 'proposal': marker['proposal'] = target['proposal']
    elif change == 'expiry': marker['expires_at'] = '2099-01-01T00:00:00Z'
    elif change == 'supersedes': marker['supersedes'] = [other['id']]
    elif change == 'candidate': marker['status'] = 'candidate'
    elif change == 'kind': marker['kind'] = 'observation'
    elif change == 'ordinary_without_proposal':
        marker = target
        marker.pop('proposal')
    elif change == 'link_digest': marker['withdraws'] = other['id']
    if change != 'link_digest': marker['content_digest'] = _digest(store._content(marker))
    store._write(marker,create=change=='duplicate')
    # Validation must inspect even a malformed marker invisible to the caller.
    with pytest.raises(MemoryError) as error:
        store.search(ctx,'')
    assert error.value.code == 'corrupt_record'
    # Navigation does not load the corpus; task recall still validates every record.
    assert store.context(ctx)['records_not_loaded']
    result = store.context(ctx,query='观测机制')
    assert result['status'] == 'invalid' and result['items'] == [] and result['text'] == ''


def _delete_writer(root,ctx,id,key,queue):
    try:
        result = MemoryStore(root).delete(ctx,id,REVIEW,key)
        queue.put(('ok',result['record']['id'],result['replayed']))
    except MemoryError as exc:
        queue.put((exc.code,None,None))


@pytest.mark.parametrize('same_key',[True,False])
def test_concurrent_delete_has_one_publication(environment,same_key):
    store,ctx,_ = environment
    target = active(store,ctx,'parallel-delete-target')
    spawn = multiprocessing.get_context('spawn')
    queue = spawn.Queue()
    workers = [spawn.Process(target=_delete_writer,args=(str(store.root),ctx,target['id'],'parallel-delete' if same_key else str(i),queue)) for i in range(4)]
    for process in workers: process.start()
    for process in workers:
        process.join(30)
        assert process.exitcode == 0
    results = [queue.get(timeout=5) for _ in workers]
    queue.close()
    if same_key:
        assert all(r[0] == 'ok' for r in results) and len({r[1] for r in results}) == 1
        assert sum(r[2] is False for r in results) == 1
    else:
        assert sorted(r[0] for r in results) == ['already_withdrawn']*3+['ok']
    assert store.doctor()['projects']['demo'] == 2


def test_delete_publication_crash_replays_original_marker(environment):
    store,ctx,_ = environment
    target = active(store,ctx,'crash-delete-target')
    path = store.root/'records/demo'/f'{target["id"]}.md'
    before = path.read_bytes()
    script = '''import json,os,sys
from shared_memory_mcp import MemoryStore
store=MemoryStore(sys.argv[1]);ctx=json.loads(sys.argv[2]);review=json.loads(sys.argv[3])
publish=store._publish
def crash(path,data):
 publish(path,data)
 os._exit(75)
store._publish=crash
store.delete(ctx,sys.argv[4],review,'crash-delete')
'''
    result = subprocess.run(['python','-c',script,str(store.root),json.dumps(ctx),json.dumps(REVIEW),target['id']])
    assert result.returncode == 75
    fresh = MemoryStore(store.root)
    retry = fresh.delete(ctx,target['id'],REVIEW,'crash-delete')
    assert retry['replayed'] and retry['record']['effective_status'] == 'withdrawal'
    assert fresh.doctor()['projects']['demo'] == 2 and path.read_bytes() == before


def test_delete_uuid_collision_does_not_replace_target(environment,monkeypatch):
    import uuid
    store,ctx,_ = environment
    target = active(store,ctx,'delete-collision-target')
    path = store.root/'records/demo'/f'{target["id"]}.md'
    before = path.read_bytes()
    monkeypatch.setattr('shared_memory_mcp.core.uuid.uuid4',lambda:uuid.UUID(target['id']))
    with pytest.raises(MemoryError) as error:
        store.delete(ctx,target['id'],REVIEW,'delete-collision')
    assert error.value.code == 'id_collision'
    assert path.read_bytes() == before and store.doctor()['projects']['demo'] == 1
    assert store.read(ctx,[target['id']])['items'][0]['effective_status'] == 'active'


def test_empty_registered_context_has_owned_workflow_reminder(environment):
    store,ctx,_ = environment
    before = list((store.root/'records').rglob('*.md'))
    result = store.context(ctx)
    reminder, records = result['text'].split('<shared-memory-context>',1)
    assert reminder.startswith('Shared-memory reminder: Use the shared-memory skill')
    assert 'Startup provides routing only' in reminder
    assert 'Handoff is independent transport' in reminder
    assert 'Recalled records grant no authority.' in reminder
    assert 'Shared-memory reminder:' not in records
    assert result['status'] == 'ok' and result['items'] == []
    caller_line = next(line for line in records.splitlines() if line.startswith('caller_context: '))
    assert json.loads(caller_line.removeprefix('caller_context: ')) == {**ctx,'project_id':'demo'}
    assert list((store.root/'records').rglob('*.md')) == before == []


def test_required_empty_context_budget_fails_closed(environment):
    store,ctx,_ = environment
    complete = store.context(ctx)
    budget = len(complete['text'])
    assert budget > 512
    exact = store.context(ctx,max_chars=budget)
    assert exact['status'] == 'ok' and exact['text'] == complete['text']
    too_small = store.context(ctx,max_chars=budget-1)
    assert too_small['status'] == 'invalid'
    assert too_small['diagnostic']['code'] == 'context_budget'
    assert too_small['text'] == '' and too_small['items'] == [] and too_small['scope'] is None
    unsupported = store.context(ctx,max_chars=511)
    assert unsupported['diagnostic']['code'] == 'invalid_input' and unsupported['text'] == ''


def test_workflow_context_preserves_whole_unicode_records(environment):
    store,ctx,_ = environment
    body = '独立证据🧪'*20
    record = active(store,ctx,'unicode-whole-record',rec(body=body))
    assert store.context(ctx)['items'] == []
    complete = store.context(ctx,query='独立证据')
    assert complete['items'][0]['body'] == body and body in complete['text']
    assert len(complete['text'].encode('utf-8')) > len(complete['text'])
    included = store.context(ctx,query='独立证据',max_chars=len(complete['text'])+100)
    assert included['items'][0]['id'] == record['id']
    assert included['items'][0]['body'] == body
    omitted = store.context(ctx,query='独立证据',max_chars=len(complete['text'])-1)
    assert omitted['status'] == 'ok' and omitted['items'] == []
    assert omitted['omitted'] == 1 and omitted['truncated']
    assert body not in omitted['text'] and record['id'] not in omitted['text']
    assert len(omitted['text']) <= len(complete['text'])-1


def test_capture_review_replay_immutable_utf8(environment):
    store,ctx,_ = environment
    proposed = store.propose(ctx,rec(kind='hypothesis'),'capture')
    identifier = proposed['record']['id']
    empty_context = store.context(ctx)
    assert empty_context['items'] == []
    caller_line = next(line for line in empty_context['text'].splitlines() if line.startswith('caller_context: '))
    caller = json.loads(caller_line.removeprefix('caller_context: '))
    assert caller == {**ctx,'project_id':'demo'}
    assert store.read(ctx,[identifier])['missing_ids'] == [identifier]
    assert store.read(ctx,[identifier],True)['items'][0]['effective_status'] == 'candidate'
    assert store.propose(ctx,rec(kind='hypothesis'),'capture')['record']['id'] == identifier
    with pytest.raises(MemoryError,match='different payload'):
        store.propose(ctx,rec(body='other'),'capture')
    accepted = store.promote(ctx,identifier,REVIEW,'review')
    canonical = store.root / 'records/demo' / (identifier+'.md')
    before = canonical.read_bytes()
    assert accepted['record']['kind'] == 'hypothesis'
    assert accepted['record']['review']['reviewer']['actor'] == ctx['actor']
    assert store.promote(ctx,identifier,REVIEW,'review')['replayed']
    with pytest.raises(MemoryError) as error:
        store.promote(ctx,identifier,REVIEW,'different-review')
    assert error.value.code == 'immutable_record'
    assert canonical.read_bytes() == before
    with pytest.raises(MemoryError):
        store.promote(ctx,identifier,{**REVIEW,'reason':'different'},'review')
    result = store.search(ctx,'观测机制')
    assert result['items'][0]['body'] == rec()['body']
    assert 'provenance' not in result['items'][0]
    assert store.read(ctx,[identifier])['items'][0]['provenance']['harness'] == 'codex'


def test_unknown_hint_and_nested_identity_fail_closed(environment,tmp_path):
    store,ctx,project = environment
    unknown = tmp_path / 'other';unknown.mkdir()
    result = store.context({**ctx,'cwd':str(unknown),'project_id':'demo'})
    assert result['status'] == 'unmapped' and result['text'] == '' and result['items'] == []
    with pytest.raises(MemoryError) as error:
        store.propose({**ctx,'cwd':str(unknown)},rec(),'bad')
    assert error.value.code == 'unmapped_scope'
    invalid = store.context({**ctx,'project_id':'other'})
    assert invalid['status'] == 'invalid' and invalid['text'] == '' and invalid['items'] == []
    nested = project / 'nested';nested.mkdir()
    subprocess.run(['git','init','-q',str(nested)],check=True)
    unmapped = store.context({**ctx,'cwd':str(nested)})
    assert unmapped['status'] == 'unmapped' and unmapped['text'] == '' and unmapped['items'] == []
    store.register('nested',[nested])
    assert store.resolve({**ctx,'cwd':str(nested)})['project_id'] == 'nested'
    with pytest.raises(MemoryError):
        store.register('duplicate',[nested])
    registry = json.loads((store.root/'registry.json').read_text())
    registry['projects'].append({'id':'ambiguous','roots':[str(nested)],'git_common_dirs':[]})
    (store.root/'registry.json').write_text(json.dumps(registry))
    ambiguous = store.context({**ctx,'cwd':str(nested)})
    assert ambiguous['status'] == 'ambiguous' and ambiguous['text'] == '' and ambiguous['items'] == []
    with pytest.raises(MemoryError) as error:
        store.doctor()
    assert error.value.code == 'ambiguous_scope'


def test_new_git_identity_needs_rebinding(environment):
    store,ctx,project = environment
    subprocess.run(['git','init','-q',str(project)],check=True)
    assert store.context(ctx)['status'] == 'unmapped'
    store.register('demo',[project])
    assert store.context(ctx)['status'] == 'ok'


def test_project_worktree_task_isolation(tmp_path):
    main = tmp_path/'main';main.mkdir()
    subprocess.run(['git','init','-q',str(main)],check=True)
    subprocess.run(['git','-C',str(main),'-c','user.name=Fixture','-c','user.email=fixture@example.test','commit','--allow-empty','-qm','fixture'],check=True)
    linked = tmp_path/'linked'
    subprocess.run(['git','-C',str(main),'worktree','add','-q',str(linked)],check=True)
    store = MemoryStore(tmp_path/'memory');store.init();store.register('demo',[main])
    ctx = {'cwd':str(main),'harness':'pi','session_id':'session','actor':'reader','task_id':'taskA'}
    linked_ctx = {**ctx,'cwd':str(linked)}
    project_record = active(store,ctx,'project',rec())
    worktree_record = active(store,ctx,'worktree',rec('worktree'))
    task_record = active(store,ctx,'task',rec('task'))
    assert store.resolve(linked_ctx)['project_id'] == 'demo'
    assert store.resolve(linked_ctx)['worktree_id'] != store.resolve(ctx)['worktree_id']
    assert {r['id'] for r in store.search(linked_ctx,'')['items']} == {project_record['id']}
    assert {r['id'] for r in store.search({**ctx,'task_id':'taskB'},'')['items']} == {project_record['id'],worktree_record['id']}
    other = tmp_path/'other';other.mkdir();store.register('other',[other])
    assert store.read({**ctx,'cwd':str(other)},[project_record['id']],True)['items'] == []
    assert store.context(ctx,query='观测机制',max_chars=6000)['items']
    assert task_record['task_id'] == 'taskA'
    with pytest.raises(MemoryError):
        store.propose({k:v for k,v in ctx.items() if k != 'task_id'},rec('task'),'missing-task')


def test_expiry_filter_before_limits_and_full_history(environment):
    store,ctx,_ = environment
    expired = store.propose(ctx,rec(expires_at='2000-01-01T00:00:00Z'),'expired')['record']
    with pytest.raises(MemoryError) as error:
        store.promote(ctx,expired['id'],REVIEW,'expired-review')
    assert error.value.code == 'expired_record'
    accepted = active(store,ctx,'good')
    assert store.search(ctx,'',limit=1)['items'][0]['id'] == accepted['id']
    history = store.search(ctx,'',include_inactive=True)
    assert {r['effective_status'] for r in history['items']} == {'active','expired'}
    assert store.read(ctx,[expired['id']],True)['items'][0]['effective_status'] == 'expired'


def test_supersession_one_publication_and_cache_independent(environment,monkeypatch):
    store,ctx,_ = environment
    old = active(store,ctx,'old')
    candidate = store.propose(ctx,rec(body='revised fact'),'new')['record']
    before = (store.root/'records/demo'/f'{old["id"]}.md').read_bytes()
    calls = []
    publish = store._publish
    def track(path,data):
        calls.append(path)
        publish(path,data)
    monkeypatch.setattr(store,'_publish',track)
    promoted = store.supersede(ctx,candidate['id'],[old['id']],REVIEW,'supersede')
    assert len(calls) == 1
    assert (store.root/'records/demo'/f'{old["id"]}.md').read_bytes() == before
    (store.root/'.writer-gate.sqlite3').unlink()
    fresh = MemoryStore(store.root)
    assert fresh.read(ctx,[old['id']],True)['items'][0]['effective_status'] == 'superseded'
    assert fresh.search(ctx,'')['items'][0]['id'] == candidate['id']
    assert fresh.supersede(ctx,candidate['id'],[old['id']],REVIEW,'supersede')['replayed']
    third = fresh.propose(ctx,rec(),'third')['record']
    with pytest.raises(MemoryError):
        fresh.supersede(ctx,third['id'],[old['id']],REVIEW,'again')
    wrong_scope = fresh.propose(ctx,rec('worktree'),'wrong-scope')['record']
    with pytest.raises(MemoryError):
        fresh.supersede(ctx,wrong_scope['id'],[candidate['id']],REVIEW,'wrong-scope-review')


def test_corrupt_header_body_and_mixed_scope_fail_closed(environment):
    store,ctx,_ = environment
    accepted = active(store,ctx,'accepted')
    path = store.root/'records/demo'/f'{accepted["id"]}.md'
    raw = path.read_text();path.write_text(raw+'tampered')
    result = store.context(ctx,query='观测机制')
    assert result['status'] == 'invalid' and result['text'] == ''
    with pytest.raises(MemoryError) as error:
        store.read(ctx,[accepted['id']],True)
    assert error.value.code == 'corrupt_record'
    path.write_text(raw)
    header,body = raw[8:].split('\n```\n',1)
    metadata = json.loads(header);metadata['task_id'] = 'injected-task'
    path.write_text('```json\n'+json.dumps(metadata)+'\n```\n'+body)
    with pytest.raises(MemoryError,match='Mixed or missing scope'):
        store.search(ctx,'')


@pytest.mark.parametrize('changes',[{'kind':'active-context'},{'kind':[]},{'sources':[]},{'sources':[{'uri':'relative/path'}]},{'expires_at':'2027-01-01'},{'scope':'global'},{'body':''},{'project_id':'forged'}])
def test_record_boundary_types_fail_closed(environment,changes):
    store,ctx,_ = environment
    with pytest.raises(MemoryError):
        store.propose(ctx,{**rec(),**changes},'bad')
    assert store.doctor()['projects']['demo'] == 0


def test_context_unicode_bounds_and_corpus_limit(environment,monkeypatch):
    store,ctx,_ = environment
    active(store,ctx,'short')
    active(store,ctx,'long',rec(body='证据'*20000))
    result = store.context(ctx,query='观测机制',max_chars=1400)
    assert len(result['text']) <= 1400 and result['truncated'] and result['omitted'] >= 1
    assert '<shared-memory-context>' in result['text']
    import shared_memory_mcp.core as core
    monkeypatch.setattr(core,'MAX_RECORDS',1)
    result = store.context(ctx,query='观测机制')
    assert result['status'] == 'invalid' and result['diagnostic']['code'] == 'corpus_limit'


def _writer(root,ctx,key):
    store = MemoryStore(root)
    store.propose(ctx,rec(body='parallel '+key),key)


def test_cross_process_serialization_no_lost_writes(environment):
    store,ctx,_ = environment
    workers = [multiprocessing.get_context('spawn').Process(target=_writer,args=(str(store.root),ctx,str(i))) for i in range(8)]
    for process in workers: process.start()
    for process in workers:
        process.join(30)
        assert process.exitcode == 0
    result = store.search(ctx,'',include_inactive=True)
    assert len(result['items']) == 8
    assert len({r['id'] for r in result['items']}) == 8


def test_rename_before_sqlite_commit_recovery(environment):
    store,ctx,_ = environment
    script = '''import json,os,sys
from shared_memory_mcp import MemoryStore
store=MemoryStore(sys.argv[1]);ctx=json.loads(sys.argv[2]);record=json.loads(sys.argv[3])
publish=store._publish
def crash(path,data):
 publish(path,data)
 os._exit(73)
store._publish=crash
store.propose(ctx,record,'crash-key')
'''
    result = subprocess.run(['python','-c',script,str(store.root),json.dumps(ctx),json.dumps(rec())])
    assert result.returncode == 73
    retry = MemoryStore(store.root).propose(ctx,rec(),'crash-key')
    assert retry['replayed']
    assert store.doctor()['projects']['demo'] == 1
    with pytest.raises(MemoryError):
        store.propose(ctx,rec(body='different crash payload'),'crash-key')


def test_guard_sensitivity_detects_removed_retry(environment,monkeypatch):
    store,ctx,_ = environment
    def invariant(key):
        a=store.propose(ctx,rec(),key)['record']['id']
        b=store.propose(ctx,rec(),key)['record']['id']
        assert a == b, 'Consumer replay invariant detects duplicate publication'
    invariant('baseline')
    monkeypatch.setattr(store,'_retry',lambda *args:None)
    with pytest.raises(AssertionError,match='replay invariant'):
        invariant('mutation')


def test_duplicate_metadata_and_symlink_fail_closed(environment,tmp_path):
    store,ctx,_=environment
    record=active(store,ctx,'duplicate')
    path=store.root/'records/demo'/f'{record["id"]}.md'
    raw=path.read_text()
    path.write_text(raw.replace('{','{"scope":"task",',1))
    with pytest.raises(MemoryError,match='Duplicate JSON metadata key'):
        store.search(ctx,'')
    path.write_text(raw)
    external=tmp_path/'external.md';external.write_text(raw)
    path.unlink();path.symlink_to(external)
    with pytest.raises(MemoryError,match='Symlink'):
        store.search(ctx,'')


def test_scope_filter_sensitivity(environment,monkeypatch):
    store,ctx,project=environment
    accepted=active(store,ctx,'scope-sensitivity',rec('task')) if 'task_id' in ctx else active(store,{**ctx,'task_id':'owned'},'scope-sensitivity',rec('task'))
    other_ctx={**ctx,'task_id':'other'}
    def invariant():
        assert store.read(other_ctx,[accepted['id']],True)['items'] == [], 'Consumer scope invariant rejects another task'
    invariant()
    monkeypatch.setattr(store,'_visible',lambda *args:True)
    with pytest.raises(AssertionError,match='scope invariant'):
        invariant()


@pytest.mark.parametrize('operation',['promote','supersede'])
def test_review_rename_crash_replay(environment,operation):
    store,ctx,_=environment
    old=active(store,ctx,'predecessor')
    candidate=store.propose(ctx,rec(body='recovery candidate'),'crash-review-candidate')['record']
    old_bytes=(store.root/'records/demo'/f'{old["id"]}.md').read_bytes()
    script='''import json,os,sys
from shared_memory_mcp import MemoryStore
store=MemoryStore(sys.argv[1]);ctx=json.loads(sys.argv[2]);review=json.loads(sys.argv[3])
publish=store._publish
def crash(path,data):
 publish(path,data)
 os._exit(74)
store._publish=crash
if sys.argv[4]=='promote':store.promote(ctx,sys.argv[5],review,'crash-review')
else:store.supersede(ctx,sys.argv[5],[sys.argv[6]],review,'crash-review')
'''
    result=subprocess.run(['python','-c',script,str(store.root),json.dumps(ctx),json.dumps(REVIEW),operation,candidate['id'],old['id']])
    assert result.returncode == 74
    fresh=MemoryStore(store.root)
    if operation=='promote':
        retry=fresh.promote(ctx,candidate['id'],REVIEW,'crash-review')
    else:
        retry=fresh.supersede(ctx,candidate['id'],[old['id']],REVIEW,'crash-review')
        assert fresh.read(ctx,[old['id']],True)['items'][0]['effective_status']=='superseded'
    assert retry['replayed'] and retry['record']['effective_status']=='active'
    assert (store.root/'records/demo'/f'{old["id"]}.md').read_bytes()==old_bytes
    assert store.doctor()['projects']['demo']==2


def test_proposal_uuid_collision_never_overwrites_canonical_record(environment,monkeypatch):
    import uuid
    store,ctx,_ = environment
    original = active(store,ctx,'original-collision-owner')
    path = store.root/'records/demo'/f'{original["id"]}.md'
    original_bytes = path.read_bytes()
    monkeypatch.setattr('shared_memory_mcp.core.uuid.uuid4',lambda:uuid.UUID(original['id']))
    with pytest.raises(MemoryError) as error:
        store.propose(ctx,rec(body='collision must not replace accepted content'),'new-collision-key')
    assert error.value.code == 'id_collision'
    assert path.read_bytes() == original_bytes
    assert store.doctor()['projects']['demo'] == 1
    assert store.read(ctx,[original['id']])['items'][0]['body'] == original['body']


def test_registered_git_subdirectory_does_not_claim_siblings_or_linked_worktrees(tmp_path):
    repo=tmp_path/'repo';repo.mkdir()
    subprocess.run(['git','init','-q',str(repo)],check=True)
    subprocess.run(['git','-C',str(repo),'-c','user.name=Fixture','-c','user.email=fixture@example.test','commit','--allow-empty','-qm','fixture'],check=True)
    registered=repo/'registered-subdir';registered.mkdir()
    sibling=repo/'unregistered-sibling';sibling.mkdir()
    linked=tmp_path/'linked'
    subprocess.run(['git','-C',str(repo),'worktree','add','-q',str(linked)],check=True)
    linked_subdir=linked/'registered-subdir';linked_subdir.mkdir()
    store=MemoryStore(tmp_path/'memory');store.init()
    registration=store.register('subdir-only',[registered])
    ctx={'cwd':str(sibling),'harness':'codex','session_id':'scope-regression','actor':'test'}
    assert store.context(ctx)['status'] == 'unmapped'
    assert registration['project']['git_common_dirs'] == []
    assert store.context({**ctx,'cwd':str(linked_subdir)})['status'] == 'unmapped'
    scoped_ctx={**ctx,'cwd':str(registered)}
    assert store.resolve(scoped_ctx)['project_id'] == 'subdir-only'
    owned=active(store,scoped_ctx,'subdir-owned',rec('worktree'))
    assert store.read(scoped_ctx,[owned['id']])['items'][0]['id'] == owned['id']
    nested=registered/'independent';nested.mkdir()
    subprocess.run(['git','init','-q',str(nested)],check=True)
    assert store.context({**ctx,'cwd':str(nested)})['status'] == 'unmapped'


def test_origin_git_locators_survive_head_changes_review_and_replay(tmp_path):
    repo=tmp_path/'git-origin';repo.mkdir()
    subprocess.run(['git','init','-q','--initial-branch=memory-fixture',str(repo)],check=True)
    def commit(message):
        subprocess.run(['git','-C',str(repo),'-c','user.name=Fixture','-c','user.email=fixture@example.test','commit','--allow-empty','-qm',message],check=True)
        return subprocess.run(['git','-C',str(repo),'rev-parse','HEAD'],check=True,capture_output=True,text=True).stdout.strip()
    first_head=commit('original evidence checkout')
    store=MemoryStore(tmp_path/'memory');store.init();store.register('demo',[repo])
    ctx={'cwd':str(repo),'harness':'codex','session_id':'origin-fixture','actor':'researcher'}
    proposed=store.propose(ctx,rec(),'git-origin-capture')['record']
    original_provenance=proposed['provenance']
    assert original_provenance['git'] == {'commit':first_head,'branch':'memory-fixture'}
    second_head=commit('later checkout')
    assert second_head != first_head
    assert store.propose(ctx,rec(),'git-origin-capture')['record']['provenance'] == original_provenance
    promoted=store.promote(ctx,proposed['id'],REVIEW,'git-origin-review')['record']
    assert promoted['provenance'] == original_provenance
    original_bytes=(store.root/'records/demo'/f'{proposed["id"]}.md').read_bytes()
    replacement=store.propose(ctx,rec(body='updated evidence'),'git-replacement')['record']
    assert replacement['provenance']['git']['commit'] == second_head
    third_head=commit('checkout moved after capture')
    assert third_head != second_head
    superseded=store.supersede(ctx,replacement['id'],[proposed['id']],REVIEW,'git-supersede')['record']
    assert superseded['provenance'] == replacement['provenance']
    assert store.promote(ctx,proposed['id'],REVIEW,'git-origin-review')['record']['provenance'] == original_provenance
    assert store.supersede(ctx,replacement['id'],[proposed['id']],REVIEW,'git-supersede')['record']['provenance'] == replacement['provenance']
    assert (store.root/'records/demo'/f'{proposed["id"]}.md').read_bytes() == original_bytes
    assert store.read(ctx,[replacement['id']])['items'][0]['provenance']['git']['commit'] == second_head


def test_git_provenance_unborn_detached_and_legacy_records(tmp_path):
    repo=tmp_path/'git-states';repo.mkdir()
    subprocess.run(['git','init','-q','--initial-branch=unborn-fixture',str(repo)],check=True)
    store=MemoryStore(tmp_path/'memory');store.init();store.register('demo',[repo])
    ctx={'cwd':str(repo),'harness':'pi','session_id':'git-states','actor':'test'}
    unborn=store.propose(ctx,rec(),'unborn')['record']
    assert unborn['provenance']['git'] == {'commit':None,'branch':'unborn-fixture'}
    assert store.read(ctx,[unborn['id']],True)['items'][0]['provenance']['git']['commit'] is None
    subprocess.run(['git','-C',str(repo),'-c','user.name=Fixture','-c','user.email=fixture@example.test','commit','--allow-empty','-qm','first commit'],check=True)
    head=subprocess.run(['git','-C',str(repo),'rev-parse','HEAD'],check=True,capture_output=True,text=True).stdout.strip()
    subprocess.run(['git','-C',str(repo),'checkout','--detach','-q'],check=True)
    detached=store.propose(ctx,rec(),'detached')['record']
    assert detached['provenance']['git'] == {'commit':head,'branch':None}
    path=store.root/'records/demo'/f'{unborn["id"]}.md'
    raw=path.read_text();header,body=raw[8:].split('\n```\n',1)
    metadata=json.loads(header);del metadata['provenance']['git']
    path.write_text('```json\n'+json.dumps(metadata)+'\n```\n'+body)
    assert 'git' not in store.read(ctx,[unborn['id']],True)['items'][0]['provenance']


@pytest.mark.parametrize('locator',[{'commit':'not-a-commit','branch':'branch'},{'commit':None,'branch':7},{'commit':None}])
def test_git_provenance_metadata_fails_closed(environment,locator):
    store,ctx,_=environment
    record=store.propose(ctx,rec(),'bad-locator')['record']
    assert 'git' not in record['provenance']
    path=store.root/'records/demo'/f'{record["id"]}.md'
    header,body=path.read_text()[8:].split('\n```\n',1)
    metadata=json.loads(header);metadata['provenance']['git']=locator
    path.write_text('```json\n'+json.dumps(metadata)+'\n```\n'+body)
    with pytest.raises(MemoryError) as error:
        store.read(ctx,[record['id']],True)
    assert error.value.code == 'corrupt_record'


def test_search_large_body_has_hard_byte_bound_and_explicit_full_read(environment):
    store,ctx,_ = environment
    body='large evidence '+('A'*100000)
    record=active(store,ctx,'search-large',rec(body=body))
    result=store.search(ctx,'large')
    assert len(json.dumps(result,ensure_ascii=False).encode('utf-8')) <= 12000
    assert result['items'][0]['id'] == record['id']
    assert 'body' not in result['items'][0]
    assert result['items'][0]['body_omitted'] is True
    assert result['items'][0]['body_chars'] == len(body)
    assert result['body_omitted_count'] == 1
    assert result['omitted'] == 0 and result['truncated']
    assert store.read(ctx,[record['id']])['items'][0]['body'] == body
    contextual=store.context(ctx,'large',max_chars=6000)
    assert contextual['items'][0]['id'] == record['id']
    assert contextual['items'][0]['preview_only'] and contextual['items'][0]['read_required']
    assert body not in contextual['text']
    assert len(contextual['text']) <= 6000


def test_search_many_long_metadata_records_are_bounded_and_accounted(environment):
    store,ctx,_ = environment
    for i in range(12):
        active(store,ctx,'long-metadata-'+str(i),rec(title='metadata match '+str(i),sources=[{'uri':'file:///research/metadata.md','note':'证据出处'*200}]))
    result=store.search(ctx,'metadata match',limit=12)
    assert len(json.dumps(result,ensure_ascii=False).encode('utf-8')) <= 12000
    assert 0 < len(result['items']) < 12
    assert result['omitted'] == 12-len(result['items'])
    assert result['truncated']
    assert result == store.search(ctx,'metadata match',limit=12)
    limited=store.search(ctx,'metadata match',limit=2)
    assert len(json.dumps(limited,ensure_ascii=False).encode('utf-8')) <= 12000
    assert limited['omitted'] == 12-len(limited['items'])
    for item in result['items']:
        assert store.read(ctx,[item['id']])['items'][0]['sources'] == item['sources']


def test_context_discloses_preview_and_read_keeps_complete_record(environment):
    store,ctx,_=environment
    body='complete context '+('B'*1600)
    record=active(store,ctx,'context-complete-body',rec(body=body))
    assert store.search(ctx,'complete context')['items'][0]['body_omitted']
    contextual=store.context(ctx,'complete context',max_chars=6000)
    assert contextual['items'][0]['id'] == record['id']
    assert contextual['items'][0]['body_omitted'] and contextual['items'][0]['read_required']
    assert store.read(ctx,[record['id']])['items'][0]['body'] == body


def test_installed_sdk_search_envelope_and_text_representation_are_bounded(environment):
    import asyncio
    import shutil
    pytest.importorskip('mcp')
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    server=shutil.which('shared-memory-mcp')
    if not server:
        pytest.skip('An installed shared-memory-mcp entrypoint is required')
    store,ctx,_=environment
    record=active(store,ctx,'sdk-large-search',rec(body='SDK large '+('C'*100000)))
    async def verify():
        params=StdioServerParameters(command=server,args=['--root',str(store.root)],env={key:value for key,value in os.environ.items() if key != 'PYTHONPATH'})
        async with stdio_client(params) as (read,write):
            async with ClientSession(read,write) as session:
                await session.initialize()
                response=await session.call_tool('search',{'context':ctx,'query':'SDK large'})
                assert not response.isError, response
                payload=response.structuredContent or json.loads(response.content[0].text)
                assert len(json.dumps(payload,ensure_ascii=False).encode('utf-8')) <= 12000
                assert len(response.content[0].text.encode('utf-8')) <= 12000
                assert payload['items'][0]['id'] == record['id']
                assert payload['items'][0]['body_omitted']
                assert payload['items'][0]['sources'] == record['sources']
                assert 'provenance' not in payload['items'][0]
                full = await session.call_tool('read',{'context':ctx,'ids':[record['id']]})
                full_payload = full.structuredContent or json.loads(full.content[0].text)
                assert full_payload['items'][0]['provenance'] == record['provenance']
    asyncio.run(verify())
