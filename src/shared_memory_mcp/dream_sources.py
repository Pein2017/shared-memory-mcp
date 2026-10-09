"""Bounded public projections. Never import a native session loader or write a source.

This module recognizes explicitly selected wire schemas, not arbitrary native
event shapes. Producer releases are provenance. Role=user is not human attribution. Attestations belong to
operator policy and bind an exact raw event digest, never model-supplied prose.
"""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import re
import stat

from .core import MemoryError, SAFE_ID, _decode, _digest, _fail, _keys, _nonempty

FORMATS = {'document': 'document-v1', 'codex': 'codex-rollout-v1',
           'pi': 'pi-session-v3', 'claude': 'claude-jsonl-v1'}
MAX_BYTES = 8 * 1024 * 1024
MAX_LINE = 64 * 1024
MAX_NATIVE_EVENT = MAX_BYTES
MAX_PI_STRUCTURE_BYTES = 128 * 1024 * 1024
MAX_EVENTS = 1024
MAX_PI_GRAPH_NODES = 16384
PI_STRUCTURE_REVISION = 2
SECRET = re.compile(r'-----BEGIN [A-Z ]*PRIVATE KEY-----|\b(?:sk-[A-Za-z0-9_-]{20,}|AKIA[A-Z0-9]{16})\b')


def validate_source(source):
    _keys(source, {'id', 'path', 'format', 'schema'},
          {'id', 'path', 'format', 'schema', 'native_version', 'attestations',
           'leaf_id', 'derived', 'lineage'}, 'dream source')
    if not isinstance(source['id'], str) or not SAFE_ID.fullmatch(source['id']):
        _fail('invalid_input', 'Source ID must be a bounded identifier')
    if not isinstance(source['format'], str) or source['format'] not in FORMATS or source['schema'] != FORMATS[source['format']]:
        _fail('unsupported_schema', 'Select a supported public projection schema explicitly')
    if not isinstance(source['path'], str) or len(source['path']) > 4096 or '\x00' in source['path']:
        _fail('unsafe_source', 'Source path must be a bounded string')
    p = Path(source['path'])
    if not p.is_absolute() or '..' in p.parts or p.name in {'AGENTS.md', 'SKILL.md', '.env'}:
        _fail('unsafe_source', 'Source must be an explicit absolute non-instruction file')
    if source['format'] == 'claude' or 'native_version' in source:
        _nonempty(source.get('native_version'), 'source.native_version')
    if type(source.get('derived', False)) is not bool:
        _fail('invalid_input', 'derived must be boolean')
    lineage = source.get('lineage', [])
    if not isinstance(lineage, list) or len(lineage) > 32 or any(not isinstance(x, str) or not x or len(x) > 256 for x in lineage):
        _fail('invalid_input', 'lineage must be a bounded string list')
    if 'leaf_id' in source:
        _nonempty(source['leaf_id'], 'source.leaf_id')
    if not isinstance(source.get('attestations', {}), dict):
        _fail('invalid_input', 'attestations must be an operator-owned mapping')
    if len(source.get('attestations', {})) > MAX_EVENTS:
        _fail('source_limit', 'Too many source attestations')
    for digest, attestation in source.get('attestations', {}).items():
        if not re.fullmatch('[0-9a-f]{64}', digest):
            _fail('invalid_input', 'Attestation must bind the exact raw event SHA256')
        _keys(attestation, {'subject', 'basis'}, {'subject', 'basis'}, 'attestation')
        if attestation['subject'] != 'Pein':
            _fail('invalid_input', 'Only Pein collaboration is supported')
        _nonempty(attestation['basis'], 'attestation.basis')
    return source


