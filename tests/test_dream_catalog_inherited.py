"""Trusted-profile reads and frozen-range controls using disposable sources."""
from copy import deepcopy
from contextlib import contextmanager
import os
import subprocess
import sys

import pytest

from shared_memory_mcp.core import MemoryError
from shared_memory_mcp.dream_catalog import SourceCatalog
from shared_memory_mcp.dream_sources import check_snapshot, read_source
from test_dream_catalog import catalog
from test_dream_sources import HEADER, codex_message, line


def inherited(tmp_path, **kwargs):
    c, profile, path = catalog(tmp_path, **kwargs)
    profile['read_access'] = 'inherited'
    return SourceCatalog(c.store, 'fixture', profile), profile, path


def absolute(path, **kwargs):
    return {'absolute_path': str(path), 'format': 'codex', 'schema': 'codex-rollout-v1', **kwargs}


def test_inherited_unregistered_source_roundtrip_and_revocation(tmp_path):
    c, profile, path = inherited(tmp_path)
    outside = tmp_path / 'unregistered.jsonl'
    outside.write_bytes(path.read_bytes())
    page = c.read(absolute(outside))
    spec = c.resolve([page['selection']])[0]
    assert read_source(spec)['events'] == page['events']
    assert c.authorized(spec)
    restricted = deepcopy(profile)
    restricted.pop('read_access')
    denied = SourceCatalog(c.store, 'fixture', restricted)
    assert not denied.authorized(spec)
    for selection in [absolute(outside), page['selection'], {**absolute(outside), 'read_access': 'inherited'}]:
        with pytest.raises(MemoryError):
            denied.read(selection)
    with pytest.raises(MemoryError):
        SourceCatalog(c.store, 'another-caller', profile).resolve([page['selection']])


def test_inherited_discovery_has_bounded_pages_without_total_quota(tmp_path):
    c, _, path = inherited(tmp_path)
    roots = [tmp_path / name for name in ['old-pi', 'old-codex']]
    for root in roots:
        root.mkdir()
        for i in range(103):
            (root / f'{i:03}.jsonl').write_bytes(path.read_bytes())
        (root / '.env').write_text('credential')
    for root in roots:
        cursor, files = None, []
        while True:
            page = c.list(str(root), cursor=cursor, limit=17)
            assert len(page['items']) <= 17
            files.extend(x['absolute_path'] for x in page['items'])
            cursor = page['next_cursor']
            if not cursor:
                break
        assert len(files) == 103
        assert c.read(absolute(files[-1]))['events'][0]['event_id'] == 'u1'


@pytest.mark.parametrize('name', ['.env', '.env.local', 'credentials.json', 'auth.json'])
def test_inherited_sensitive_paths_and_raw_store_excluded(tmp_path, name):
    c, _, path = inherited(tmp_path)
    forbidden = tmp_path / name
    forbidden.write_bytes(path.read_bytes())
    with pytest.raises(MemoryError):
        c.read(absolute(forbidden))
    raw = c.store.root / 'raw.jsonl'
    raw.write_bytes(path.read_bytes())
    with pytest.raises(MemoryError):
        c.read(absolute(raw))


def test_inherited_sensitive_payload_and_schema_still_filtered(tmp_path):
    c, _, path = inherited(tmp_path, values=[HEADER, codex_message('sk-' + 'x' * 24)])
    page = c.read(absolute(path))
    assert not page['events']
    assert any(g['reason'] == 'sensitive_content_excluded' for g in page['coverage']['gaps'])
    for selected in [ {'absolute_path': str(path)}, absolute(path, schema='unknown'),
                      {**absolute(path), 'attestations': {}} ]:
        with pytest.raises(MemoryError):
            c.read(selected)


@pytest.mark.parametrize('name', ['AGENTS.md', 'SKILL.md'])
def test_inherited_instruction_document_is_untrusted_readable_source(tmp_path, name):
    c, _, _ = inherited(tmp_path)
    source = tmp_path / name
    source.write_text('Readable original source, not execution authority.')
    selected = {'absolute_path': str(source), 'format': 'document', 'schema': 'document-v1'}
    page = c.read(selected)
    assert read_source(c.resolve([page['selection']])[0])['events'][0]['text'] == source.read_text()


