"""Session extraction with a fake model command; no real model, native store or live config is touched."""
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import threading
import time

import pytest

from shared_memory_mcp import extract
from shared_memory_mcp.adapters import handle_subagent, hook_main
from shared_memory_mcp.configuration import load_extraction
from shared_memory_mcp.core import MemoryStore
from shared_memory_mcp.operations import call

PACKAGE = Path(__file__).resolve().parents[1]
ROOT = {'format': 'codex', 'schema': 'codex-rollout-v1', 'native_version': 'fixture-v1'}
FAKE = r'''#!{python}
import hashlib, json, os, re, sys, time
prompt = sys.stdin.read()
with open({log!r}, 'a') as stream:
    stream.write(json.dumps({{'argv': sys.argv[1:], 'worker': 'delegated worker' in prompt, 'prompt': prompt,
                             'marker': os.environ.get('SHARED_MEMORY_EXTRACTION')}}) + '\n')
labels = re.findall(r'^\[(L\d+)\]', prompt, re.M)
if 'QUOTA' in prompt:
    print('Error: quota exceeded for this account', file=sys.stderr); sys.exit(1)
if 'SLOW' in prompt:
    time.sleep(4)
if 'BADJSON' in prompt:
    print('I think the answer is probably fine'); sys.exit(0)
if 'NOOUTPUT' in prompt:
    body = {{'candidates': [], 'no_output': True}}
elif 'BENIGN' in prompt:
    body = {{'candidates': [
        {{'kind': 'observation', 'title': 'Worker was assigned a read-only Dreaming audit', 'body': 'The worker audited.',
         'conditions': 'Fixture'}},
        {{'kind': 'observation', 'category': 'mistake', 'title': 'Completed the governance comparison',
         'body': 'The worker was asked for a read-only governance comparison.', 'cause': 'none', 'conditions': 'Fixture'}}],
        'no_output': False}}
elif 'delegated worker' in prompt:
    tag = hashlib.sha256(prompt.encode()).hexdigest()[:8]
    body = {{'candidates': [{{'kind': 'bug/root-cause', 'category': 'mistake', 'title': 'Fixture lesson ' + tag,
                             'body': 'Edited the wrong file first ' + tag, 'cause': 'Did not read the owner first',
                             'conditions': 'Fixture only', 'source_events': labels[:1]}}], 'no_output': False}}
else:
    tag = hashlib.sha256(prompt.encode()).hexdigest()[:8]
    body = {{'candidates': [{{'kind': 'decision', 'title': 'Fixture lesson ' + tag, 'body': 'EXTRACTED_BODY ' + tag,
                             'conditions': 'Fixture only', 'source_events': labels[:1]}}], 'no_output': False}}
print(json.dumps({{'type': 'result', 'result': json.dumps(body), 'usage': {{'input_tokens': 100, 'output_tokens': 20}},
                  'total_cost_usd': 0.001}}))
'''


def message(text, role='user', identifier='u1'):
    kind = 'input_text' if role == 'user' else 'output_text'
    return {'type': 'response_item', 'id': identifier, 'timestamp': '2026-10-07T00:00:00Z',
            'payload': {'type': 'message', 'role': role, 'content': [{'type': kind, 'text': text}]}}