def _open(path, *, directory=False, identities=None):
    """Walk every component with dirfds: pre-open path checks cannot fence races."""
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts:
        _fail('unsafe_source', 'Source must be an absolute non-traversing path')
    identities = {str(Path(key)): value for key, value in (identities or {}).items()}
    fd = os.open('/', os.O_RDONLY | os.O_DIRECTORY)
    try:
        for index, component in enumerate(path.parts[1:]):
            final = index == len(path.parts[1:]) - 1
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
            if not final or directory:
                flags |= os.O_DIRECTORY
            following = os.open(component, flags, dir_fd=fd)
            os.close(fd)
            fd = following
            # Bind the actual opened directory component, not its pathname
            # before/after the walk: an ABA rename can restore that pathname.
            expected_identity = identities.get(str(Path('/', *path.parts[1:index + 2])))
            if expected_identity is not None:
                st = os.fstat(fd)
                if [st.st_dev, st.st_ino] != expected_identity:
                    _fail('source_changed', 'Opened source grant directory was replaced')
        expected = stat.S_ISDIR if directory else stat.S_ISREG
        if not expected(os.fstat(fd).st_mode):
            _fail('unsafe_source', 'Source has the wrong file kind')
        result = os.fdopen(fd, 'rb') if not directory else fd
        fd = None
        return result
    finally:
        if fd is not None:
            os.close(fd)


@contextmanager
def _open_source(source):
    """Retained prefix reads share the directory-grant replacement fence."""
    def check_root():
        if source.get('_grant_root'):
            fd = _open(source['_grant_root'], directory=True)
            try:
                st = os.fstat(fd)
                if [st.st_dev, st.st_ino] != source['_grant_identity']:
                    _fail('source_changed', 'Source grant directory was replaced')
            finally:
                os.close(fd)
    identities = {source['_grant_root']: source['_grant_identity']} if source.get('_grant_root') else None
    with _open(source['path'], identities=identities) as stream:
        check_root()
        yield stream
        check_root()


def _text(content):
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ''
    return '\n'.join(x.get('text', '') for x in content
                     if isinstance(x, dict) and x.get('type') in {'text', 'input_text', 'output_text'}
                     and isinstance(x.get('text'), str))


def _native_line(stream, end, state):
    """Frame a complete bounded event; a page boundary never discards its prefix."""
    start = stream.tell()
    data = stream.readline(min(MAX_NATIVE_EVENT + 1, end - start))
    if len(data) > MAX_NATIVE_EVENT or state.get('draining'):
        while data and not data.endswith(b'\n') and stream.tell() < end:
            data = stream.readline(min(MAX_LINE, end - stream.tell()))
        state['draining'] = bool(data and not data.endswith(b'\n'))
        return None, 'oversized_event', stream.tell() - start
    if not data.endswith(b'\n'):
        scanned = stream.tell() - start
        stream.seek(start)
        return None, 'partial_line' if end == os.fstat(stream.fileno()).st_size else 'event_exceeds_remaining_budget', scanned
    return data, None, len(data)


def _native_public(source, data, line, state):
    """All readers use the same strict JSON decoder and public filtering."""
    raw_digest = hashlib.sha256(data).hexdigest()
    try:
        raw = _decode(data.decode('utf-8'))
        if not isinstance(raw, dict):
            raise ValueError('Not an event object')
        event, gap = _public(source, raw, line, state, raw_digest=raw_digest)
    except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
        event, gap = None, 'malformed_event'
    if event is not None:
        event.update(raw_digest=raw_digest, locator=f'line:{line}')
    return event, gap


def _source_epoch(st):
    return [st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns]


def _scan_pi_structure(source, stream, cutoff):
    """Rebuild edges and saved resume selection without retaining any payload."""
    if cutoff > MAX_PI_STRUCTURE_BYTES:
        _fail('source_limit', f'Pi structural scan requires {cutoff} bytes; fixed limit is {MAX_PI_STRUCTURE_BYTES} bytes')
    original = stream.tell()
    epoch = _source_epoch(os.fstat(stream.fileno()))
    stream.seek(0)
    state, gaps, line = {}, [], 0
    saved_leaf = None
    while stream.tell() < cutoff:
        start = stream.tell()
        continuing = bool(state.get('draining'))
        data, framing_gap, scanned = _native_line(stream, cutoff, state)
        line += not continuing
        if framing_gap:
            gaps.append({'reason': framing_gap, 'line': line})
            if stream.tell() == start:
                break
            saved_leaf = None
            continue
        try:
            raw = _decode(data.decode('utf-8'))
            if not isinstance(raw, dict):
                raise ValueError('Not an event object')
            _, gap = _public(source, raw, line, state, raw_digest=hashlib.sha256(data).hexdigest())
            if raw.get('type') != 'session':
                saved_leaf = raw.get('id')
        except (ValueError, TypeError, KeyError, AttributeError, RecursionError):
            gap, saved_leaf = 'malformed_event', None
        if gap:
            gaps.append({'reason': gap, 'line': line})
    metadata = {'parents': state.get('pi_structure', {}), 'valid': bool(state.get('valid')),
                'leaf': saved_leaf, 'gaps': gaps, 'cutoff': cutoff, 'projection_revision': PI_STRUCTURE_REVISION,
                'epoch': epoch}
    metadata['sha256'] = _digest(metadata)
    if _source_epoch(os.fstat(stream.fileno())) != epoch:
        _fail('source_changed', 'Pi structure changed during scan')
    stream.seek(original)
    return metadata


