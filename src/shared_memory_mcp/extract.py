"""Startup-triggered, leased, cheap-model extraction of idle native sessions into candidates.

Input is only the Dreaming public projection (`dream_sources.read_source`) plus a bounded
metadata peek (cwd, session/agent identity) at the transcript head; output is only candidates
written through the public `capture` operation with `details.assurance = model-extracted`.
Leases live in the writer-gate SQLite; no daemon, timer or per-turn trigger exists here.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import time
import uuid

from .configuration import load_extraction
from .core import KINDS, SECRET_CLASSES, MemoryError, _fail
from .dream_sources import MAX_BYTES, MAX_LINE, SECRET, read_source

LEASE_SECONDS = 3600
MODEL_TIMEOUT = 900
BACKOFF_BASE = 3600
BACKOFF_MAX = 86400
JOURNAL_LIMIT = 64
HEADER_LINES = 64
MAX_CANDIDATES = 16
# Set in every model command's environment; any hook or `extract --startup` that sees it never spawns.
MARKER = 'SHARED_MEMORY_EXTRACTION'
WORKER_CATEGORIES = {'mistake', 'correction', 'capability-gap'}
# Worker output that only restates the assignment or its completion is not a lesson.
TASK_ONLY = re.compile(r'^\W*(?:the\s+)?(?:worker|subagent|agent)\s+(?:was\s+|is\s+)?(?:assigned|asked|tasked|given|instructed|requested)\b'
                       r'|^\W*(?:successfully\s+)?(?:completed|finished|performed|conducted|delivered)\b', re.I)
DONE = ('extracted', 'no-output', 'skipped')
CAPTURE_KINDS = KINDS - {'handoff'}
# Recognizable provider/auth/quota text; only consulted when no valid result was produced.
PROVIDER_ERROR = re.compile(r'quota|rate.?limit|\b429\b|\b401\b|\b403\b|unauthori[sz]ed|authenticat|billing|'
                            r'credit balance|not logged in|usage limit', re.I)
# Harness-injected wrappers carry instructions/tool echoes, not conversation content.
NOISE = re.compile(r'<(system-reminder|environment_context|user_instructions|local-command-stdout|local-command-stderr|'
                   r'command-name|command-message|command-args)>.*?</\1>', re.S)
SCHEMA = '''CREATE TABLE IF NOT EXISTS extraction_jobs (
    transcript TEXT PRIMARY KEY, size INTEGER NOT NULL, state TEXT NOT NULL, lease_owner TEXT,
    lease_until REAL NOT NULL DEFAULT 0, attempts INTEGER NOT NULL DEFAULT 0, next_attempt REAL NOT NULL DEFAULT 0,
    generation INTEGER NOT NULL DEFAULT 0, windows TEXT NOT NULL DEFAULT '[]', journal TEXT NOT NULL DEFAULT '[]',
    updated_at REAL NOT NULL)'''
COLUMNS = ('transcript', 'size', 'state', 'lease_owner', 'lease_until', 'attempts', 'next_attempt', 'generation',
           'windows', 'journal', 'updated_at')

COMMON = ('Rules for every candidate: a generalization from one or a few sessions must use kind "hypothesis"; '
          'plain configuration or settings changes are excluded; write title, body, conditions and cause in the '
          'language of the transcript.\n')
CONTRACT = {
    'root': ('Return only one JSON object, no prose or code fences:\n'
             '{"candidates":[{"kind":"decision|bug/root-cause|invariant|observation|result|hypothesis|evidence|experiment",'
             '"title":"<=100 chars","body":"self-contained statement","conditions":"when and where it holds",'
             '"source_events":["L12"]}],"no_output":false}\n'
             'Use {"candidates":[],"no_output":true} when nothing qualifies. At most 5 candidates. '
             'source_events must be event labels from the window below.\n'),
    'worker': ('Return only one JSON object, no prose or code fences:\n'
               '{"candidates":[{"kind":"bug/root-cause|observation|hypothesis","category":"mistake|correction|capability-gap",'
               '"title":"<=100 chars","body":"what went wrong","cause":"its likely cause",'
               '"conditions":"when it happens","source_events":["L12"]}],"no_output":false}\n'
               'Use {"candidates":[],"no_output":true} when nothing qualifies, including when the worker simply did '
               'its task. At most 3 candidates. source_events must be event labels from the window below.\n'),
}
PROMPTS = {
    'root': ('You extract durable, reusable knowledge from one window of a past {harness} lead-agent session '
             'transcript. Keep only decisions with their reasons, corrections the user made to the agent, verified '
             'root causes of failures, and durable lessons or invariants, each with the conditions under which it holds. '
             'Skip routine progress, tool output, unexecuted plans and speculation. Prefer no candidate over a weak one.\n'),
    'worker': ('You review one window of a past {harness} delegated worker (subagent) session transcript. Do not '
               'extract project knowledge and do not describe the assignment or report that work was completed. '
               'Report only an actual mistake the worker made, a correction it received, or a capability gap it hit, '
               'each with its likely cause and the condition under which it happens. Prefer no candidate over a weak one.\n'),
}


class Lost(Exception):
    """The lease was taken over (expired); stop without writing more state."""


HARNESS_HOMES = {'.claude', '.codex', '.pi', '.harnessdeck', '.shared-memory'}


def _now_iso():
    return datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')


@contextmanager
def _jobs(store):
    if not (store.root / 'registry.json').is_file():
        _fail('uninitialized', 'Memory root has no explicit project registry')
    path = store.root / '.writer-gate.sqlite3'
    if path.is_symlink():
        _fail('unsafe_path', 'Writer gate may not be a symlink')
    db = sqlite3.connect(path, timeout=30, isolation_level=None)
    try:
        db.execute('PRAGMA busy_timeout=30000')
        db.execute('BEGIN IMMEDIATE')
        db.execute(SCHEMA)
        yield db
        db.execute('COMMIT')
    except BaseException:
        if db.in_transaction:
            db.execute('ROLLBACK')
        raise
    finally:
        db.close()


def _row(db, transcript):
    found = db.execute(f'SELECT {",".join(COLUMNS)} FROM extraction_jobs WHERE transcript=?', (transcript,)).fetchone()
    if found is None:
        return None
    row = dict(zip(COLUMNS, found))
    row['windows'], row['journal'] = json.loads(row['windows']), json.loads(row['journal'])
    return row


def _put(db, row):
    values = {**row, 'windows': json.dumps(row['windows']), 'journal': json.dumps(row['journal'][-JOURNAL_LIMIT:]),
              'updated_at': time.time()}
    db.execute(f'INSERT OR REPLACE INTO extraction_jobs ({",".join(COLUMNS)}) VALUES ({",".join("?" * len(COLUMNS))})',
               tuple(values[k] for k in COLUMNS))


def _status(row, size, now, force=False):
    if row is None:
        return 'eligible'
    if row['state'] == 'leased' and row['lease_until'] > now:
        return 'leased'
    if force:
        return 'eligible'
    if row['size'] == size and row['state'] in DONE:
        return row['state']
    if row['state'] == 'failed' and row['next_attempt'] > now:
        return 'failed'
    return 'eligible'


def _transcripts(config):
    for root in config['history_roots']:
        for directory, dirs, files in os.walk(Path(root['path']).resolve()):
            dirs.sort()
            for name in sorted(files):
                if name.endswith('.jsonl'):
                    yield Path(directory) / name, root


def _root_for(config, transcript):
    path = Path(transcript).resolve()
    for root in config['history_roots']:
        if path.suffix == '.jsonl' and path.is_relative_to(Path(root['path']).resolve()):
            return path, root
    _fail('invalid_input', 'Transcript is not a .jsonl file under a configured extraction history root')


def _idle(st, config, now):
    return now - config['max_age_days'] * 86400 <= st.st_mtime <= now - config['idle_hours'] * 3600


def claim(store, config, owner, *, limit, transcript=None, force=False, now=None):
    """Lease at most `limit` sessions in one short writer-gate transaction; returns claimed jobs and replays."""
    now = time.time() if now is None else now
    if transcript is not None:
        candidates = [_root_for(config, transcript)]  # explicit operator choice bypasses idle/age windows
    else:
        found = []
        for path, root in _transcripts(config):
            try:
                st = path.stat()
            except OSError:
                continue
            if _idle(st, config, now):
                found.append((st.st_mtime, path, root))
        candidates = [(path, root) for _, path, root in sorted(found, key=lambda x: (-x[0], str(x[1])))]
    claimed, replays = [], []
    with _jobs(store) as db:
        for path, root in candidates:
            if len(claimed) >= limit:
                break
            try:
                size = path.stat().st_size
            except OSError:
                continue
            row = _row(db, str(path))
            state = _status(row, size, now, force)
            if state != 'eligible':
                if transcript is not None:
                    replays.append({'transcript': str(path), 'state': state, 'replayed': state in DONE,
                                    'candidates': [i for w in (row or {}).get('windows', []) for i in w.get('ids', [])]})
                continue
            row = row or {'transcript': str(path), 'attempts': 0, 'next_attempt': 0, 'generation': 0,
                          'windows': [], 'journal': []}
            if force and row['windows']:
                row.update(generation=row['generation'] + 1, windows=[])
            row.update(size=size, state='leased', lease_owner=owner, lease_until=now + LEASE_SECONDS)
            _put(db, row)
            claimed.append((path, root, row['generation']))
    return claimed, replays


def _update(store, transcript, owner, change):
    """Apply `change(row)` only while this process still owns the lease."""
    with _jobs(store) as db:
        row = _row(db, transcript)
        if row is None or row['lease_owner'] != owner or row['state'] != 'leased':
            raise Lost(transcript)
        change(row)
        if row['state'] == 'leased':
            row['lease_until'] = time.time() + LEASE_SECONDS
        _put(db, row)
        return row


def _finish(row, state, entry=None, failure=False):
    if entry:
        row['journal'].append(entry)
    row.update(state=state, lease_owner=None, lease_until=0)
    if failure:
        row['attempts'] += 1
        row['next_attempt'] = time.time() + min(BACKOFF_BASE * 2 ** (row['attempts'] - 1), BACKOFF_MAX)
    else:
        row.update(attempts=0, next_attempt=0)


def _header(path, fmt):
    """Bounded metadata peek: identity, cwd and lineage only. Message payloads are never kept."""
    meta = {}
    with open(path, 'rb') as stream:
        for _ in range(HEADER_LINES):
            line = stream.readline(MAX_LINE + 1)
            if not line:
                break
            if not line.endswith(b'\n'):
                while line and not line.endswith(b'\n'):
                    line = stream.readline(MAX_LINE)
                continue
            try:
                raw = json.loads(line)
            except ValueError:
                continue
            if not isinstance(raw, dict):
                continue
            kind = raw.get('type')
            payload = raw.get('payload') if isinstance(raw.get('payload'), dict) else {}
            if fmt == 'codex' and kind == 'session_meta' and 'session_id' not in meta:
                source = payload.get('source')
                meta.update(session_id=payload.get('id'), cwd=payload.get('cwd'))
                if source == 'subagent' or isinstance(source, dict) and 'subagent' in source:
                    spawn = source.get('subagent', {}) if isinstance(source, dict) else {}
                    spawn = spawn.get('thread_spawn', spawn) if isinstance(spawn, dict) else {}
                    meta.update(worker=True, parent_session_id=spawn.get('parent_thread_id'),
                                agent_id=payload.get('agent_nickname') or spawn.get('agent_nickname') or spawn.get('agent_path'))
            elif fmt == 'codex' and kind == 'turn_context':
                meta.setdefault('session_model', payload.get('model'))
                meta.setdefault('session_effort', payload.get('effort'))
            elif fmt == 'pi' and kind == 'session' and 'session_id' not in meta:
                meta.update(session_id=raw.get('id'), cwd=raw.get('cwd'))
            elif fmt == 'pi' and kind == 'custom' and raw.get('customType') == 'pi-web:subagent':
                data = raw.get('data') if isinstance(raw.get('data'), dict) else {}
                meta.update(worker=True, parent_session_id=data.get('parentSessionId'))
            elif fmt == 'pi' and kind == 'model_change':
                meta.setdefault('session_model', raw.get('modelId'))
            elif fmt == 'pi' and kind == 'thinking_level_change':
                meta.setdefault('session_effort', raw.get('thinkingLevel'))
            elif fmt == 'claude' and isinstance(raw.get('sessionId'), str):
                # Navigation records (last-prompt, mode, ...) carry sessionId before any cwd.
                meta.setdefault('session_id', raw['sessionId'])
                if isinstance(raw.get('cwd'), str):
                    meta.setdefault('cwd', raw['cwd'])
                if raw.get('isSidechain') and isinstance(raw.get('agentId'), str):
                    meta.update(worker=True, agent_id=raw['agentId'])
            if fmt == 'claude' and kind == 'assistant' and isinstance(raw.get('message'), dict):
                meta.setdefault('session_model', raw['message'].get('model'))
    if fmt == 'claude' and path.parent.name == 'subagents' and path.name.startswith('agent-'):
        meta.update(worker=True, agent_id=meta.get('agent_id') or path.stem[len('agent-'):])
    if fmt == 'claude' and meta.get('worker'):
        # A Claude subagent transcript repeats the parent's sessionId; the agent is the worker session.
        meta.update(parent_session_id=meta.get('session_id'), session_id=meta['agent_id'])
    return {k: v for k, v in meta.items() if isinstance(v, (str, bool)) and v != '' and len(str(v)) <= 256}


def _events(spec):
    """All public events up to the reader's 8 MiB history bound; reader gaps are reported, not hidden."""
    events, gaps, cursor = [], set(), None
    while True:
        try:
            page = read_source(spec, max_bytes=MAX_BYTES, max_events=1024, cursor=cursor)
        except MemoryError as exc:
            gaps.add(exc.code)
            break
        events += page['events']
        gaps.update(g['reason'] for g in page['coverage']['gaps'] if g['reason'] != 'bounded_partial')
        following = page['cursor']
        if following['offset'] >= following['cutoff']:
            break
        if cursor is not None and following['offset'] <= cursor['offset']:
            gaps.add('history_bound_reached')
            break
        cursor = following
    return events, sorted(gaps)