class Env:
    def __init__(self, tmp_path):
        self.tmp = tmp_path
        self.project = tmp_path / 'project'
        self.project.mkdir()
        self.history = tmp_path / 'history'
        self.history.mkdir()
        self.store = MemoryStore(tmp_path / 'store')
        self.store.init()
        self.store.register('fixture', [str(self.project)])
        self.log = tmp_path / 'model-calls.jsonl'
        self.fake = self.script('fake-model', FAKE.format(python=sys.executable, log=str(self.log)))
        self.configure()

    def script(self, name, text):
        path = self.tmp / name
        path.write_text(text)
        path.chmod(0o700)
        return path

    def configure(self, **changes):
        config = {'version': 1, 'enabled': True, 'models': {'claude': [str(self.fake), '--model', 'fake-haiku']},
                  'history_roots': [{'path': str(self.history), **ROOT}], **changes}
        (self.store.root / 'extraction.json').write_text(json.dumps(config))

    def transcript(self, name, texts, *, session=None, parent=None, age=7200, cwd=None):
        source = {'subagent': {'thread_spawn': {'parent_thread_id': parent, 'agent_nickname': 'Tesla'}}} if parent else 'cli'
        header = {'type': 'session_meta', 'payload': {'id': session or name, 'cli_version': 'fixture-v1',
                                                       'source': source, 'cwd': str(cwd or self.project)}}
        lines = [header] + [message(text, 'user' if i % 2 == 0 else 'assistant', f'e{i}') for i, text in enumerate(texts)]
        path = self.history / f'{name}.jsonl'
        path.write_text(''.join(json.dumps(x) + '\n' for x in lines))
        stamp = time.time() - age
        os.utime(path, (stamp, stamp))
        return path

    def calls(self):
        return [json.loads(x) for x in self.log.read_text().splitlines()] if self.log.exists() else []

    def caller(self, session='reader'):
        return {'cwd': str(self.project), 'harness': 'codex', 'session_id': session, 'actor': 'test'}

    def candidates(self):
        found = call(self.store, 'search', {'caller': self.caller(), 'query': 'Fixture lesson',
                                            'statuses': ['candidate', 'stale']})
        return found['items']

    def row(self, path):
        with extract._jobs(self.store) as db:
            return extract._row(db, str(path))

    def cli(self, *args, **kwargs):
        return subprocess.run([sys.executable, '-m', 'shared_memory_mcp.cli', '--root', str(self.store.root), *args],
                              capture_output=True, text=True, env={**os.environ, 'PYTHONPATH': str(PACKAGE / 'src')},
                              **kwargs)


@pytest.fixture
def env(tmp_path):
    return Env(tmp_path)


def test_configuration_missing_model_or_malformed_disables_and_reports_once(env):
    assert load_extraction(env.store)['model']['name'] == 'fake-haiku'
    for config, code in (({'models': {}}, 'extraction_model_missing'),
                         ({'models': {'claude': ['/nonexistent/claude']}}, 'extraction_model_missing'),
                         ({'window_bytes': 'large'}, 'invalid_extraction'),
                         ({'preferred': 'codex'}, 'invalid_extraction'),
                         ({'history_roots': [{'path': 'relative', **ROOT}]}, 'unsafe_source')):
        env.configure(**config)
        loaded = load_extraction(env.store)
        assert loaded['diagnostic'].startswith(code) and loaded['model'] is None and not loaded['enabled']
        assert extract.spawn(env.store) == {'spawned': False, 'diagnostic': loaded['diagnostic']}
    env.transcript('root', ['Hello'])
    errors, output = io.StringIO(), io.StringIO()
    event = {'hook_event_name': 'SessionStart', 'source': 'startup', 'session_id': 'host', 'cwd': str(env.project)}
    hook_main(env.store, 'codex', stdin=io.StringIO(json.dumps(event)), stdout=output, stderr=errors)
    assert len(errors.getvalue().splitlines()) == 1 and 'unsafe_source' in errors.getvalue()
    assert '<shared-memory-context>' in json.loads(output.getvalue())['hookSpecificOutput']['additionalContext']
    assert not env.calls() and not (env.store.root / '.state' / 'extraction.log').exists()
    # Disabled with no model is silent: recall only.
    env.configure(enabled=False, models={})
    assert load_extraction(env.store)['diagnostic'] is None and extract.spawn(env.store)['spawned'] is False


def test_preferred_model_never_falls_back(env):
    other = env.script('other-model', '#!/bin/sh\nexit 0\n')
    env.configure(models={'codex': ['/nonexistent/codex'], 'claude': [str(other)]}, preferred='codex')
    assert load_extraction(env.store)['diagnostic'].startswith('extraction_model_missing')