def _pi_structure(raw, state, raw_digest):
    """Keep ancestry metadata for private entries, never their payloads."""
    kind, identifier, parent = raw.get('type'), raw.get('id'), raw.get('parentId')
    recognized = kind in {'message', 'model_change', 'thinking_level_change', 'label', 'custom', 'session_info',
                          'custom_message', 'usage', 'context_edit', 'compaction', 'branch_summary'}
    if kind == 'message':
        recognized = isinstance(raw.get('message'), dict) and raw['message'].get('role') in {'user', 'assistant', 'toolResult', 'system'}
    valid = (isinstance(identifier, str) and 0 < len(identifier) <= 256 and 'parentId' in raw and
             (parent is None or isinstance(parent, str) and 0 < len(parent) <= 256))
    parents = state.setdefault('pi_structure', {})
    if not isinstance(identifier, str) or not 0 < len(identifier) <= 256:
        return 'missing_event_identity'
    node = {'parent': parent if valid else None, 'digest': raw_digest, 'recognized': recognized and valid}
    if identifier in parents and parents[identifier] != node:
        parents[identifier]['recognized'] = False
        return 'conflicting_event_identity'
    if identifier not in parents:
        if len(parents) >= MAX_PI_GRAPH_NODES:
            _fail('source_limit', f'Pi structural graph exceeds fixed limit of {MAX_PI_GRAPH_NODES} identities')
        parents[identifier] = node
    if not valid:
        return 'compaction_originals_not_proven' if kind in {'compaction', 'branch_summary'} else 'missing_parent_identity'
    if not recognized:
        return 'compaction_originals_not_proven' if kind in {'compaction', 'branch_summary'} else 'unknown_event_schema'
    return None


