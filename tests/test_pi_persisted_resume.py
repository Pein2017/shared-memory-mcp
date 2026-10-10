"""Retained disk-backed, fresh-process Pi resume check with a CPU-only fake stream."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from shared_memory_mcp.core import MemoryStore
from test_pi_installed_adapter import ADAPTER, PACKAGE, SDK


def test_disk_backed_exact_session_resume_through_installed_adapter_and_sdk_prompt(tmp_path):
    if not (SDK / 'dist/index.js').is_file() or not ADAPTER.is_file():
        pytest.skip('Installed Pi SDK/MCP adapter unavailable; persistence is not mocked')
    project = tmp_path / 'project'
    project.mkdir()
    owner = project / 'owner.md'
    owner.write_text('Synthetic CPU airport control; no transfer or scientific conclusion.\n')
    store = MemoryStore(tmp_path / 'store')
    store.init()
    store.register('fixture', [project])
    seed = dict(cwd=str(project), harness='pi', session_id='fixture-seed', actor='pi')
    for title, role, text in [('goal', 'goal', 'FIXTURE_BACKGROUND; no execution authority.'),
                               ('airport', 'outcome', 'FIXTURE_TASK: airport fixed CPU control; no transfer.')]:
        record = dict(kind='observation', title=title, body=text, scope='project', sources=[{'uri': owner.as_uri()}])
        store.capture(seed, record, title, {'reason': 'Synthetic source review', 'evidence': record['sources']},
                      {'conditions': 'Disposable CPU fixture only.',
                       'extensions': {'narrative': {'id': title, 'role': role}}})
    calls = tmp_path / 'cli-calls.jsonl'
    cli = tmp_path / 'shared-memory'
    cli.write_text(f'#!{sys.executable}\nimport json, sys\n'
                   f'with open({str(calls)!r}, "a") as log: log.write(json.dumps(sys.argv[1:]) + "\\n")\n'
                   'from shared_memory_mcp.cli import main\nmain()\n')
    cli.chmod(0o700)
    options = dict(project=str(project), root=str(store.root), cli=str(cli), sdkRoot=str(SDK), adapter=str(ADAPTER),
                   agentDir=str(tmp_path / 'agent'), sessionDir=str(tmp_path / 'sessions'), outputDir=str(tmp_path),
                   primaryReceipt=str(tmp_path / 'primary.json'), peerReceipt=str(tmp_path / 'peer.json'),
                   extension=os.environ.get('SHARED_MEMORY_TEST_PI_EXTENSION', str(PACKAGE / 'adapters/pi/shared-memory.ts')))
    config = tmp_path / 'options.json'
    config.write_text(json.dumps(options))
    env = {**os.environ, 'PYTHONPATH': str(PACKAGE / 'src'), 'RTK_HOOK_DISABLE': '1',
            'OPENSPEC_TELEMETRY': '0', 'DO_NOT_TRACK': '1'}
    artifact_dir = Path(os.environ['PI_MEMORY_ARTIFACT_DIR']) if os.environ.get('PI_MEMORY_ARTIFACT_DIR') else None
    if artifact_dir:
        artifact_dir.mkdir(parents=True, exist_ok=True)
    processes = []
    peer_before = None
    resume_start = 0
    for phase in ['warm', 'peer', 'seed', 'resume']:
        if phase == 'resume':
            peer = json.loads(Path(options['peerReceipt']).read_text())
            peer_before = hashlib.sha256(Path(peer['sessionFile']).read_bytes()).hexdigest()
            resume_start = len(calls.read_text().splitlines())
        result = subprocess.run(['node', str(PACKAGE / 'tests/native/pi_persisted_resume.mjs'), str(config), phase],
                                env=env, capture_output=True, text=True, timeout=45)
        if artifact_dir:
            (artifact_dir / f'persisted-{phase}-stdout.log').write_text(result.stdout)
            (artifact_dir / f'persisted-{phase}-stderr.log').write_text(result.stderr)
            request = tmp_path / f'{phase}-requests.json'
            if request.exists():
                (artifact_dir / request.name).write_bytes(request.read_bytes())
        assert result.returncode == 0, f'{phase}:\n{result.stdout}\n{result.stderr}'
        if phase != 'warm':
            receipt = json.loads(result.stdout.strip().splitlines()[-1])
            processes.append(receipt['pid'])
            assert receipt['status'] == 'passed'
    assert len(set(processes)) == 3, 'Seed, neighboring session and resume use distinct OS processes'
    peer = json.loads(Path(options['peerReceipt']).read_text())
    primary = json.loads(Path(options['primaryReceipt']).read_text())
    assert peer['sessionId'] != primary['sessionId']
    assert hashlib.sha256(Path(peer['sessionFile']).read_bytes()).hexdigest() == peer_before
    refreshes = [json.loads(line) for line in calls.read_text().splitlines()[resume_start:]
                 if json.loads(line)[2] == 'context']
    assert len(refreshes) == 2, 'Fresh startup then one recovered-task refresh, not an unbounded retry'
    for args in refreshes:
        assert args[args.index('--session-id') + 1] == primary['sessionId']
        assert args[args.index('--cwd') + 1] == str(project)
    assert '--task-mode' not in refreshes[0]
    assert refreshes[1][refreshes[1].index('--task-mode') + 1] == 'research'
    assert refreshes[1][refreshes[1].index('--query') + 1] == 'airport'
    if artifact_dir:
        for name in ['seed-requests.json', 'peer-requests.json', 'resume-requests.json',
                     'primary.json', 'peer.json', 'resume-receipt.json', 'cli-calls.jsonl']:
            source = tmp_path / name
            if source.exists():
                (artifact_dir / name).write_bytes(source.read_bytes())
        (artifact_dir / 'persisted-primary.jsonl').write_bytes(Path(primary['sessionFile']).read_bytes())
        (artifact_dir / 'persisted-peer.jsonl').write_bytes(Path(peer['sessionFile']).read_bytes())
