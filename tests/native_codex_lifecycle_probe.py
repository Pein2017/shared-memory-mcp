"""CPU-only installed Codex startup/resume/compact request-boundary probe.

Only isolated homes/stores and synthetic local Responses SSE are used. The
disabled-hook control must fail the same freshness/caller assertions.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import selectors
import shlex
import shutil
import signal
import subprocess
import tempfile
import time
import uuid

from native_startup_probe import CLI, HELPER, PACKAGE, RUNTIME, TOOLS, Provider, codex_trust, environment, require


class NativeRPC:
    def __init__(self, binary, cwd, env, log):
        self.process = subprocess.Popen([binary, 'app-server', '--listen', 'stdio://'],
            cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log,
            start_new_session=True)
        self.selector = selectors.DefaultSelector()
        self.selector.register(self.process.stdout, selectors.EVENT_READ)
        self.pending = b''
        self.sequence = 0
        self.events = []
        self.request('initialize', {'clientInfo': {'name': 'native-lifecycle-probe', 'version': '1'},
                                    'capabilities': {'experimentalApi': True}})
        self.send({'method': 'initialized', 'params': {}})

    def send(self, message):
        self.process.stdin.write((json.dumps(message)+'\n').encode())
        self.process.stdin.flush()

    def receive(self, deadline):
        while time.monotonic() < deadline:
            if b'\n' in self.pending:
                line, self.pending = self.pending.split(b'\n', 1)
                if line:
                    message = json.loads(line)
                    if 'method' in message:
                        assert 'id' not in message, 'Unexpected native approval/tool request'
                        self.events.append(message)
                    return message
            if not self.selector.select(max(0, deadline-time.monotonic())):
                break
            chunk = os.read(self.process.stdout.fileno(), 65536)
            if not chunk:
                break
            self.pending += chunk
        raise TimeoutError('Native Codex event deadline')

    def request(self, method, params):
        self.sequence += 1
        self.send({'id': self.sequence, 'method': method, 'params': params})
        deadline = time.monotonic()+30
        while True:
            message = self.receive(deadline)
            if message.get('id') == self.sequence:
                assert 'error' not in message, f'{method}: {message.get("error")}'
                return message['result']

    def completed(self, thread_id):
        deadline = time.monotonic()+40
        while True:
            message = self.receive(deadline)
            if message.get('method') == 'turn/completed' and message['params']['threadId'] == thread_id:
                turn = message['params']['turn']
                assert turn['status'] == 'completed' and not turn.get('error'), turn
                return turn

    def close(self):
        self.process.stdin.close()
        try:
            self.process.wait(timeout=4)
            shutdown = 'stdin_eof'
        except subprocess.TimeoutExpired:
            os.killpg(self.process.pid, signal.SIGTERM)
            shutdown = 'sigterm'
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait()
                shutdown = 'sigkill'
        self.selector.close()
        return {'exit_code': self.process.returncode, 'shutdown': shutdown}


def successful_provider(sentinel, identifier):
    provider = Provider(sentinel, identifier)
    def respond(handler):
        if handler.command != 'POST' or handler.path != '/v1/responses':
            handler.send_error(404)
            return
        number = len(provider.requests)
        provider.requests[-1]['response_status'] = 200
        response_id = f'synthetic-response-{number}'
        events = [
            {'type': 'response.created', 'response': {'id': response_id}},
            {'type': 'response.output_item.done', 'item': {'type': 'message', 'role': 'assistant',
                'id': f'synthetic-message-{number}', 'content': [{'type': 'output_text',
                'text': 'Synthetic CPU lifecycle acknowledgement.'}]}},
            {'type': 'response.completed', 'response': {'id': response_id,
                'usage': {'input_tokens': 1, 'output_tokens': 1, 'total_tokens': 2}}},
        ]
        payload = ''.join('data: '+json.dumps(event)+'\n\n' for event in events).encode()
        handler.send_response(200)
        handler.send_header('Content-Type', 'text/event-stream')
        handler.send_header('Content-Length', str(len(payload)))
        handler.end_headers()
        handler.wfile.write(payload)
    provider.server.RequestHandlerClass.reject = respond
    return provider


def check_boundary(requests, receipt, thread_id, cwd, source):
    assert len(requests) == 1, f'{source}: expected one local request, got {len(requests)}'
    request = requests[0]
    assert all(request[key] for key in ('sentinel_present', 'record_id_present', 'workflow_reminder_present')), \
        f'{source}: fresh scoped context missing at provider boundary'
    assert set(TOOLS) <= {name.rsplit('__', 1)[-1] for name in request['memory_tools']}
    callers = [entry for entry in request['caller_contexts'] if entry.get('cwd') == str(cwd)
               and entry.get('session_id') == thread_id and entry.get('harness') == 'codex'
               and entry.get('actor') == 'codex' and entry.get('project_id') == 'native-fixture']
    assert callers, f'{source}: actual native caller scope missing'
    hooks = [json.loads(line) for line in receipt.read_text().splitlines()] if receipt.exists() else []
    matching = [entry for entry in hooks if entry.get('source') == source
                and entry.get('session_id') == thread_id and entry.get('cwd') == str(cwd)
                and entry.get('hook_event_name') == 'SessionStart' and entry.get('exit_code') == 0
                and entry.get('sentinel_present') and entry.get('record_id_present')
                and entry.get('text_chars', 6001) <= 6000 and entry.get('serialized_bytes', 8001) <= 8000]
    assert len(matching) == 1, f'{source}: expected one matching native hook receipt'
    return {'source': source, 'request': request, 'hook_receipt': matching[0], 'status': 'pass'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--disable-hook', action='store_true')
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    root = Path(tempfile.mkdtemp(prefix='disabled-' if args.disable_hook else 'enabled-', dir=output))
    project, home, store = root/'project', root/'codex', root/'memory'
    project.mkdir(); home.mkdir()
    cwd = project/'consumer'; cwd.mkdir()
    (project/'fixture-owner.md').write_text('Synthetic native lifecycle fixture; no model-quality claim.\n')
    env = environment(home); env['CODEX_HOME'] = str(home)
    require([CLI, '--root', str(store), 'init'], root, env)
    require([CLI, '--root', str(store), 'register', '--project-id', 'native-fixture', '--project-root', str(project)], root, env)
    marker = 'NATIVE_LIFECYCLE_'+uuid.uuid4().hex
    options = {'cli': CLI, 'root': str(store), 'project': str(project), 'sentinel': marker+'_startup'}
    seed = root/'seed.json'; seed.write_text(json.dumps(options))
    seeded = json.loads(require([RUNTIME, str(HELPER), 'seed', str(seed)], root, env)['stdout'])
    receipt = root/'hook-receipts.jsonl'
    hook_options = root/'hook-options.json'
    options.update(id=seeded['id'], harness='codex', receipt=str(receipt))
    hook_options.write_text(json.dumps(options))
    command = shlex.join([RUNTIME, str(HELPER), 'hook', str(hook_options)])
    provider = successful_provider(options['sentinel'], seeded['id'])
    (home/'hooks.json').write_text(json.dumps({'hooks': {'SessionStart': [{'matcher': 'startup|resume|clear|compact',
        'hooks': [{'type': 'command', 'command': command, 'timeout': 20}]}]}}))
    (home/'config.toml').write_text(f'''model = "gpt-5.4"
model_provider = "native_stub"
approval_policy = "never"
sandbox_mode = "read-only"
[features]
hooks = {str(not args.disable_hook).lower()}
plugin_hooks = true
[model_providers.native_stub]
name = "Synthetic Local Lifecycle Probe"
base_url = {json.dumps(provider.url+'/v1')}
wire_api = "responses"
requires_openai_auth = false
supports_websockets = false
request_max_retries = 0
stream_max_retries = 0
[mcp_servers.shared_memory]
command = {json.dumps(CLI)}
args = ["--root", {json.dumps(str(store))}, "serve"]
startup_timeout_sec = 15
tool_timeout_sec = 15
''')
    binary = shutil.which('codex')
    assert binary, 'Installed native Codex unavailable'
    report = {'status': 'limit', 'run_root': str(root), 'consumer_cwd': str(cwd),
        'native_binary': binary, 'native_version': require([binary, '--version'], root, env)['stdout'].strip(),
        'record_id': seeded['id'], 'disabled_hook_control': args.disable_hook, 'boundaries': [],
        'process_exits': [], 'real_provider_requests': 0, 'model_inference_calls': 0,
        'consumer_boundary': 'installed native app-server lifecycle and serialized local provider requests',
        'claim_limit': 'Synthetic local Responses only; no model compliance or paid provider qualification.'}
    rpc = None
    log = open(root/'native-stderr.log', 'w')
    try:
        if not args.disable_hook:
            report['hook_trust'] = codex_trust(binary, home, cwd, env)
        rpc = NativeRPC(binary, cwd, env, log)
        thread = rpc.request('thread/start', {'cwd': str(cwd), 'ephemeral': False})['thread']
        thread_id = thread['id']; report['thread_id'] = thread_id
        def turn(source):
            start = len(provider.requests)
            result = rpc.request('turn/start', {'threadId': thread_id,
                'input': [{'type': 'text', 'text': 'Synthetic lifecycle probe. Do not run tools.'}]})
            completed = rpc.completed(thread_id)
            assert completed['id'] == result['turn']['id'], 'Wrong native terminal turn'
            boundary = check_boundary(provider.requests[start:], receipt, thread_id, cwd, source)
            boundary['terminal_turn'] = {'id': completed['id'], 'status': completed['status']}
            report['boundaries'].append(boundary)
        def refresh(source):
            options['sentinel'] = marker+'_'+source
            source_ref = {'uri': (project/'fixture-owner.md').as_uri()}
            payload = {'caller': {'cwd': str(project), 'harness': 'codex', 'session_id': 'native-fixture-seed', 'actor': 'fixture'},
                'id': seeded['id'], 'review': {'reason': 'Synthetic freshness check', 'evidence': [source_ref]},
                'idempotency_key': 'native-lifecycle-'+source, 'details': {'summary': options['sentinel'],
                    'conditions': 'Synthetic fixture only; no scientific support.', 'extensions': {'narrative': {
                        'id': 'native.background', 'role': 'background', 'compact': options['sentinel']}}}}
            changed = subprocess.run([CLI, '--root', str(store), 'call', '--tool', 'annotate'], cwd=root, env=env,
                input=json.dumps(payload), capture_output=True, text=True, timeout=20)
            assert changed.returncode == 0, changed.stderr[:600]
            assert json.loads(changed.stdout).get('status') == 'ok', changed.stdout[:600]
            hook_options.write_text(json.dumps(options))
            provider.sentinel = options['sentinel']
        turn('startup')
        report['process_exits'].append(rpc.close()); rpc = None
        refresh('resume')
        rpc = NativeRPC(binary, cwd, env, log)
        resumed = rpc.request('thread/resume', {'threadId': thread_id})['thread']
        assert resumed['id'] == thread_id and resumed.get('turns'), 'Exact persisted native resume failed'
        report['resumed_prior_turn_count'] = len(resumed['turns'])
        turn('resume')
        refresh('compact')
        compact_start = len(provider.requests)
        rpc.request('thread/compact/start', {'threadId': thread_id})
        compact_turn = rpc.completed(thread_id)
        assert len(provider.requests)-compact_start == 1, 'Expected one native compaction request'
        report['compaction_terminal_turn'] = {'id': compact_turn['id'], 'status': compact_turn['status']}
        turn('compact')
        report['process_exits'].append(rpc.close()); rpc = None
        rollouts = list(home.glob('sessions/**/*.jsonl'))
        assert len(rollouts) == 1, f'Expected exact one persisted native rollout, got {len(rollouts)}'
        entries = [json.loads(line) for line in rollouts[0].read_text().splitlines()]
        assert entries[0]['payload']['id'] == thread_id
        compacted = [entry for entry in entries if entry.get('type') == 'compacted']
        assert len(compacted) == 1, 'Native compaction not durably persisted'
        report['rollout'] = str(rollouts[0]); report['persisted_compacted_entries'] = len(compacted)
        assert all(exit['exit_code'] == 0 for exit in report['process_exits']), report['process_exits']
        report['status'] = 'pass'
    except Exception as exc:
        report['error'] = {'type': type(exc).__name__, 'message': str(exc)[:1000]}
    finally:
        if rpc:
            report['process_exits'].append(rpc.close())
        log.close(); provider.close()
        report['provider_requests'] = provider.requests
        report['native_hook_receipts'] = [json.loads(line) for line in receipt.read_text().splitlines()] if receipt.exists() else []
        path = root/'report.json'; path.write_text(json.dumps(report, indent=2)+'\n')
        print(json.dumps({'status': report['status'], 'report': str(path), 'error': report.get('error')}))
    return 0 if report['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