def _redact(text):
    text = SECRET.sub('[REDACTED]', NOISE.sub('', text))
    for _, pattern in SECRET_CLASSES:
        text = pattern.sub('[REDACTED]', text)
    return text.strip()


def _windows(events, window_bytes):
    """Greedy public-text windows; identical prefixes give identical windows (resume after growth)."""
    windows, current, used = [], [], 0
    for event in events:
        text = _redact(event['text'])
        if not text:
            continue
        label = 'L' + str(event['locator']).split(':')[-1]
        line = f'[{label}] {event["role"]}: {text}\n'
        if len(line.encode()) > window_bytes:
            line = line.encode()[:window_bytes - 16].decode('utf-8', 'ignore') + ' [truncated]\n'
        size = len(line.encode())
        if current and used + size > window_bytes:
            windows.append(current)
            current, used = [], 0
        current.append((label, line, event['key']))
        used += size
    if current:
        windows.append(current)
    return [{'labels': [x[0] for x in w], 'text': ''.join(x[1] for x in w),
             'digest': hashlib.sha256(json.dumps([x[2] for x in w]).encode()).hexdigest()} for w in windows]


def _json_object(text):
    if isinstance(text, dict):
        return text
    if not isinstance(text, str) or '{' not in text:
        return None
    try:
        return json.loads(text[text.index('{'):text.rindex('}') + 1])
    except ValueError:
        return None