def _public(source, raw, line, state, *, raw_digest=None):
    """Return (event or None, gap or None); private/system/tool payloads are excluded."""
    fmt = source['format']
    kind = raw.get('type')
    native = source.get('native_version')
    if fmt == 'codex':
        if kind == 'session_meta':
            payload = raw.get('payload', {})
            # A fork may embed parent metadata after the rollout's own header.
            # It cannot replace the file owner or prove a later input is human.
            if state.get('header_seen'):
                state['delegated'] = True
                return None, 'inherited_session_metadata'
            state['header_seen'] = True
            state['valid'] = False
            release = payload.get('cli_version')
            if not isinstance(release, str) or not release or len(release) > 128:
                return None, 'unknown_native_version'
            if not isinstance(payload.get('id'), str):
                return None, 'missing_session_identity'
            state.update(session=payload['id'], valid=True, native_version=release,
                         parent=payload.get('forked_from_id'),
                         delegated=bool(payload.get('source') == 'subagent' or
                                        isinstance(payload.get('source'), dict)))
            return None, None
        if not state.get('valid'):
            return None, 'missing_or_unknown_header'
        if kind in {'compacted', 'compaction'}:
            return None, 'compaction_originals_not_proven'
        if kind in {'world_state', 'token_usage_record'}:
            payload = raw.get('payload')
            if not isinstance(payload, dict):
                return None, 'unknown_event_schema'
            if kind == 'world_state':
                known = type(payload.get('full')) is bool and isinstance(payload.get('state'), dict)
            else:
                known = (all(isinstance(payload.get(k), dict) for k in ('usage', 'turn_token_usage', 'thread_token_usage')) and
                         all(isinstance(payload.get(k), str) for k in ('thread_id', 'turn_id', 'session_id', 'root_turn_id', 'response_id')))
            return None, None if known else 'unknown_event_schema'
        if kind in {'event_msg', 'turn_context'}:
            # event_msg duplicates public response_item text; it is not extra evidence.
            return None, None
        if kind != 'response_item':
            return None, 'unknown_event_schema'
        payload = raw.get('payload', {})
        if payload.get('type') != 'message':
            return None, None if payload.get('type') in {'reasoning', 'function_call', 'function_call_output',
                                                       'custom_tool_call', 'custom_tool_call_output'} else 'unknown_event_schema'
        role = payload.get('role')
        content = payload.get('content')
        event_id, parent = raw.get('id', f'line:{line}'), None
        delegated = state.get('delegated', False)
    elif fmt == 'pi':
        if kind == 'session':
            if raw.get('version') != 3 or not isinstance(raw.get('id'), str):
                state['valid'] = False
                return None, 'unknown_native_version'
            if state.get('session', raw['id']) != raw['id']:
                state['valid'] = False
                return None, 'mixed_session_identity'
            state.update(session=raw['id'], valid=True, parent=raw.get('parentSession'))
            return None, None
        if not state.get('valid'):
            return None, 'missing_or_unknown_header'
        structural_gap = None if state.get('pi_metadata') else _pi_structure(raw, state, raw_digest or _digest(raw))
        if structural_gap:
            return None, structural_gap
        if kind in {'compaction', 'branch_summary'}:
            return None, 'compaction_originals_not_proven'
        if kind in {'model_change', 'thinking_level_change', 'label', 'custom', 'session_info',
                    'custom_message', 'usage', 'context_edit'}:
            return None, None
        if kind != 'message' or not isinstance(raw.get('message'), dict):
            return None, 'unknown_event_schema'
        payload = raw['message']
        role, content = payload.get('role'), payload.get('content')
        event_id, parent = raw.get('id'), raw.get('parentId')
        delegated = bool(raw.get('delegated') or payload.get('source') in {'rpc', 'agent', 'subagent'}
                         or raw.get('source') in {'rpc', 'agent', 'subagent'})
        if not isinstance(event_id, str):
            return None, 'missing_event_identity'
    else:
        if native is None or raw.get('version') != native:
            return None, 'unknown_native_version'
        if kind in {'summary', 'compact_boundary'} or raw.get('isCompactSummary'):
            return None, 'compaction_originals_not_proven'
        if kind in {'system', 'progress', 'file-history-snapshot', 'queue-operation'}:
            return None, None
        if kind not in {'user', 'assistant'} or not isinstance(raw.get('message'), dict):
            return None, 'unknown_event_schema'
        payload = raw['message']
        role, content = payload.get('role'), payload.get('content')
        event_id, parent = raw.get('uuid'), raw.get('parentUuid')
        session = raw.get('sessionId')
        if not isinstance(session, str) or not isinstance(event_id, str):
            return None, 'missing_event_identity'
        if 'parentUuid' not in raw:
            return None, 'missing_parent_identity'
        if state.get('session', session) != session:
            return None, 'mixed_session_identity'
        state.update(session=session, valid=True)
        delegated = bool(raw.get('isSidechain') or raw.get('isMeta'))
    if payload.get('channel') in {'analysis', 'summary'} or raw.get('channel') in {'analysis', 'summary'}:
        return None, None
    if role not in {'user', 'assistant'}:
        return None, None
    if isinstance(content, list) and any(isinstance(x, dict) and x.get('type') == 'tool_result' for x in content):
        delegated = True
    text = _text(content)
    if not text:
        return None, None
    if SECRET.search(text):
        return None, 'sensitive_content_excluded'
    if role == 'assistant' and (payload.get('stop_reason') in {'aborted', 'error'} or
                               payload.get('stopReason') in {'aborted', 'error'}):
        return None, 'unfinished_output'
    return {'session': state['session'], 'event_id': event_id, 'parent': parent,
            'session_parent': state.get('parent'), 'role': role, 'text': text,
            'timestamp': raw.get('timestamp', payload.get('timestamp')),
            'delegated': delegated, 'branch': 'unspecified',
            **({'native_version': state['native_version']} if fmt == 'codex' else {})}, None


