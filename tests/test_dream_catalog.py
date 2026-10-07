"""Disposable public-schema source catalog fixtures; no native history reads."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import json
import os

import pytest

from shared_memory_mcp.core import MemoryError
from shared_memory_mcp.dream_catalog import SourceCatalog, validate_source_grants
from shared_memory_mcp.dream_sources import read_source, check_snapshot, MAX_BYTES
from test_dream_sources import HEADER, codex_message, line, attest, claude_message


def catalog(tmp_path, *, directory=True, values=None):
    root = tmp_path / 'store'; root.mkdir()
    sources = tmp_path / 'sources'; sources.mkdir()
    path = sources / 'a.jsonl'
    path.write_bytes(b''.join(line(x) for x in (values or [HEADER, codex_message()])))
    grant = {'id':'history', 'path':str(sources if directory else path), 'kind':'directory' if directory else 'file',
        'format':'codex','schema':'codex-rollout-v1','native_version':'fixture-v1'}
    store = SimpleNamespace(root=root)
    profile = {'source_grants':[grant]}
    return SourceCatalog(store, 'fixture', profile), profile, path


def test_discovery_pages_selection_and_materialized_consumer(tmp_path):
    c, profile, path = catalog(tmp_path)
    for name in ['b.jsonl', 'c.jsonl']:
        (path.parent/name).write_bytes(path.read_bytes())
    first = c.list('history', limit=2)
    assert [x['path'] for x in first['items']] == ['a.jsonl','b.jsonl']
    assert c.list('history',cursor=first['next_cursor'],limit=2)['items'][0]['path']=='c.jsonl'
    assert c.resolve() == []
    public = c.read({'grant_id':'history','path':'a.jsonl'})
    # A fresh catalog instance resolves server-owned page state for a Run.
    spec = SourceCatalog(c.store,'fixture',profile).resolve([public['selection']])[0]
    assert c.authorized(spec)
    assert read_source(spec)['events']==public['events']
    assert check_snapshot(spec, public['version'])=='valid'


def test_exact_file_has_same_catalog_and_retained_prefix_fixture(tmp_path):
    c, _, path = catalog(tmp_path,directory=False)
    assert c.list('history')['items'][0]['path']==''
    spec=c.resolve()[0]
    assert read_source(spec)['events'][0]['event_id']=='u1'
    public=c.read({'grant_id':'history'})
    assert read_source(c.resolve([public['selection']])[0])['events']==public['events']


@pytest.mark.parametrize('selection',[{'grant_id':'history','path':'../outside'}, {'grant_id':'history','path':'/etc/passwd'},
    {'grant_id':'other','path':'a.jsonl'},{'grant_id':'history','path':'AGENTS.md'},
    {'grant_id':'history','path':'a.jsonl','state':{'delegated':False}}])
def test_model_cannot_expand_grants_or_supply_parser_state(tmp_path,selection):
    c,_,_=catalog(tmp_path)
    with pytest.raises(MemoryError): c.read(selection)


def test_symlink_components_and_replaced_directory_fenced(tmp_path):
    c,_,path=catalog(tmp_path)
    (path.parent/'link').symlink_to(path.parent, target_is_directory=True)
    with pytest.raises((MemoryError,OSError)): c.read({'grant_id':'history','path':'link/a.jsonl'})
    assert all(x['path']!='link' for x in c.list('history')['items'])
    page=c.read({'grant_id':'history','path':'a.jsonl'})
    spec=c.resolve([page['selection']])[0]
    old=path.parent.with_name('old');path.parent.rename(old)
    path.parent.mkdir();os.link(old/'a.jsonl',path)
    assert not c.authorized(spec)
    assert check_snapshot(spec,page['version'])=='unverifiable'


@pytest.mark.parametrize('change',['append','replace','edit'])
def test_frozen_page_epoch_rejects_mutation_for_cursor_and_publication(tmp_path,change):
    c,_,path=catalog(tmp_path,values=[HEADER,codex_message('One'),codex_message('Two',identifier='u2')])
    page=c.read({'grant_id':'history','path':'a.jsonl'},max_events=1)
    spec=c.resolve([page['selection']])[0]
    before=path.stat()
    if change=='append':
        with path.open('ab') as f:f.write(line(codex_message('Later',identifier='u3')))
    elif change=='replace':
        replacement=path.with_name('new');replacement.write_bytes(path.read_bytes());replacement.replace(path)
    else:
        path.write_bytes(path.read_bytes().replace(b'One',b'Ono'))
        os.utime(path,ns=(before.st_atime_ns,before.st_mtime_ns))
    with pytest.raises(MemoryError):c.read({'grant_id':'history','path':'a.jsonl'},cursor=page['next_cursor'])
    with pytest.raises(MemoryError):c.resolve([page['selection']])
    assert check_snapshot(spec,page['version'])!='valid'


def test_grant_revocation_and_page_swaps_are_rejected(tmp_path):
    c,profile,path=catalog(tmp_path)
    page=c.read({'grant_id':'history','path':'a.jsonl'})
    spec=c.resolve([page['selection']])[0]
    changed=deepcopy(profile);changed['source_grants'][0]['native_version']='other'
    revoked=SourceCatalog(c.store,'fixture',changed)
    assert not revoked.authorized(spec)
    with pytest.raises(MemoryError):revoked.resolve([page['selection']])
    with pytest.raises(MemoryError):c.read({'grant_id':'history','path':'a.jsonl'},cursor={'state':{}})
    (path.parent/'b.jsonl').write_bytes(path.read_bytes())
    with pytest.raises(MemoryError):c.resolve([{**page['selection'],'path':'b.jsonl'}])


def test_listing_cursor_detects_changed_listing(tmp_path):
    c,_,path=catalog(tmp_path)
    (path.parent/'b').write_text('one')
    first=c.list('history',limit=1)
    (path.parent/'c').write_text('two')
    with pytest.raises(MemoryError):c.list('history',cursor=first['next_cursor'])


def test_supported_history_continues_beyond_eight_mib_and_1024_ids(tmp_path):
    values=[HEADER]+[codex_message('public text '*760,identifier=f'u{i}') for i in range(1150)]
    c,_,path=catalog(tmp_path,values=values)
    assert path.stat().st_size>MAX_BYTES
    selection={'grant_id':'history','path':'a.jsonl'}
    cursor=None; ids=[]; max_read=0
    while True:
        page=c.read(selection,cursor=cursor,max_bytes=262144,max_events=128)
        ids.extend(e['event_id'] for e in page['events'])
        max_read=max(max_read,page['coverage']['read_bytes'])
        cursor=page['next_cursor']
        if not cursor:break
    assert ids==[f'u{i}' for i in range(1150)]
    assert max_read<=262144
    assert page['version']['consumed']==path.stat().st_size
    assert read_source(c.resolve([page['selection']])[0])['events'][-1]['event_id']=='u1149'


def test_cross_page_duplicate_and_codex_owner_preserved(tmp_path):
    child={'type':'session_meta','payload':{'id':'child','cli_version':'fixture-v1','source':'cli'}}
    user=codex_message('Synthetic public fixture')
    c,profile,path=catalog(tmp_path,values=[child,user,HEADER,codex_message('Second',identifier='u2'),user])
    profile['source_grants'][0]['attestations']=attest(user)
    c=SourceCatalog(c.store,'fixture',profile)
    first=c.read({'grant_id':'history','path':'a.jsonl'},max_events=1)
    second=c.read({'grant_id':'history','path':'a.jsonl'},cursor=first['next_cursor'])
    assert [e['event_id'] for e in second['events']]==['u2']
    assert second['events'][0]['session']=='child' and second['events'][0]['human']=='unknown'
    assert second['coverage']['excluded']==2


def test_claude_selected_ancestry_fails_closed_across_pages(tmp_path):
    c,profile,path=catalog(tmp_path,values=[claude_message('A',None),claude_message('C','A')])
    profile['source_grants'][0].update(format='claude',schema='claude-jsonl-v1')
    c=SourceCatalog(c.store,'fixture',profile)
    selection={'grant_id':'history','path':'a.jsonl','leaf_id':'C'}
    first=c.read(selection,max_events=1)
    second=c.read(selection,cursor=first['next_cursor'],max_events=1)
    assert first['events']==second['events']==[]
    assert any(x['reason']=='branch_ancestry_not_in_window' for x in second['coverage']['gaps'])


def test_source_grant_may_not_include_store(tmp_path):
    c,profile,_=catalog(tmp_path)
    profile['source_grants'][0]['path']=str(tmp_path)
    with pytest.raises(MemoryError):validate_source_grants(c.store,profile['source_grants'])


def test_actual_open_rejects_replacement_symlink_race(tmp_path, monkeypatch):
    c,_,path=catalog(tmp_path)
    outside=tmp_path/'outside.jsonl';outside.write_bytes(line(HEADER)+line(codex_message('Outside forbidden')))
    original_open=os.open
    replaced=False
    def racing_open(component, flags, *args, **kwargs):
        nonlocal replaced
        if component=='a.jsonl' and not replaced:
            replaced=True
            path.unlink();path.symlink_to(outside)
        return original_open(component,flags,*args,**kwargs)
    monkeypatch.setattr(os,'open',racing_open)
    with pytest.raises(MemoryError):c.read({'grant_id':'history','path':'a.jsonl'})
    assert replaced


def test_read_cursor_replays_exact_page_after_lost_response(tmp_path):
    c,_,_=catalog(tmp_path,values=[HEADER,codex_message('One'),codex_message('Two',identifier='u2')])
    selection={'grant_id':'history','path':'a.jsonl'}
    first=c.read(selection,max_events=1)
    second=c.read(selection,cursor=first['next_cursor'])
    assert second['events'][0]['event_id']=='u2'
    replay=c.read(selection,cursor=first['next_cursor'])
    assert replay==second
    assert read_source(c.resolve([second['selection']])[0])['events']==second['events']


def test_direct_selected_directory_file_rejects_replaced_grant_at_open(tmp_path):
    c,_,path=catalog(tmp_path)
    spec=c.resolve([{'grant_id':'history','path':'a.jsonl'}])[0]
    old=path.parent.with_name('old');path.parent.rename(old)
    path.parent.mkdir();path.write_bytes((old/'a.jsonl').read_bytes())
    with pytest.raises(MemoryError):read_source(spec)


def test_page_descriptor_retains_no_transcript_and_identity_is_stable(tmp_path):
    marker='PUBLIC_TRANSCRIPT_MUST_NOT_BE_MIRRORED'
    c,_,path=catalog(tmp_path,values=[HEADER,codex_message(marker)])
    selection={'grant_id':'history','path':'a.jsonl'}
    first=c.read(selection)
    second=c.read(selection)
    assert first['selection']==second['selection']
    spec=c.resolve([first['selection']])[0]
    assert marker not in json.dumps(spec)
    with c._db() as db:
        retained=''.join(row[0] for row in db.execute('SELECT body FROM handles'))
    assert marker not in retained
    assert read_source(spec)['events'][0]['text']==marker


def test_accepted_source_entitlement_survives_append_but_page_is_stale(tmp_path):
    c,_,path=catalog(tmp_path)
    page=c.read({'grant_id':'history','path':'a.jsonl'})
    spec=c.resolve([page['selection']])[0]
    with path.open('ab') as stream:stream.write(line(codex_message('Later',identifier='u2')))
    assert c.authorized(spec)
    assert check_snapshot(spec,page['version'])=='stale'
    with pytest.raises(MemoryError):read_source(spec)


def test_catalog_handle_eviction_keeps_live_continuation_and_run_descriptor(tmp_path,monkeypatch):
    import shared_memory_mcp.dream_catalog as module
    monkeypatch.setattr(module,'MAX_HANDLES',4)
    values=[HEADER]+[codex_message(identifier=f'u{i}') for i in range(20)]
    c,_,_=catalog(tmp_path,values=values)
    selection={'grant_id':'history','path':'a.jsonl'}
    first=c.read(selection,max_events=1)
    old_spec=c.resolve([first['selection']])[0]
    cursor=first['next_cursor'];ids=['u0']
    while cursor:
        page=c.read(selection,cursor=cursor,max_events=1)
        assert c.read(selection,cursor=cursor,max_events=1)==page
        ids.extend(e['event_id'] for e in page['events'])
        cursor=page['next_cursor']
    assert ids==[f'u{i}' for i in range(20)]
    assert read_source(old_spec)['events'][0]['event_id']=='u0'
    with c._db() as db:
        assert db.execute('SELECT count(*) FROM handles').fetchone()[0]<=4
    # Expired locator fails explicitly; its captured Run descriptor remains valid.
    with pytest.raises(MemoryError):c.resolve([first['selection']])


def test_lost_response_control_rejects_old_consumed_cursor_implementation(tmp_path,monkeypatch):
    c,_,_=catalog(tmp_path,values=[HEADER,codex_message('One'),codex_message('Two',identifier='u2')])
    selection={'grant_id':'history','path':'a.jsonl'}
    first=c.read(selection,max_events=1)
    second=c.read(selection,cursor=first['next_cursor'])
    original_get=c._get
    def consumed_cursor(db,grant,kind,token):
        body=original_get(db,grant,kind,token)
        if kind=='read' and body.get('completed'):
            raise MemoryError('invalid_cursor','Nearest wrong implementation consumed the read cursor')
        return body
    with monkeypatch.context() as context:
        context.setattr(c,'_get',consumed_cursor)
        with pytest.raises(MemoryError) as error:
            replay=c.read(selection,cursor=first['next_cursor'])
            assert replay==second
        assert error.value.code=='invalid_cursor'
    assert c.read(selection,cursor=first['next_cursor'])==second


def test_concurrent_cursor_retry_returns_same_page(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    c,_,_=catalog(tmp_path,values=[HEADER,codex_message('One'),codex_message('Two',identifier='u2')])
    selection={'grant_id':'history','path':'a.jsonl'}
    first=c.read(selection,max_events=1)
    with ThreadPoolExecutor(max_workers=2) as executor:
        results=list(executor.map(lambda _: c.read(selection,cursor=first['next_cursor']),range(2)))
    assert results[0]==results[1]
    assert results[0]['events'][0]['event_id']=='u2'


@pytest.mark.parametrize('operation',['read','list','snapshot','reconstruct','prefix'])
@pytest.mark.parametrize('trailing_slash',[False,True])
def test_actual_grant_dirfd_rejects_aba_directory_replacement(tmp_path,monkeypatch,operation,trailing_slash):
    c,profile,path=catalog(tmp_path)
    if trailing_slash:
        profile['source_grants'][0]['path'] += '/'
        c=SourceCatalog(c.store,'fixture',profile)
    outside=tmp_path/'not-granted';outside.mkdir()
    (outside/'a.jsonl').write_bytes(line(HEADER)+line(codex_message('OUTSIDE_GRANTED_DIRECTORY')))
    page=c.read({'grant_id':'history','path':'a.jsonl'})
    page_spec=c.resolve([page['selection']])[0]
    prefix_spec=c.resolve([{'grant_id':'history','path':'a.jsonl'}])[0]
    saved=tmp_path/'saved'
    original_open=os.open
    opened=0
    attacked=False
    def racing_open(component,flags,*args,**kwargs):
        nonlocal opened,attacked
        if component=='sources':
            opened+=1
            trigger={'read':2,'list':2,'snapshot':2,'reconstruct':6,'prefix':1}[operation]
            if opened==trigger:
                attacked=True
                path.parent.rename(saved);outside.rename(path.parent)
                try:
                    # Capture the wrong root dirfd, then restore the lexical path
                    # before the caller's pre/post pathname checks can see it.
                    return original_open(component,flags,*args,**kwargs)
                finally:
                    path.parent.rename(outside);saved.rename(path.parent)
        return original_open(component,flags,*args,**kwargs)
    monkeypatch.setattr(os,'open',racing_open)
    if operation=='snapshot':
        assert check_snapshot(page_spec,page['version'])!='valid'
    else:
        with pytest.raises(MemoryError) as error:
            if operation=='read':
                c.read({'grant_id':'history','path':'a.jsonl'})
            elif operation=='list':
                c.list('history')
            elif operation=='reconstruct':
                read_source(page_spec)
            else:
                read_source(prefix_spec)
        assert error.value.code in {'source_changed','unsafe_source'}
    assert attacked