def _parse(stdout):
    """Accept a bare contract object, `claude --output-format json` or `codex exec --json` JSONL."""
    try:
        documents = [json.loads(stdout)]
    except ValueError:
        documents = []
        for line in stdout.splitlines():
            try:
                documents.append(json.loads(line))
            except ValueError:
                pass
    texts, usage, error = [], None, False
    for document in documents:
        if not isinstance(document, dict):
            continue
        if 'candidates' in document:
            texts.append(document)
        if document.get('is_error') is True or document.get('type') in ('error', 'turn.failed'):
            error = True
        if isinstance(document.get('result'), str):
            texts.append(document['result'])
        item = document.get('item')
        if isinstance(item, dict) and item.get('type') in ('agent_message', 'assistant_message') and isinstance(item.get('text'), str):
            texts.append(item['text'])
        if isinstance(document.get('usage'), dict):
            usage = {k: v for k, v in document['usage'].items() if type(v) in (int, float)}
        if type(document.get('total_cost_usd')) in (int, float):
            usage = {**(usage or {}), 'total_cost_usd': document['total_cost_usd']}
    parsed = [_json_object(t) for t in texts]
    return next((p for p in reversed(parsed) if p is not None), None), usage, error


def _validate(result, labels):
    if (not isinstance(result, dict) or set(result) != {'candidates', 'no_output'} or
            not isinstance(result['candidates'], list) or type(result['no_output']) is not bool or
            len(result['candidates']) > MAX_CANDIDATES or result['no_output'] and result['candidates']):
        return None
    for item in result['candidates']:
        if (not isinstance(item, dict) or not {'kind', 'title', 'body'} <= set(item) or
                not set(item) <= {'kind', 'title', 'body', 'conditions', 'source_events', 'category', 'cause'} or
                not isinstance(item.get('category', ''), str) or not isinstance(item.get('cause', ''), str) or
                item['kind'] not in CAPTURE_KINDS or
                not isinstance(item['title'], str) or not 0 < len(item['title'].strip()) <= 200 or
                not isinstance(item['body'], str) or not 0 < len(item['body'].strip()) <= 4000 or
                not isinstance(item.get('conditions', ''), str) or len(item.get('conditions', '')) > 2000 or
                not isinstance(item.get('source_events', []), list) or
                any(x not in labels for x in item.get('source_events', []))):
            return None
    return result