def check_snapshot(source, version):
    """Check a frozen prefix outside the memory writer gate; never return source text."""
    if source.get('_catalog_page'):
        from .dream_catalog import check_page_snapshot
        return check_page_snapshot(source, version)
    if not version:
        return 'unverifiable'
    try:
        with _open_source(source) as stream:
            st = os.fstat(stream.fileno())
            if source['format'] == 'pi' and version.get('structure_epoch') != _source_epoch(st):
                return 'stale'
            if [st.st_dev, st.st_ino] != version['identity']:
                return 'unverifiable'
            if source['format'] == 'document' and st.st_size != version['cutoff']:
                return 'stale'
            remaining = version['consumed']
            if type(remaining) is not int or not 0 <= remaining <= MAX_BYTES or st.st_size < remaining:
                return 'unverifiable'
            digest = hashlib.sha256()
            while remaining:
                part = stream.read(min(65536, remaining))
                if not part:
                    return 'unverifiable'
                digest.update(part)
                remaining -= len(part)
            return 'valid' if digest.hexdigest() == version['prefix_sha256'] else 'stale'
    except (OSError, MemoryError, KeyError, TypeError):
        return 'unverifiable'


def read_source(source, *, max_bytes=262144, max_events=128, cursor=None, refresh_cutoff=False):
    """A finite read with a prefix-integrity cursor. Verification I/O is reported.

    A replaced file or edited consumed prefix invalidates the cursor. Appends do
    not extend the original cutoff. A new Run is required to observe that suffix.
    Native events are parsed up to 8MiB, independently of the delivery window.
    """
    if source.get('_catalog_page'):
        from .dream_catalog import materialized_page
        return materialized_page(source)
    validate_source({k: v for k, v in source.items() if not k.startswith('_')})
    if type(max_bytes) is not int or not 1 <= max_bytes <= MAX_BYTES or type(max_events) is not int or not 1 <= max_events <= MAX_EVENTS:
        _fail('source_limit', 'Invalid source byte/event budget')
    cursor = dict(cursor or {})
    offset = cursor.get('offset', 0)
    if type(offset) is not int or not 0 <= offset <= MAX_BYTES:
        _fail('source_limit', 'Cursor verification exceeds the bounded history window')
    events, gaps, excluded = [], [], 0
    state = deepcopy(cursor.get('state', {}))
    seen = dict(cursor.get('seen', {}))
    line = cursor.get('line', 0)
    digest = hashlib.sha256()
    try:
        with _open_source(source) as stream:
            st = os.fstat(stream.fileno())
            identity = [st.st_dev, st.st_ino]
            cutoff = cursor.get('cutoff', st.st_size)
            if type(cutoff) is not int or cutoff < offset:
                _fail('source_changed', 'Invalid frozen source cutoff')
            if cursor and (identity != cursor.get('identity') or st.st_size < cutoff):
                _fail('source_changed', 'Source replaced/truncated; restart from an explicitly reviewed checkpoint')
            remaining = offset
            while remaining:
                part = stream.read(min(65536, remaining))
                if not part:
                    _fail('source_changed', 'Consumed source prefix is unavailable')
                digest.update(part)
                remaining -= len(part)
            if cursor and digest.hexdigest() != cursor.get('prefix_sha256'):
                _fail('source_changed', 'Consumed source prefix changed; locator is invalid')
            if refresh_cutoff and cursor and (offset == cutoff or cursor.get('pending_tail')):
                cutoff = st.st_size
            structure_bytes = 0
            framing_verification_bytes = 0
            pi_reference = None
            if source['format'] == 'pi':
                metadata = state.get('pi_metadata')
                if metadata and metadata.get('projection_revision') != PI_STRUCTURE_REVISION:
                    _fail('unsupported_structure_revision', 'Frozen Pi structural projection revision is unsupported; select a fresh source page')
                if source.get('_structure_cache'):
                    from .dream_catalog import _resolve_pi_structure
                    metadata, pi_reference, structure_bytes = _resolve_pi_structure(
                        source, stream, cutoff, reference=metadata if metadata and 'cache_key' in metadata else None)
                else:
                    if metadata and metadata['epoch'] != _source_epoch(st):
                        _fail('source_changed', 'Pi structural snapshot changed')
                    if not metadata or metadata['cutoff'] != cutoff:
                        metadata = _scan_pi_structure(source, stream, cutoff)
                        structure_bytes = cutoff
                state['pi_metadata'] = metadata
                gaps.extend(deepcopy(metadata['gaps']))
            scanned = offset
            pending_tail = False
            end = min(cutoff, offset + max_bytes, MAX_BYTES)
            if source['format'] == 'document':
                data = stream.read(end - offset)
                digest.update(data)
                scanned = stream.tell()
                try:
                    text = data.decode('utf-8')
                except UnicodeDecodeError:
                    text = ''
                    gaps.append({'reason': 'invalid_or_partial_utf8', 'offset': offset})
                if SECRET.search(text):
                    text = ''
                    gaps.append({'reason': 'sensitive_content_excluded', 'offset': offset})
                if text:
                    events.append({'session': None, 'event_id': f'bytes:{offset}:{end}', 'parent': None,
                                   'role': 'owner', 'text': text, 'timestamp': None,
                                   'delegated': False, 'branch': 'document', 'raw_digest': hashlib.sha256(data).hexdigest()})
            else:
                while stream.tell() < end and len(events) < max_events:
                    start = stream.tell()
                    continuing = bool(state.get('draining'))
                    data, framing_gap, read_bytes = _native_line(stream, end, state)
                    scanned = max(scanned, start + read_bytes)
                    if framing_gap:
                        gap = {'reason': framing_gap, 'line': line + 1}
                        if framing_gap == 'event_exceeds_remaining_budget':
                            gap.update(next_offset=start, required_bytes_at_least=read_bytes + 1, supported_event_bytes=MAX_NATIVE_EVENT)
                        gaps.append(gap)
                        if stream.tell() == start:
                            pending_tail = framing_gap == 'partial_line'
                            break
                        # A rejected event is drained without storing its payload.
                        stream.seek(start)
                        left = scanned - start
                        framing_verification_bytes += left
                        while left:
                            part = stream.read(min(MAX_LINE, left))
                            digest.update(part)
                            left -= len(part)
                        line += not continuing
                        continue
                    digest.update(data)
                    line += 1
                    raw_digest = hashlib.sha256(data).hexdigest()
                    event, gap = _native_public(source, data, line, state)
                    if gap:
                        gaps.append({'reason': gap, 'line': line})
                    if event:
                        eid = str(event['event_id'])
                        if eid in seen:
                            if seen[eid] != raw_digest:
                                gaps.append({'reason': 'conflicting_event_identity', 'line': line})
                                if source['format'] == 'claude':
                                    state.setdefault('conflicting_ids', {})[eid] = True
                            excluded += 1
                            continue
                        seen[eid] = raw_digest
                        if len(seen) > MAX_EVENTS:
                            _fail('source_limit', 'Event identity window exhausted; split the authorized source')
                        event.update(raw_digest=raw_digest, locator=f'line:{line}', byte_start=start)
                        events.append(event)
                    else:
                        excluded += 1
            position = stream.tell()
            # Verify the exact consumed prefix again against in-place edits while reading.
            scanned = max(scanned, position)
            stream.seek(0)
            verify, left = hashlib.sha256(), position
            while left:
                part = stream.read(min(65536, left))
                if not part:
                    _fail('source_changed', 'Source changed during read')
                verify.update(part)
                left -= len(part)
            if (source['format'] == 'pi' and _source_epoch(os.fstat(stream.fileno())) != state['pi_metadata']['epoch']):
                _fail('source_changed', 'Pi structural snapshot changed during read')
            if verify.digest() != digest.digest() or os.fstat(stream.fileno()).st_ino != st.st_ino:
                _fail('source_changed', 'Source changed during read')
    except OSError as exc:
        _fail('source_unavailable', f'Authorized source unavailable: {type(exc).__name__}; verify its owner/path')
    complete = position == cutoff
    if not complete:
        gaps.append({'reason': 'bounded_partial', 'next_offset': position})
    events, excluded = _branches(source, events, gaps, state, excluded)
    version = {'identity': identity, 'cutoff': cutoff, 'consumed': position,
               'prefix_sha256': digest.hexdigest(), 'schema': source['schema']}
    if source['format'] == 'pi':
        version['structure_epoch'] = state['pi_metadata']['epoch']
        version['structure_sha256'] = state['pi_metadata']['sha256']
    if source['format'] == 'codex':
        version['native_version'] = state.get('native_version')
    for event in events:
        attestation = source.get('attestations', {}).get(event['raw_digest'])
        human = bool(event['role'] == 'user' and not event['delegated'] and attestation)
        event.update(source_id=source['id'], harness=source['format'],
                     key=_digest([source['format'], event['session'] or source['path'], event['event_id'], event['raw_digest']]),
                     source_version=_digest(version), human='attested-Pein' if human else 'unknown',
                     attribution_basis=attestation['basis'] if human else None,
                     evidence='derivative' if source.get('derived') else 'owner' if event['role'] == 'owner' else 'public-message',
                     lineage=source.get('lineage', []))
    cursor_state = deepcopy(state)
    if pi_reference is not None:
        cursor_state['pi_metadata'] = pi_reference
    return {'source_id': source['id'], 'events': events, 'version': version,
            'coverage': {'discovered_bytes': cutoff, 'read_bytes': scanned - offset,
                         'verification_bytes': offset + position + structure_bytes + framing_verification_bytes, 'structure_bytes': structure_bytes, 'events': len(events),
                         'excluded': excluded, 'complete': complete and not gaps, 'gaps': gaps},
            'cursor': {'offset': position, 'cutoff': cutoff, 'identity': identity,
                       'prefix_sha256': digest.hexdigest(), 'line': line, 'state': cursor_state, 'seen': seen,
                       'pending_tail': pending_tail}}


