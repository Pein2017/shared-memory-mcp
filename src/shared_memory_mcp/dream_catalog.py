"""Operator grants, read-only discovery and opaque, epoch-frozen public pages."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
import os
from pathlib import Path
import secrets
import sqlite3

from .core import MemoryError, _digest, _fail, _keys
from .dream_sources import (MAX_BYTES, MAX_EVENTS, MAX_LINE, SECRET, _open, _open_source, _public,
                            _branches, validate_source)

MAX_HANDLES = 512


def validate_source_grants(store, grants):
    if not isinstance(grants, list) or not 1 <= len(grants) <= 16:
        _fail('invalid_policy', 'One to sixteen source grants are required')
    ids = []
    for grant in grants:
        _keys(grant, {'id', 'path', 'kind', 'format', 'schema'},
              {'id', 'path', 'kind', 'format', 'schema', 'native_version',
               'attestations', 'derived', 'lineage'}, 'source grant')
        if grant['kind'] not in {'file', 'directory'}:
            _fail('invalid_policy', 'Source kind must be file or directory')
        validate_source({k: v for k, v in grant.items() if k != 'kind'})
        path = Path(grant['path'])
        root = store.root.resolve()
        if path.resolve().is_relative_to(root) or (grant['kind'] == 'directory' and root.is_relative_to(path.resolve())):
            _fail('invalid_policy', 'A source grant cannot include the memory store')
        ids.append(grant['id'])
    if len(ids) != len(set(ids)):
        _fail('invalid_policy', 'Duplicate source grant identity')
    return grants


def _epoch(st):
    return [st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns]


def _listing_stamp(fd):
    # Directory stat timestamps can be coarse. Bind entry identity as well, using
    # order-independent bounded memory rather than copying a directory listing.
    total, count = 0, 0
    with os.scandir(fd) as entries:
        for entry in entries:
            st = entry.stat(follow_symlinks=False)
            digest = hashlib.sha256(json.dumps([entry.name, _epoch(st), st.st_mode]).encode()).digest()
            total = (total + int.from_bytes(digest, 'big')) % (1 << 256)
            count += 1
    return [_epoch(os.fstat(fd)), count, str(total)]


def _relative(value, *, empty=True):
    if not isinstance(value, str) or len(value) > 4096 or '\x00' in value:
        _fail('unsafe_source', 'Relative source path must be a bounded string')
    p = Path(value)
    if p.is_absolute() or '..' in p.parts or (not empty and not value):
        _fail('unsafe_source', 'Source selection must stay within its grant')
    if any(x in {'AGENTS.md', 'SKILL.md', '.env'} for x in p.parts):
        _fail('unsafe_source', 'Instruction and credential files are not sources')
    return p.as_posix() if value else ''


def _directory_identity(path):
    fd = _open(path, directory=True)
    try:
        st = os.fstat(fd)
        return [st.st_dev, st.st_ino]
    finally:
        os.close(fd)


def _verify(spec, version):
    try:
        if spec.get('_grant_root') and _directory_identity(spec['_grant_root']) != spec['_grant_identity']:
            return 'unverifiable'
        with _open_source(spec) as stream:
            if _epoch(os.fstat(stream.fileno())) != version['epoch']:
                return 'stale'
            stream.seek(version['start'])
            remaining = version['consumed'] - version['start']
            if not 0 <= remaining <= MAX_BYTES:
                return 'unverifiable'
            digest = hashlib.sha256()
            while remaining:
                chunk = stream.read(min(65536, remaining))
                if not chunk:
                    return 'unverifiable'
                digest.update(chunk)
                remaining -= len(chunk)
            if _epoch(os.fstat(stream.fileno())) != version['epoch']:
                return 'stale'
            if spec.get('_grant_root') and _directory_identity(spec['_grant_root']) != spec['_grant_identity']:
                return 'unverifiable'
            return 'valid' if digest.hexdigest() == version['page_sha256'] else 'stale'
    except (OSError, MemoryError, KeyError, TypeError, ValueError):
        return 'unverifiable'


def check_page_snapshot(source, version):
    return _verify(source, version)


def _decorate(source, events, version):
    for event in events:
        attestation = source.get('attestations', {}).get(event['raw_digest'])
        human = bool(event['role'] == 'user' and not event['delegated'] and attestation)
        event.update(source_id=source['id'], harness=source['format'],
            key=_digest([source['format'], event['session'] or source['path'], event['event_id'], event['raw_digest']]),
            source_version=_digest(version), human='attested-Pein' if human else 'unknown',
            attribution_basis=attestation['basis'] if human else None,
            evidence='derivative' if source.get('derived') else 'owner' if event['role']=='owner' else 'public-message',
            lineage=source.get('lineage', []))
    return events


def materialized_page(source):
    """Reconstruct one selected page from original bytes; never persist its text."""
    descriptor = source['_catalog_page']
    version = descriptor['version']
    if _verify(source, version) != 'valid':
        _fail('source_changed', 'Selected public page is stale')
    state = deepcopy(descriptor['state_before'])
    admitted = set(descriptor['admitted'])
    line = descriptor['line_before']
    events = []
    with _open_source(source) as stream:
        if _epoch(os.fstat(stream.fileno())) != version['epoch']:
            _fail('source_changed', 'Selected public page changed during reconstruction')
        stream.seek(version['start'])
        if source['format'] == 'document':
            data = stream.read(version['consumed'] - version['start'])
            if admitted:
                events.append({'session': None, 'event_id': f"bytes:{version['start']}:{version['consumed']}",
                    'parent': None, 'role': 'owner', 'text': data.decode('utf-8', errors='replace'), 'timestamp': None,
                    'delegated': False, 'branch': 'document', 'raw_digest': hashlib.sha256(data).hexdigest()})
        else:
            while stream.tell() < version['consumed']:
                start = stream.tell()
                data = stream.readline(min(MAX_LINE + 1, version['consumed'] - start))
                if len(data) > MAX_LINE or state.get('draining'):
                    if not state.get('draining'):
                        line += 1
                    state['draining'] = not data.endswith(b'\n')
                    continue
                line += 1
                if not data.endswith(b'\n'):
                    break
                try:
                    event, _ = _public(source, json.loads(data), line, state)
                except (ValueError, TypeError, KeyError, AttributeError):
                    event = None
                if event is not None and start in admitted:
                    event.update(raw_digest=hashlib.sha256(data).hexdigest(), locator=f'line:{line}', byte_start=start)
                    if source.get('leaf_id'):
                        event['branch'] = source['leaf_id']
                    events.append(event)
    # Fence source mutation around the reconstruction, including replacement.
    if _verify(source, version) != 'valid':
        _fail('source_changed', 'Selected public page changed during reconstruction')
    return {'source_id': source['id'], 'events': _decorate(source, events, version), 'version': deepcopy(version),
            'coverage': deepcopy(descriptor['coverage']), 'cursor': None}


class SourceCatalog:
    def __init__(self, store, profile_id, profile):
        self.store, self.profile_id, self.profile = store, profile_id, deepcopy(profile)
        self.grants = validate_source_grants(store, self.profile['source_grants'])
        # Persist locators, parser state and metadata; public text stays in its source.
        self.dbpath = store.root / 'dream' / 'catalog.sqlite3'

    def _db(self):
        self.dbpath.parent.mkdir(parents=True, exist_ok=True)
        db = sqlite3.connect(self.dbpath)
        db.execute('CREATE TABLE IF NOT EXISTS handles (token TEXT PRIMARY KEY, profile TEXT, grant_digest TEXT, kind TEXT, body TEXT)')
        db.execute('CREATE TABLE IF NOT EXISTS identities (pass_id TEXT, event_id TEXT, digest TEXT, PRIMARY KEY(pass_id,event_id))')
        return db

    def _put(self, db, grant, kind, body):
        # Page identity is stable for the same authorized content/window. Read
        # cursors are random capabilities because their parser pass is mutable.
        token = _digest([self.profile_id, _digest(grant), kind, body])[:48] if kind == 'page' else secrets.token_hex(24)
        if db.execute('SELECT 1 FROM handles WHERE token=?', (token,)).fetchone():
            return token
        if db.execute('SELECT count(*) FROM handles WHERE profile=?', (self.profile_id,)).fetchone()[0] >= MAX_HANDLES:
            oldest = db.execute('SELECT token FROM handles WHERE profile=? ORDER BY rowid LIMIT 1', (self.profile_id,)).fetchone()[0]
            db.execute('DELETE FROM handles WHERE token=?', (oldest,))
        db.execute('INSERT INTO handles VALUES (?,?,?,?,?)', (token, self.profile_id, _digest(grant), kind, json.dumps(body)))
        return token

    def _gc_ids(self, db):
        # Index rows carry identities/digests only. Expired passes have no
        # remaining continuation capability and can be removed without sources.
        passes = {json.loads(row[0]).get('pass_id') for row in db.execute('SELECT body FROM handles WHERE kind=\'read\'')}
        passes.discard(None)
        if passes:
            db.execute('DELETE FROM identities WHERE pass_id NOT IN (' + ','.join('?' for _ in passes) + ')', tuple(passes))
        else:
            db.execute('DELETE FROM identities')

    def _get(self, db, grant, kind, token):
        if not isinstance(token, str) or len(token) != 48:
            _fail('invalid_cursor', 'Use the server-produced opaque source selector')
        row = db.execute('SELECT body FROM handles WHERE token=? AND profile=? AND grant_digest=? AND kind=?',
                         (token, self.profile_id, _digest(grant), kind)).fetchone()
        if not row:
            _fail('invalid_cursor', 'Source selector is missing or its grant changed')
        return json.loads(row[0])

    def _grant(self, grant_id):
        for grant in self.grants:
            if grant['id'] == grant_id:
                return grant
        _fail('dream_access_denied', 'Source grant is not authorized')

    def _spec(self, selection):
        _keys(selection, {'grant_id'}, {'grant_id', 'path', 'relative_path', 'leaf_id', 'page'}, 'source selection')
        grant = self._grant(selection['grant_id'])
        if 'path' in selection and 'relative_path' in selection:
            _fail('invalid_input', 'Choose one relative path field')
        relative = _relative(selection.get('path', selection.get('relative_path', '')))
        if grant['kind'] == 'file' and relative:
            _fail('unsafe_source', 'Exact-file grants do not permit another path')
        if grant['kind'] == 'directory' and not relative:
            _fail('unsafe_source', 'Select a file within the directory grant')
        spec = {k: deepcopy(v) for k, v in grant.items() if k != 'kind'}
        if grant['kind'] == 'directory':
            spec['path'] = str(Path(grant['path']) / relative)
            spec['id'] = grant['id'][:111] + '-' + _digest([grant['id'], relative])[:16]
        if 'leaf_id' in selection:
            spec['leaf_id'] = selection['leaf_id']
        validate_source(spec)
        return grant, relative, spec

    def list(self, grant_id, relative_dir='', cursor=None, limit=50):
        if type(limit) is not int or not 1 <= limit <= 100:
            _fail('source_limit', 'Listing limit must be between one and one hundred')
        grant = self._grant(grant_id)
        relative_dir = _relative(relative_dir)
        if grant['kind'] == 'file':
            if relative_dir or cursor:
                _fail('invalid_cursor', 'Exact-file listing has no continuation')
            with _open(grant['path']) as stream:
                st = os.fstat(stream.fileno())
            return {'items': [{'grant_id': grant_id, 'path': '', 'kind': 'file', 'size': st.st_size}], 'next_cursor': None}
        path = Path(grant['path']) / relative_dir
        grant_identity = _directory_identity(grant['path'])
        fd = _open(path, directory=True, identities={grant['path']: grant_identity})
        try:
            initial = _listing_stamp(fd)
            # scandir iterates a dirfd; the output remains bounded even for large directories.
            after = ''
            with self._db() as db:
                db.execute('BEGIN IMMEDIATE')
                if cursor:
                    prior = self._get(db, grant, 'list', cursor)
                    if prior['relative'] != relative_dir or prior['epoch'] != initial:
                        _fail('source_changed', 'Directory listing changed')
                    after = prior['after']
                items = []
                import heapq
                entries = heapq.nsmallest(limit + 1, (e for e in os.scandir(fd) if e.name > after and not e.is_symlink()
                        and e.name not in {'AGENTS.md', 'SKILL.md', '.env'}), key=lambda e: e.name)
                for entry in entries[:limit]:
                    if entry.is_file(follow_symlinks=False) or entry.is_dir(follow_symlinks=False):
                        items.append({'grant_id': grant_id, 'path': str(Path(relative_dir) / entry.name),
                                      'kind': 'directory' if entry.is_dir(follow_symlinks=False) else 'file'})
                if (_listing_stamp(fd) != initial or _directory_identity(path) != initial[0][:2]
                        or _directory_identity(grant['path']) != grant_identity):
                    _fail('source_changed', 'Directory changed during listing')
                next_cursor = self._put(db, grant, 'list', {'relative': relative_dir, 'epoch': initial,
                                  'after': entries[limit-1].name}) if len(entries) > limit else None
            return {'items': items, 'next_cursor': next_cursor}
        except OSError:
            _fail('source_unavailable', 'Authorized directory is unavailable')
        finally:
            os.close(fd)

    def resolve(self, selections=None):
        if selections is None:
            selections = [{'grant_id': g['id']} for g in self.grants if g['kind'] == 'file']
        if not isinstance(selections, list) or len(selections) > 16:
            _fail('source_limit', 'Select at most sixteen sources')
        specs = []
        for selection in selections:
            grant, relative, spec = self._spec(selection)
            spec['_grant_id'] = grant['id']
            spec['_grant_digest'] = _digest(grant)
            spec['_relative_path'] = relative
            if grant['kind'] == 'directory':
                spec['_grant_root'] = grant['path']
                spec['_grant_identity'] = _directory_identity(grant['path'])
            if selection.get('page'):
                with self._db() as db:
                    saved = self._get(db, grant, 'page', selection['page'])
                if saved['relative'] != relative or saved.get('leaf_id') != spec.get('leaf_id'):
                    _fail('invalid_cursor', 'Page selector does not match this source')
                spec['_catalog_page'] = saved['descriptor']
                spec['_grant_identity'] = saved.get('grant_identity')
                if _verify(spec, saved['descriptor']['version']) != 'valid':
                    _fail('source_changed', 'Selected public page changed')
            specs.append(spec)
        return specs

    def authorized(self, spec):
        try:
            selection = {'grant_id': spec['_grant_id'], 'path': spec['_relative_path']}
            if 'leaf_id' in spec:
                selection['leaf_id'] = spec['leaf_id']
            grant, _, expected = self._spec(selection)
            if spec['_grant_digest'] != _digest(grant):
                return False
            if any(spec.get(k) != v for k, v in expected.items()):
                return False
            if grant['kind'] == 'directory':
                return _directory_identity(grant['path']) == spec['_grant_identity']
            return True
        except (MemoryError, OSError, KeyError):
            return False

    def read(self, selection, cursor=None, max_bytes=262144, max_events=128):
        if type(max_bytes) is not int or not MAX_LINE + 1 <= max_bytes <= MAX_BYTES or type(max_events) is not int or not 1 <= max_events <= MAX_EVENTS:
            _fail('source_limit', 'Public pages require 65537 to 8388608 bytes and one to 1024 events')
        if selection.get('page'):
            _fail('invalid_input', 'Read a source selection; page handles are for Run selection')
        grant, relative, spec = self._spec(selection)
        grant_identity = _directory_identity(grant['path']) if grant['kind'] == 'directory' else None
        if grant_identity is not None:
            spec['_grant_root'], spec['_grant_identity'] = grant['path'], grant_identity
        try:
            with self._db() as db, _open_source(spec) as stream:
                # Complete continuation atomically: retries reuse the same page
                # rather than advancing the identity index twice.
                db.execute('BEGIN IMMEDIATE')
                epoch = _epoch(os.fstat(stream.fileno()))
                prior = self._get(db, grant, 'read', cursor) if cursor else None
                if prior and (prior['relative'] != relative or prior.get('leaf_id') != spec.get('leaf_id') or prior['epoch'] != epoch or prior['grant_identity'] != grant_identity):
                    _fail('source_changed', 'Source epoch changed; append continuity is not supported')
                if prior and prior.get('completed'):
                    completed = prior['completed']
                    spec['_catalog_page'] = completed['descriptor']
                    if grant_identity is not None:
                        spec['_grant_root'], spec['_grant_identity'] = grant['path'], grant_identity
                    material = materialized_page(spec)
                    self._put(db, grant, 'page', completed['page_body'])
                    return {**material, 'selection': completed['selection'], 'next_cursor': completed['next_cursor']}
                offset = prior['offset'] if prior else 0
                state = prior['state'] if prior else {}
                line_number = prior['line'] if prior else 0
                pass_id = prior['pass_id'] if prior else secrets.token_hex(24)
                state_before = deepcopy(state)
                line_before = line_number
                stream.seek(offset)
                end = min(epoch[2], offset + max_bytes)
                events, gaps, excluded = [], [], 0
                digest = hashlib.sha256()
                if spec['format'] == 'document':
                    data = stream.read(end-offset); digest.update(data)
                    text = data.decode('utf-8', errors='replace')
                    if SECRET.search(text):
                        gaps.append({'reason': 'sensitive_content_excluded', 'offset': offset})
                    elif text:
                        events.append({'session': None, 'event_id': f'bytes:{offset}:{end}', 'parent': None, 'role': 'owner',
                            'text': text, 'timestamp': None, 'delegated': False, 'branch': 'document', 'raw_digest': hashlib.sha256(data).hexdigest()})
                else:
                    while stream.tell() < end and len(events) < max_events:
                        start = stream.tell()
                        data = stream.readline(min(MAX_LINE+1, end-start))
                        if not data.endswith(b'\n') and len(data) <= MAX_LINE and not state.get('draining'):
                            if stream.tell() == epoch[2]:
                                digest.update(data); gaps.append({'reason': 'partial_line', 'line': line_number+1})
                            else:
                                stream.seek(start)
                            break
                        digest.update(data)
                        if len(data) > MAX_LINE or state.get('draining'):
                            if not state.get('draining'):
                                line_number += 1
                            state['draining'] = not data.endswith(b'\n')
                            gaps.append({'reason': 'oversized_event', 'line': line_number})
                            continue
                        line_number += 1
                        raw_digest = hashlib.sha256(data).hexdigest()
                        try:
                            raw = json.loads(data)
                            event, gap = _public(spec, raw, line_number, state)
                        except (ValueError, TypeError, KeyError, AttributeError):
                            event, gap = None, 'malformed_event'
                        if gap:
                            gaps.append({'reason': gap, 'line': line_number})
                        if not event:
                            excluded += 1; continue
                        eid = str(event['event_id'])
                        duplicate = db.execute('SELECT digest FROM identities WHERE pass_id=? AND event_id=?', (pass_id,eid)).fetchone()
                        if duplicate:
                            if duplicate[0] != raw_digest:
                                gaps.append({'reason': 'conflicting_event_identity', 'line': line_number})
                                if spec['format'] == 'claude':
                                    state.setdefault('conflicting_ids', {})[eid] = True
                            excluded += 1; continue
                        db.execute('INSERT INTO identities VALUES (?,?,?)', (pass_id,eid,raw_digest))
                        event.update(raw_digest=raw_digest, locator=f'line:{line_number}', byte_start=start)
                        events.append(event)
                position = stream.tell()
                if _epoch(os.fstat(stream.fileno())) != epoch or (grant_identity is not None and _directory_identity(grant['path']) != grant_identity):
                    _fail('source_changed', 'Source changed during public page read')
                events, excluded = _branches(spec, events, gaps, state, excluded)
                # Conflicts remain a page-local rejection; never trust cross-page branch ancestry.
                state.pop('conflicting_ids', None)
                version = {'epoch': epoch, 'identity': epoch[:2], 'cutoff': epoch[2], 'start': offset,
                           'consumed': position, 'page_sha256': digest.hexdigest(), 'schema': spec['schema']}
                if position < epoch[2]:
                    gaps.append({'reason': 'bounded_partial', 'next_offset': position})
                coverage = {'discovered_bytes': epoch[2], 'read_bytes': position-offset, 'verification_bytes': 0,
                    'events': len(events), 'excluded': excluded, 'complete': position==epoch[2] and not gaps, 'gaps': gaps}
                descriptor = {'version': version, 'state_before': state_before, 'line_before': line_before,
                    'admitted': [e.get('byte_start', offset) for e in events], 'coverage': coverage}
                material = {'source_id': spec['id'], 'events': _decorate(spec, events, version),
                    'version': version, 'coverage': coverage, 'cursor': None}
                body = {'relative': relative, 'leaf_id': spec.get('leaf_id'), 'grant_identity': grant_identity, 'descriptor': descriptor}
                page = self._put(db, grant, 'page', body)
                next_cursor = self._put(db, grant, 'read', {'relative': relative, 'leaf_id': spec.get('leaf_id'),
                    'grant_identity': grant_identity, 'epoch': epoch, 'offset': position, 'line': line_number,
                    'state': state, 'pass_id': pass_id}) if position < epoch[2] else None
                selected = {'grant_id': grant['id'], 'path': relative, 'page': page}
                if 'leaf_id' in spec:
                    selected['leaf_id'] = spec['leaf_id']
                if cursor:
                    prior['completed'] = {'descriptor': descriptor, 'page_body': body,
                        'selection': selected, 'next_cursor': next_cursor}
                    # If capacity eviction removed this cursor, restore the
                    # completed response binding for immediate retry recovery.
                    db.execute('INSERT OR REPLACE INTO handles VALUES (?,?,?,?,?)',
                        (cursor, self.profile_id, _digest(grant), 'read', json.dumps(prior)))
                self._gc_ids(db)
                return {**material, 'selection': selected, 'next_cursor': next_cursor}

        except OSError:
            _fail('source_unavailable', 'Authorized source is unavailable')