def _worker_filter(result):
    """Keep worker candidates only for a mistake/correction/capability gap with a cause and a condition."""
    kept = []
    for item in result['candidates']:
        text = item['title'].strip() + '\n' + item['body'].strip()
        if (item.get('category') in WORKER_CATEGORIES and item.get('cause', '').strip() and
                item.get('conditions', '').strip() and not TASK_ONLY.search(item['title']) and not TASK_ONLY.search(item['body'])):
            kept.append({**item, 'body': item['body'].strip() + '\nLikely cause: ' + item['cause'].strip()})
    return {'candidates': kept, 'no_output': not kept}, len(result['candidates']) - len(kept)


def _model(argv, prompt, labels):
    """One configured model; one retry on invalid JSON; provider failures are final for this run."""
    entry = {'model_command': argv[0], 'attempts': 0, 'wall_seconds': 0.0}
    for _ in range(2):
        entry['attempts'] += 1
        started = time.monotonic()
        try:
            process = subprocess.run(argv, input=prompt, capture_output=True, text=True, timeout=MODEL_TIMEOUT,
                                     env={**os.environ, MARKER: '1'})
        except (OSError, subprocess.TimeoutExpired) as exc:
            entry['wall_seconds'] += round(time.monotonic() - started, 3)
            return None, {**entry, 'outcome': 'provider-error', 'error': type(exc).__name__}
        entry['wall_seconds'] += round(time.monotonic() - started, 3)
        result, usage, error = _parse(process.stdout)
        if usage:
            entry['tokens'] = usage
        valid = _validate(result, set(labels)) if not error else None
        if process.returncode != 0 or error or valid is None and PROVIDER_ERROR.search(process.stdout + process.stderr):
            return None, {**entry, 'outcome': 'provider-error', 'exit_code': process.returncode,
                          'error': (process.stderr or process.stdout)[-300:]}
        if valid is not None:
            return valid, {**entry, 'outcome': 'no-output' if not valid['candidates'] else 'candidates'}
    return None, {**entry, 'outcome': 'invalid-json'}