def _branches(source, events, gaps, state, excluded):
    if source['format'] == 'pi':
        metadata = state.get('pi_metadata', {})
        parents = metadata.get('parents', state.get('pi_structure', {}))
        leaf = source.get('leaf_id', metadata.get('leaf'))
        if leaf:
            selected, current = set(), leaf
            while (isinstance(current, str) and current in parents and current not in selected and
                   parents[current]['recognized'] and metadata.get('valid', state.get('valid'))):
                selected.add(current)
                current = parents[current]['parent']
            if current is not None:
                gaps.append({'reason': 'branch_ancestry_not_in_window'})
                selected.clear()
            excluded += sum(x['event_id'] not in selected for x in events)
            events = [{**x, 'branch': leaf, 'branch_selection': 'explicit' if source.get('leaf_id') else 'saved-resume',
                       'ancestry_verified': True} for x in events if x['event_id'] in selected]
        else:
            gaps.append({'reason': 'saved_branch_unverified'})
            excluded += len(events)
            events = []
    elif source['format'] == 'claude':
        leaf = source.get('leaf_id')
        if leaf:
            parents = {x['event_id']: x['parent'] for x in events}
            selected, current = set(), leaf
            conflicts = state.get('conflicting_ids', {})
            while (isinstance(current, str) and current in parents and
                   current not in selected and current not in conflicts):
                selected.add(current)
                current = parents[current]
            if current is not None:
                # An incomplete or ambiguous chain cannot admit even its known
                # suffix: the absent ancestor may change the selected branch.
                gaps.append({'reason': 'branch_ancestry_not_in_window'})
                selected.clear()
            excluded += sum(x['event_id'] not in selected for x in events)
            events = [{**x, 'branch': leaf} for x in events if x['event_id'] in selected]
        else:
            gaps.append({'reason': 'active_branch_unverified'})
    return events, excluded