def test_root_extraction_captures_lineage_candidates_outside_startup_context(env):
    path = env.transcript('root', ['Please keep FIXTURE_SECRET ghp_' + 'a' * 36 + ' out.',
                                   'Decided to keep the owner file.'], session='root-session')
    result = extract.run(env.store)
    [session] = result['sessions']
    assert session['state'] == 'extracted' and len(session['candidates']) == 1
    [model_call] = env.calls()
    assert not model_call['worker'] and 'ghp_' not in model_call['prompt'] and '[REDACTED]' in model_call['prompt']
    [item] = env.candidates()
    record = call(env.store, 'read', {'caller': env.caller(), 'ids': [item['id']], 'include_inactive': True})['items'][0]
    assert record['status'] == 'candidate' and record['assurance'] == 'model-extracted'
    assert record['provenance'] == {'cwd': str(env.project), 'harness': 'codex', 'session_id': 'root-session',
                                    'actor': 'extraction', 'role': 'lead', 'model': 'fake-haiku'}
    assert record['sources'] == [{'uri': path.as_uri(), 'locator': 'events L2-L2'}]
    extension = record['details']['extensions']['extraction']
    assert extension['transcript'] == str(path) and extension['session_class'] == 'root'
    assert extension['extraction_model'] == 'fake-haiku' and extension['events'] == 'events L2-L3'
    row = env.row(path)
    assert row['state'] == 'extracted' and row['lease_owner'] is None
    entry = next(e for e in row['journal'] if 'tokens' in e)
    assert entry['tokens']['input_tokens'] == 100 and entry['wall_seconds'] >= 0 and entry['model'] == 'fake-haiku'
    context = env.store.context(env.caller('next-startup'), 'Fixture lesson owner')
    assert context['status'] == 'ok'
    assert 'EXTRACTED_BODY' not in context['text'] and item['id'] not in json.dumps(context['items'])


def test_unchanged_transcript_replays_and_force_reextracts(env):
    path = env.transcript('root', ['Decided one thing.'])
    first = extract.run(env.store)['sessions'][0]['candidates']
    assert extract.run(env.store)['sessions'] == []
    replay = extract.run(env.store, transcript=str(path))['sessions'][0]
    assert replay == {'transcript': str(path), 'state': 'extracted', 'replayed': True, 'candidates': first}
    assert len(env.calls()) == 1
    forced = extract.run(env.store, transcript=str(path), force=True)['sessions'][0]
    assert len(env.calls()) == 2 and forced['candidates'] != first and env.row(path)['generation'] == 1
    assert len(env.candidates()) == 2


def test_concurrent_claims_extract_a_session_once(env):
    path = env.transcript('root', ['SLOW decision about the owner.'])
    results = [None, None]

    def worker(index):
        results[index] = env.cli('extract', timeout=60)
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert all(r.returncode == 0 for r in results), [r.stderr for r in results]
    sessions = [s for r in results for s in json.loads(r.stdout)['sessions']]
    assert [s['transcript'] for s in sessions] == [str(path)]
    assert len(env.calls()) == 1 and len(env.candidates()) == 1


def test_active_session_and_old_session_are_not_claimed(env):
    env.transcript('active', ['Still typing.'], age=60)
    env.transcript('ancient', ['Long ago.'], age=20 * 86400)
    assert extract.run(env.store)['sessions'] == [] and not env.calls()
    assert extract.status(env.store)['sessions'] == []


def test_invalid_json_retries_once_then_fails_without_candidates(env):
    path = env.transcript('root', ['BADJSON please.'])
    [session] = extract.run(env.store)['sessions']
    assert session['state'] == 'failed' and session['outcome'] == 'invalid-json'
    assert len(env.calls()) == 2 and env.candidates() == []
    row = env.row(path)
    assert row['state'] == 'failed' and row['lease_owner'] is None and row['next_attempt'] > time.time() + 3000
    assert extract.run(env.store)['sessions'] == [] and len(env.calls()) == 2