def _locator(labels, fallback):
    lines = sorted(int(x[1:]) for x in labels) if labels else None
    return f'events L{lines[0]}-L{lines[-1]}' if lines else fallback


def _extract_one(store, config, owner, path, root, generation):
    from .operations import call
    fmt, transcript, model = root['format'], str(path), config['model']
    size = path.stat().st_size
    meta = _header(path, fmt)
    worker = bool(meta.get('worker'))
    caller = {'cwd': meta.get('cwd'), 'harness': fmt, 'session_id': meta.get('session_id'), 'actor': 'extraction',
              'role': 'worker' if worker else 'lead', 'model': model['name']}
    if worker and meta.get('parent_session_id'):
        caller['parent_session_id'] = meta['parent_session_id']
    base = {'at': _now_iso(), 'generation': generation, 'model': model['name'], 'session_class': 'worker' if worker else 'root'}
    try:
        if not caller['cwd'] or not caller['session_id']:
            _fail('missing_session_header', 'Transcript head has no session identity or cwd')
        # Harness homes hold smoke/job scratch dirs that resolve to the enclosing project and are later deleted.
        if HARNESS_HOMES.intersection(Path(caller['cwd']).parts):
            _fail('scratch_cwd', 'Session ran inside a harness home scratch directory')
        store.resolve({k: v for k, v in caller.items() if k in ('cwd', 'harness', 'session_id', 'actor')})
    except MemoryError as exc:
        # Unregistered or vanished cwd: nothing to capture, do not spend a model call; re-checked on growth.
        _update(store, transcript, owner, lambda r: _finish(r, 'skipped', {**base, 'outcome': 'skipped', 'reason': exc.code}))
        return {'transcript': transcript, 'state': 'skipped', 'reason': exc.code}
    spec = {'id': 'extraction', 'path': transcript,
            **{k: root[k] for k in ('format', 'schema', 'native_version', 'native_versions') if k in root}}
    events, gaps = _events(spec)
    windows = _windows(events, config['window_bytes'])
    lineage = {k: meta[k] for k in ('agent_id', 'session_model', 'session_effort') if k in meta}
    ids = []
    for index, window in enumerate(windows):
        stored = next((w for w in _update(store, transcript, owner, lambda r: None)['windows']
                       if w['digest'] == window['digest'] and w.get('generation') == generation), None)
        window_range = _locator(window['labels'][:1] + window['labels'][-1:], 'events')
        if stored and stored.get('state') == 'captured':
            ids += stored['ids']
            continue
        if stored is None:
            prompt = (PROMPTS[base['session_class']].format(harness=fmt) + COMMON + CONTRACT[base['session_class']] +
                      f'\nWindow {index + 1} of {len(windows)} ({window_range}):\n' + window['text'])
            result, entry = _model(model['argv'], prompt, window['labels'])
            entry = {**base, **entry, 'window': index, 'events': window_range, 'gaps': gaps}
            if result is not None and worker:
                result, entry['filtered'] = _worker_filter(result)
                if entry['outcome'] == 'candidates' and not result['candidates']:
                    entry['outcome'] = 'no-output'
            if result is None:
                _update(store, transcript, owner, lambda r: _finish(r, 'failed', entry, failure=True))
                return {'transcript': transcript, 'state': 'failed', 'outcome': entry['outcome'], 'candidates': ids}
            stored = {'digest': window['digest'], 'generation': generation, 'index': index, 'events': window_range,
                      'output': result, 'state': 'modeled', 'ids': []}

            def remember(row, stored=stored, entry=entry):
                row['windows'] = [w for w in row['windows'] if w['digest'] != stored['digest']] + [stored]
                row['journal'].append(entry)
            _update(store, transcript, owner, remember)
        captured = []
        for number, item in enumerate(stored['output']['candidates']):
            key = 'extract:' + hashlib.sha256(json.dumps([transcript, generation, window['digest'], number]).encode()).hexdigest()
            details = {'assurance': 'model-extracted', 'extensions': {'extraction': {
                'transcript': transcript, 'window': index, 'events': window_range, 'harness': fmt,
                'session_class': base['session_class'], 'extraction_model': model['name'],
                'source_events': item.get('source_events', []), **lineage,
                **({'category': item['category']} if item.get('category') else {})}}}
            if item.get('conditions', '').strip():
                details['conditions'] = item['conditions'].strip()
            record = {'kind': item['kind'], 'title': item['title'].strip(), 'body': item['body'].strip(), 'scope': 'project',
                      'sources': [{'uri': path.as_uri(), 'locator': _locator(item.get('source_events'), window_range)}]}
            out = call(store, 'capture', {'caller': caller, 'record': record, 'details': details, 'idempotency_key': key})
            captured.append(out['item']['id'])
        ids += captured

        def done(row, digest=window['digest'], captured=captured):
            for w in row['windows']:
                if w['digest'] == digest:
                    w.update(state='captured', ids=captured)
        _update(store, transcript, owner, done)
    state = 'extracted' if ids else 'no-output'
    entry = {**base, 'outcome': state, 'windows': len(windows), 'events': len(events), 'gaps': gaps, 'candidates': ids}

    def finish(row):
        _finish(row, state, entry)
        row['size'] = size
    _update(store, transcript, owner, finish)
    return {'transcript': transcript, 'state': state, 'windows': len(windows), 'candidates': ids, 'gaps': gaps}