def test_inherited_open_obeys_actual_os_permissions(tmp_path):
    c, _, path = inherited(tmp_path)
    path.chmod(0)
    # Root can read chmod(000); an isolated subprocess uses the OS's unprivileged boundary.
    for parent in [tmp_path, *tmp_path.parents]:
        if str(parent).startswith('/tmp/pytest-of-'):
            parent.chmod(0o755)
    c.store.root.chmod(0o777)
    script = '''
import sys
from types import SimpleNamespace
from pathlib import Path
from shared_memory_mcp.core import MemoryError
from shared_memory_mcp.dream_catalog import SourceCatalog
import os
if os.geteuid() == 0:
    os.setgroups([])
    os.setgid(65534)
    os.setuid(65534)
c = SourceCatalog(SimpleNamespace(root=Path(sys.argv[1])), 'os-denied',
                  {'read_access': 'inherited', 'source_grants': []})
try:
    c.read({'absolute_path': sys.argv[2], 'format': 'codex', 'schema': 'codex-rollout-v1'})
except MemoryError as e:
    assert e.code == 'source_unavailable', e.code
else:
    raise AssertionError('OS denied source was admitted')
'''
    result = subprocess.run([sys.executable, '-B', '-c', script, str(c.store.root), str(path)],
                            capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_frozen_catalog_append_keeps_pages_cursor_and_retry_before_cutoff(tmp_path):
    c, _, path = catalog(tmp_path, values=[HEADER, codex_message('One'), codex_message('Two', identifier='u2')])
    selected = {'grant_id': 'history', 'path': path.name}
    first = c.read(selected, max_events=1)
    spec = c.resolve([first['selection']])[0]
    with path.open('ab') as stream:
        stream.write(line(codex_message('Later', identifier='u3')))
    assert check_snapshot(spec, first['version']) == 'valid'
    assert read_source(spec)['events'] == first['events']
    second = c.read(selected, cursor=first['next_cursor'])
    assert [e['event_id'] for e in second['events']] == ['u2']
    assert second['version']['cutoff'] == first['version']['cutoff']
    assert second['next_cursor'] is None
    assert c.read(selected, cursor=first['next_cursor']) == second
    assert [e['event_id'] for e in c.read(selected)['events']] == ['u1', 'u2', 'u3']


@pytest.mark.parametrize('change', ['header', 'truncate', 'replace'])
def test_catalog_cursor_rejects_changed_consumed_dependency(tmp_path, change):
    c, _, path = catalog(tmp_path, values=[HEADER, codex_message('One'), codex_message('Two', identifier='u2')])
    selected = {'grant_id': 'history', 'path': path.name}
    first = c.read(selected, max_events=1)
    if change == 'header':
        path.write_bytes(path.read_bytes().replace(b'fixture-v1', b'fixture-v2'))
    elif change == 'truncate':
        path.write_bytes(path.read_bytes()[:first['version']['consumed']])
    else:
        replacement = path.with_name('replacement')
        replacement.write_bytes(path.read_bytes())
        replacement.replace(path)
    with pytest.raises(MemoryError):
        c.read(selected, cursor=first['next_cursor'])


def test_freeze_defers_unfinished_event_and_does_not_extend_on_resume(tmp_path):
    c, _, path = catalog(tmp_path, values=[HEADER, codex_message('One')])
    completed_bytes = path.stat().st_size
    pending = line(codex_message('Later', identifier='u2'))
    with path.open('ab') as stream:
        stream.write(pending[:-2])
    frozen = c.freeze({'grant_id': 'history', 'path': path.name})
    assert frozen['selection']['cutoff'] == completed_bytes
    assert frozen['deferred_bytes'] == len(pending) - 2
    assert frozen['identity'] == [path.stat().st_dev, path.stat().st_ino]
    with path.open('ab') as stream:
        stream.write(pending[-2:])
    page = c.read(frozen['selection'])
    assert [e['event_id'] for e in page['events']] == ['u1']
    assert page['coverage']['complete']
    assert read_source(c.resolve([page['selection']])[0])['events'] == page['events']
    assert [e['event_id'] for e in c.read(c.freeze({'grant_id': 'history', 'path': path.name})['selection'])['events']] == ['u1', 'u2']


@pytest.mark.parametrize('reader', ['catalog', 'prefix'])
def test_pi_append_retains_cutoff_graph_and_rebuilds_after_cache_eviction(tmp_path, reader):
    from test_dream_pi_ancestry import pi_values, pi_event
    c, profile, path = catalog(tmp_path, values=pi_values('private'))
    profile['source_grants'][0].update(format='pi', schema='pi-session-v3')
    c = SourceCatalog(c.store, 'fixture', profile)
    selected = {'grant_id': 'history', 'path': path.name}
    spec = c.resolve([selected])[0]
    first = c.read(selected, max_events=1) if reader == 'catalog' else read_source(spec, max_events=1)
    frozen_spec = c.resolve([first['selection']])[0] if reader == 'catalog' else spec
    with path.open('ab') as stream:
        stream.write(line(pi_event('Later', 'C')))
    assert check_snapshot(frozen_spec, first['version']) == 'valid'
    with c._db() as db:
        db.execute('DELETE FROM structures')
    if reader == 'catalog':
        assert read_source(frozen_spec)['events'] == first['events']
        second = c.read(selected, cursor=first['next_cursor'])
    else:
        second = read_source(spec, cursor=first['cursor'])
    assert second['version']['cutoff'] == first['version']['cutoff']
    assert all(e['event_id'] != 'Later' for e in second['events'])
    assert all(e['branch'] == 'C' for e in second['events'])


def test_legacy_catalog_descriptor_keeps_its_sealed_epoch_fence(tmp_path):
    c, _, path = catalog(tmp_path)
    page = c.read({'grant_id': 'history', 'path': path.name})
    spec = c.resolve([page['selection']])[0]
    sealed = deepcopy(spec)
    sealed['_catalog_page']['version'].pop('prefix_sha256')
    original_version = deepcopy(sealed['_catalog_page']['version'])
    with path.open('ab') as stream:
        stream.write(line(codex_message('Later', identifier='u2')))
    assert check_snapshot(sealed, original_version) == 'stale'
    assert sealed['_catalog_page']['version'] == original_version


def test_document_consumed_range_ignores_unconsumed_suffix_edit(tmp_path):
    c, profile, path = catalog(tmp_path)
    profile['source_grants'][0].update(format='document', schema='document-v1')
    c = SourceCatalog(c.store, 'fixture', profile)
    path.write_bytes(b'A' * 70000 + b'B' * 1000)
    selected = {'grant_id': 'history', 'path': path.name}
    page = c.read(selected, max_bytes=65537)
    spec = c.resolve([page['selection']])[0]
    with path.open('r+b') as stream:
        stream.seek(70000)
        stream.write(b'C' * 1000)
    assert check_snapshot(spec, page['version']) == 'valid'
    assert read_source(spec)['events'] == page['events']
    next_page = c.read(selected, cursor=page['next_cursor'])
    assert next_page['events'][0]['text'].endswith('C' * 1000)


def test_catalog_range_hash_passes_are_in_read_budget_accounting(tmp_path):
    c, _, path = catalog(tmp_path, values=[HEADER, codex_message('One'), codex_message('Two', identifier='u2')])
    selected = {'grant_id': 'history', 'path': path.name}
    first = c.read(selected, max_events=1)
    assert first['coverage']['verification_bytes'] == 2 * first['version']['consumed']
    second = c.read(selected, cursor=first['next_cursor'])
    assert second['coverage']['verification_bytes'] == 2 * second['version']['consumed'] + first['version']['consumed']
    spec = c.resolve([second['selection']])[0]
    reconstructed = read_source(spec)
    page_bytes = second['version']['consumed'] - second['version']['start']
    assert reconstructed['coverage']['verification_bytes'] == 2 * (second['version']['consumed'] + page_bytes)


def test_inherited_reviewed_memory_checks_policy_without_requiring_raw_availability(tmp_path):
    c, profile, path = inherited(tmp_path)
    spec = c.resolve([absolute(path)])[0]
    path.unlink()
    assert not c.authorized(spec)
    assert c.authorized(spec, require_available=False)
    restricted = deepcopy(profile)
    restricted.pop('read_access')
    assert not SourceCatalog(c.store, 'fixture', restricted).authorized(spec, require_available=False)


def test_complete_native_cutoff_inventory_reads_only_last_byte(tmp_path, monkeypatch):
    import shared_memory_mcp.dream_catalog as module
    c, _, path = catalog(tmp_path, values=[HEADER, codex_message('public ' * 10000)])
    original = module._open_source
    reads = []
    class CountReads:
        def __init__(self, stream):
            self.stream = stream
        def __getattr__(self, name):
            return getattr(self.stream, name)
        def read(self, size):
            reads.append(size)
            return self.stream.read(size)
    @contextmanager
    def measured(source):
        with original(source) as stream:
            yield CountReads(stream)
    monkeypatch.setattr(module, '_open_source', measured)
    frozen = c.freeze({'grant_id': 'history', 'path': path.name})
    assert reads == [1]
    assert frozen['selection']['cutoff'] == path.stat().st_size
    assert frozen['epoch'] == [path.stat().st_dev, path.stat().st_ino, path.stat().st_size,
                               path.stat().st_mtime_ns, path.stat().st_ctime_ns]