def test_quota_error_releases_lease_without_fallback(env):
    other_log = env.tmp / 'other-calls'
    other = env.script('other-model', f'#!/bin/sh\necho called >> {other_log}\nexit 0\n')
    env.configure(models={'claude': [str(env.fake), '--model', 'fake-haiku'], 'codex': [str(other)]})
    path = env.transcript('root', ['QUOTA heavy request.'])
    [session] = extract.run(env.store)['sessions']
    assert session['state'] == 'failed' and session['outcome'] == 'provider-error'
    assert len(env.calls()) == 1 and not other_log.exists() and env.candidates() == []
    row = env.row(path)
    assert row['lease_owner'] is None and row['attempts'] == 1 and 'quota' in row['journal'][-1]['error']


def test_worker_session_is_classified_with_parent_lineage(env):
    env.transcript('worker', ['Fix the parser.', 'I edited the wrong file first.'], session='child', parent='lead-1')
    [session] = extract.run(env.store)['sessions']
    assert env.calls()[0]['worker'] is True
    record = call(env.store, 'read', {'caller': env.caller(), 'ids': session['candidates'], 'include_inactive': True})['items'][0]
    assert record['provenance']['role'] == 'worker' and record['provenance']['parent_session_id'] == 'lead-1'
    assert record['provenance']['session_id'] == 'child'
    assert record['details']['extensions']['extraction']['agent_id'] == 'Tesla'
    assert record['details']['extensions']['extraction']['category'] == 'mistake'
    assert record['body'].endswith('Likely cause: Did not read the owner first')


def test_benign_worker_task_description_is_filtered_to_no_output(env):
    path = env.transcript('benign', ['BENIGN: audit the Dreaming store read-only.', 'Done, no issues.'],
                          session='child', parent='lead-1')
    [session] = extract.run(env.store)['sessions']
    assert env.calls()[0]['worker'] and 'capability gap' in env.calls()[0]['prompt']
    assert session['state'] == 'no-output' and session['candidates'] == [] and env.candidates() == []
    entry = next(e for e in env.row(path)['journal'] if 'filtered' in e)
    assert entry['filtered'] == 2 and entry['outcome'] == 'no-output'


def test_prompts_require_hypothesis_language_and_exclude_configuration(env):
    env.transcript('root', ['Decided one thing.'])
    extract.run(env.store)
    prompt = env.calls()[0]['prompt']
    assert '"hypothesis"' in prompt and 'configuration' in prompt and 'language of the transcript' in prompt


def test_model_command_carries_marker_and_marker_suppresses_spawns(env, monkeypatch):
    env.transcript('root', ['Decided one thing.'])
    extract.run(env.store)
    assert env.calls()[0]['marker'] == '1'
    monkeypatch.setenv('SHARED_MEMORY_EXTRACTION', '1')
    assert extract.spawn(env.store)['suppressed'] == 'recursive_spawn'
    assert extract.run(env.store, startup=True)['status'] == 'suppressed_recursive_spawn'
    log = (env.store.root / '.state' / 'extraction.log').read_text()
    assert 'suppressed_recursive_spawn' in log
    env.transcript('second', ['Another decision.'])
    # The hook still returns recall inside an extraction model process, but starts nothing.
    event = {'hook_event_name': 'SessionStart', 'source': 'startup', 'session_id': 'host', 'cwd': str(env.project)}
    out = env.cli('hook', '--harness', 'codex', input=json.dumps(event), timeout=30)
    assert '<shared-memory-context>' in json.loads(out.stdout)['hookSpecificOutput']['additionalContext']
    startup = env.cli('extract', '--startup', timeout=30)
    assert json.loads(startup.stdout)['status'] == 'suppressed_recursive_spawn'
    time.sleep(1)
    assert len(env.calls()) == 1 and env.row(env.history / 'second.jsonl') is None