def run(store, *, limit=None, transcript=None, force=False, startup=False):
    if startup and os.environ.get(MARKER):
        # A startup inside an extraction model process must never extract again (recursive chain guard).
        return {'status': 'suppressed_recursive_spawn', 'pid': os.getpid(), 'at': _now_iso()}
    config = load_extraction(store)
    if config['diagnostic']:
        return {'status': 'disabled', 'diagnostic': config['diagnostic']}
    if startup and not config['enabled']:
        return {'status': 'disabled', 'diagnostic': None}
    if config['model'] is None:
        return {'status': 'disabled', 'diagnostic': 'extraction_model_missing: configure extraction.models'}
    if limit is not None and (type(limit) is not int or not 1 <= limit <= 16):
        _fail('invalid_input', '--max must be in [1, 16]')
    owner = uuid.uuid4().hex
    claimed, replays = claim(store, config, owner, limit=limit or config['max_sessions_per_startup'],
                             transcript=transcript, force=force)
    sessions = list(replays)
    for path, root, generation in claimed:
        try:
            sessions.append(_extract_one(store, config, owner, path, root, generation))
        except Lost:
            sessions.append({'transcript': str(path), 'state': 'lease_lost'})
        except Exception as exc:  # release with backoff; an extraction error never stays leased
            entry = {'at': _now_iso(), 'outcome': 'error', 'error': f'{type(exc).__name__}: {exc}'[:300]}
            try:
                _update(store, str(path), owner, lambda r: _finish(r, 'failed', entry, failure=True))
            except Lost:
                pass
            sessions.append({'transcript': str(path), 'state': 'failed', 'error': entry['error']})
    return {'status': 'ok', 'model': config['model']['name'], 'sessions': sessions}


def status(store):
    config = load_extraction(store)
    now = time.time()
    with _jobs(store) as db:
        rows = {r[0]: _row(db, r[0]) for r in db.execute('SELECT transcript FROM extraction_jobs').fetchall()}
    items = {}
    for path, _ in (_transcripts(config) if not config['diagnostic'] else ()):
        try:
            st = path.stat()
        except OSError:
            continue
        row = rows.get(str(path))
        if row is None and not _idle(st, config, now):
            continue
        items[str(path)] = (row, st.st_size)
    for name, row in rows.items():
        items.setdefault(name, (row, row['size']))
    listing = []
    for name, (row, size) in sorted(items.items()):
        state = _status(row, size, now)
        listing.append({'transcript': name, 'state': state, 'size': size,
                        **({k: row[k] for k in ('attempts', 'generation', 'next_attempt', 'lease_until')} if row else {}),
                        'candidates': [i for w in (row or {}).get('windows', []) for i in w.get('ids', [])],
                        'journal': (row or {}).get('journal', [])})
    counts = {}
    for item in listing:
        counts[item['state']] = counts.get(item['state'], 0) + 1
    return {'status': 'ok', 'enabled': config['enabled'], 'diagnostic': config['diagnostic'],
            'model': (config['model'] or {}).get('name'), 'counts': counts, 'sessions': listing}