def test_hook_spawns_only_for_a_resolved_startup(env, tmp_path):
    plain = tmp_path / 'extraction-cwd'
    plain.mkdir()
    repository = tmp_path / 'unregistered-repo'
    repository.mkdir()
    subprocess.run(['git', 'init', '-q', str(repository)], check=True)
    spawned = []
    for cwd, source, expected in ((plain, 'startup', 0), (repository, 'startup', 0), (env.project, 'resume', 0),
                                  (env.project, 'startup', 1)):
        event = {'hook_event_name': 'SessionStart', 'source': source, 'session_id': 'host', 'cwd': str(cwd)}
        output = io.StringIO()
        hook_main(env.store, 'codex', stdin=io.StringIO(json.dumps(event)), stdout=output, stderr=io.StringIO(),
                  spawn=lambda store, trigger: spawned.append(trigger) or {'spawned': True})
        if cwd == repository:  # the onboarding diagnostic is hook output, yet not a resolved project
            assert 'onboarding diagnostic' in output.getvalue()
        assert len(spawned) == expected, (cwd, source)
    assert spawned[0] == {'cwd': str(env.project), 'session_id': 'host', 'source': 'startup', 'transcript_path': None,
                          'harness': 'codex'}


def test_sequential_startups_claim_different_sessions_and_never_loop(env):
    paths = [env.transcript(f's{i}', [f'Decision {i}.'], age=7200 + i) for i in range(3)]
    first = [s['transcript'] for s in extract.run(env.store, startup=True)['sessions']]
    second = [s['transcript'] for s in extract.run(env.store, startup=True)['sessions']]
    assert len(first) == 2 and len(second) == 1 and not set(first) & set(second)
    assert sorted(first + second) == sorted(map(str, paths)) and len(env.calls()) == 3
    assert extract.run(env.store, startup=True)['sessions'] == [] and len(env.calls()) == 3


def test_header_detection_for_claude_and_pi_workers(tmp_path):
    subagents = tmp_path / 'session-1' / 'subagents'
    subagents.mkdir(parents=True)
    claude = subagents / 'agent-abc.jsonl'
    claude.write_text(json.dumps({'type': 'user', 'isSidechain': True, 'agentId': 'abc', 'sessionId': 'session-1',
                                  'cwd': '/work', 'message': {'role': 'user', 'content': 'PRIVATE'}}) + '\n')
    assert extract._header(claude, 'claude') == {'session_id': 'abc', 'cwd': '/work', 'worker': True,
                                                 'agent_id': 'abc', 'parent_session_id': 'session-1'}
    root = tmp_path / 'root.jsonl'
    root.write_text(json.dumps({'type': 'last-prompt', 'sessionId': 'root-1'}) + '\n' +
                    json.dumps({'type': 'attachment', 'sessionId': 'root-1', 'cwd': '/work', 'isSidechain': False}) + '\n')
    assert extract._header(root, 'claude') == {'session_id': 'root-1', 'cwd': '/work'}
    pi = tmp_path / 'pi.jsonl'
    pi.write_text(json.dumps({'type': 'session', 'version': 3, 'id': 'child', 'cwd': '/work', 'parentSession': '/p.jsonl'}) + '\n'
                  + json.dumps({'type': 'custom', 'customType': 'pi-web:subagent',
                                'data': {'version': 1, 'parentSessionId': 'lead', 'parentSessionPath': '/p.jsonl'}}) + '\n')
    assert extract._header(pi, 'pi') == {'session_id': 'child', 'cwd': '/work', 'worker': True, 'parent_session_id': 'lead'}
    fork = tmp_path / 'fork.jsonl'
    fork.write_text(json.dumps({'type': 'session', 'version': 3, 'id': 'fork', 'cwd': '/work', 'parentSession': '/p.jsonl'}) + '\n')
    assert 'worker' not in extract._header(fork, 'pi')