def _log(log, record):
    with open(log, 'a', encoding='utf-8') as stream:
        stream.write(json.dumps({**record, 'pid': os.getpid(), 'at': _now_iso()}) + '\n')


def spawn(store, command=None, trigger=None):
    """Start `extract --startup` detached; never inherit the hook's pipes or wait for it.

    A hook passes its `trigger`; non-persisted (ephemeral) startups never spawn. A store-wide
    cooldown (`min_spawn_interval_minutes`, user-owned) is enforced in the writer-gate DB.
    """
    config = load_extraction(store)
    if config['diagnostic'] or not config['enabled'] or config['model'] is None:
        return {'spawned': False, 'diagnostic': config['diagnostic']}
    log = store.root / '.state' / 'extraction.log'
    log.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.environ.get(MARKER):
        _log(log, {'status': 'suppressed_recursive_spawn'})
        return {'spawned': False, 'diagnostic': None, 'suppressed': 'recursive_spawn'}
    if trigger is not None and not trigger.get('transcript_path'):
        _log(log, {'status': 'skipped_ephemeral_trigger', 'trigger': trigger})
        return {'spawned': False, 'diagnostic': None, 'suppressed': 'ephemeral_trigger'}
    now, interval = time.time(), config['min_spawn_interval_minutes'] * 60
    with _jobs(store) as db:
        db.execute('CREATE TABLE IF NOT EXISTS extraction_spawns (id INTEGER PRIMARY KEY CHECK (id = 1), last_spawn REAL NOT NULL)')
        last = (db.execute('SELECT last_spawn FROM extraction_spawns WHERE id = 1').fetchone() or [None])[0]
        cooling = interval and last is not None and now - last < interval
        if not cooling:
            db.execute('INSERT OR REPLACE INTO extraction_spawns (id, last_spawn) VALUES (1, ?)', (now,))
    if cooling:
        _log(log, {'status': 'spawn_cooldown', 'trigger': trigger or {}, 'next_after_seconds': round(interval - (now - last))})
        return {'spawned': False, 'diagnostic': None, 'suppressed': 'spawn_cooldown'}
    argv = command or [sys.executable, '-m', 'shared_memory_mcp.cli', '--root', str(store.root), 'extract', '--startup']
    fd = os.open(log, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    try:
        process = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=fd, stderr=fd,
                                   start_new_session=True, close_fds=True)
    finally:
        os.close(fd)
    _log(log, {'status': 'spawned', 'child_pid': process.pid, 'trigger': trigger or {}})  # which startup started which extractor
    return {'spawned': True, 'pid': process.pid, 'log': str(log)}