def test_windows_resume_after_interruption_without_duplicates(env):
    env.configure(window_bytes=4096)
    texts = ['First decision ' + 'x' * 3000, 'Second window BADJSON ' + 'y' * 3000]
    path = env.transcript('large', texts)
    [session] = extract.run(env.store)['sessions']
    assert session['state'] == 'failed' and len(session['candidates']) == 1 and len(env.calls()) == 3
    with sqlite3.connect(env.store.root / '.writer-gate.sqlite3') as db:
        db.execute('UPDATE extraction_jobs SET next_attempt=0')
    env.fake.write_text(env.fake.read_text().replace("'BADJSON' in prompt", "False"))
    [session] = extract.run(env.store)['sessions']
    assert session['state'] == 'extracted' and len(session['candidates']) == 2 and len(env.calls()) == 4
    assert len(env.candidates()) == 2 and env.row(path)['windows'][0]['events'] == 'events L2-L2'


def test_status_lists_each_state(env):
    paths = {name: env.transcript(name, [text]) for name, text in (
        ('extracted', 'A decision.'), ('failed', 'QUOTA please.'), ('nooutput', 'NOOUTPUT here.'))}
    assert {s['state'] for s in extract.run(env.store, limit=3)['sessions']} == {'extracted', 'failed', 'no-output'}
    paths['eligible'] = env.transcript('eligible', ['Later.'])
    paths['leased'] = env.transcript('leased', ['Busy.'])
    config = load_extraction(env.store)
    extract.claim(env.store, config, 'other-owner', limit=1, transcript=str(paths['leased']))
    listing = {Path(s['transcript']).stem: s for s in extract.status(env.store)['sessions']}
    assert {k: v['state'] for k, v in listing.items()} == {
        'extracted': 'extracted', 'failed': 'failed', 'nooutput': 'no-output', 'eligible': 'eligible', 'leased': 'leased'}
    assert listing['failed']['journal'][-1]['outcome'] == 'provider-error'
    assert listing['extracted']['candidates'] and listing['eligible']['journal'] == []
    out = env.cli('extract', '--status')
    assert out.returncode == 0 and len(json.loads(out.stdout)['sessions']) == 5


def test_unregistered_cwd_is_skipped_without_a_model_call(env, tmp_path):
    elsewhere = tmp_path / 'elsewhere'
    elsewhere.mkdir()
    path = env.transcript('foreign', ['Decision.'], cwd=elsewhere)
    [session] = extract.run(env.store)['sessions']
    assert session == {'transcript': str(path), 'state': 'skipped', 'reason': 'unmapped_scope'} and not env.calls()


def test_startup_hook_returns_fast_while_extractor_is_slow(env):
    path = env.transcript('root', ['SLOW decision.'])
    event = {'hook_event_name': 'SessionStart', 'source': 'resume', 'session_id': 'host', 'cwd': str(env.project),
             'transcript_path': str(env.tmp / 'host-session.jsonl')}
    started = time.monotonic()
    resumed = env.cli('hook', '--harness', 'claude', input=json.dumps(event), timeout=30)
    assert resumed.returncode == 0 and not (env.store.root / '.state' / 'extraction.log').exists()
    started = time.monotonic()
    out = env.cli('hook', '--harness', 'claude', input=json.dumps({**event, 'source': 'startup'}), timeout=30)
    elapsed = time.monotonic() - started
    assert out.returncode == 0 and elapsed < 2, (elapsed, out.stderr)
    assert 'Fixture lesson' not in out.stdout
    assert json.loads(out.stdout)['hookSpecificOutput']['hookEventName'] == 'SessionStart'
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline and (env.row(path) or {}).get('state') != 'extracted':
        time.sleep(0.2)
    assert env.row(path)['state'] == 'extracted' and len(env.calls()) == 1
    lines = [json.loads(x) for x in (env.store.root / '.state' / 'extraction.log').read_text().splitlines()]
    assert lines[0]['status'] == 'spawned' and lines[0]['trigger']['session_id'] == 'host' and lines[-1]['status'] == 'ok'


def test_claude_subagent_start_emits_only_bounded_worker_identity(env):
    event = {'hook_event_name': 'SubagentStart', 'session_id': 'lead-session', 'agent_id': 'agent-7',
             'agent_type': 'general-purpose', 'cwd': str(env.project), 'transcript_path': '/do/not/read.jsonl'}
    output = handle_subagent(env.store, event)
    text = output['hookSpecificOutput']['additionalContext']
    assert output['hookSpecificOutput']['hookEventName'] == 'SubagentStart'
    assert len(json.dumps(output).encode()) < 1024 and '<shared-memory-context>' not in text
    identity = json.loads(text.splitlines()[0].split(': ', 1)[1])
    assert identity == {'harness': 'claude', 'session_id': 'agent-7', 'parent_session_id': 'lead-session', 'role': 'worker',
                        'actor': 'general-purpose', 'cwd': str(env.project), 'project_id': 'fixture'}
    assert len(text.splitlines()) == 2 and 'context' in text.splitlines()[1]
    # The emitted identity is directly usable for a worker write with lineage.
    caller = {k: identity[k] for k in ('cwd', 'harness', 'session_id', 'actor', 'role', 'parent_session_id')}
    written = call(env.store, 'capture', {'caller': caller, 'record': {
        'kind': 'observation', 'title': 'Worker note', 'body': 'Found by the worker.', 'scope': 'project',
        'sources': [{'uri': env.project.as_uri()}]}})
    record = call(env.store, 'read', {'caller': caller, 'ids': [written['item']['id']], 'include_inactive': True})['items'][0]
    assert record['provenance']['role'] == 'worker' and record['provenance']['parent_session_id'] == 'lead-session'
    # A held writer gate (e.g. a Dreaming publish) cannot delay the worker identity.
    held, release = threading.Event(), threading.Event()

    def hold():
        with env.store._gate():
            held.set()
            release.wait(10)
    holder = threading.Thread(target=hold)
    holder.start()
    held.wait(5)
    started = time.monotonic()
    try:
        assert handle_subagent(env.store, event) == output and time.monotonic() - started < 1
    finally:
        release.set()
        holder.join()
    out = env.cli('hook', '--harness', 'claude', input=json.dumps({**event, 'cwd': str(env.tmp)}), timeout=30)
    assert json.loads(out.stdout) == {} and 'diagnostic' in out.stderr
    out = env.cli('hook', '--harness', 'codex', input=json.dumps(event), timeout=30)
    assert json.loads(out.stdout) == {}


def log_lines(env):
    path = env.store.root / '.state' / 'extraction.log'
    return [json.loads(x) for x in path.read_text().splitlines()] if path.exists() else []


@pytest.mark.parametrize('transcript', [None, 'missing'])
def test_ephemeral_startup_never_spawns(env, transcript):
    event = {'hook_event_name': 'SessionStart', 'source': 'startup', 'session_id': 'smoke', 'cwd': str(env.project)}
    if transcript is None:
        event['transcript_path'] = None
    output = io.StringIO()
    hook_main(env.store, 'claude', stdin=io.StringIO(json.dumps(event)), stdout=output, stderr=io.StringIO())
    assert '<shared-memory-context>' in json.loads(output.getvalue())['hookSpecificOutput']['additionalContext']
    assert [x['status'] for x in log_lines(env)] == ['skipped_ephemeral_trigger']


def startup_spawn(env):
    return extract.spawn(env.store, command=['true'], trigger={'session_id': 'host', 'transcript_path': '/persisted.jsonl'})


def test_spawn_cooldown_is_store_wide(env):
    assert startup_spawn(env)['spawned'] is True
    time.sleep(1)
    assert startup_spawn(env) == {'spawned': False, 'diagnostic': None, 'suppressed': 'spawn_cooldown'}
    assert [x['status'] for x in log_lines(env)] == ['spawned', 'spawn_cooldown']
    assert 0 < log_lines(env)[1]['next_after_seconds'] <= 1800


def test_zero_cooldown_spawns_every_startup(env):
    env.configure(min_spawn_interval_minutes=0)
    assert startup_spawn(env)['spawned'] and startup_spawn(env)['spawned']
    assert [x['status'] for x in log_lines(env)] == ['spawned', 'spawned']
    env.configure(min_spawn_interval_minutes=-1)
    assert load_extraction(env.store)['diagnostic'].startswith('invalid_extraction')
