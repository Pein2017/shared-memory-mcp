"""CPU-only installed consumer regression; no provider or persistent-session proof."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from shared_memory_mcp.core import MemoryStore

PACKAGE = Path(__file__).resolve().parents[1]
SDK = Path(os.environ.get('PI_SDK_ROOT', str(PACKAGE.parent / 'pi-web/node_modules/@earendil-works/pi-coding-agent'))).resolve()
ADAPTER = Path(os.environ.get('PI_MCP_ADAPTER_PATH', '/data/CoordExp/.pi/npm/node_modules/pi-mcp-adapter/index.ts'))


@pytest.mark.parametrize('transport', ['installed', 'native'])
def test_installed_pi_context_identity_and_lifecycle(tmp_path, transport):
    if not (SDK / 'dist/index.js').is_file() or (transport == 'installed' and not ADAPTER.is_file()):
        pytest.skip('Installed Pi SDK/MCP adapter unavailable; not a mocked replacement')
    project = tmp_path / 'project'
    project.mkdir()
    source = project / 'owner.md'
    source.write_text('Synthetic source: airport finite fixture, not transfer evidence.\n')
    store = MemoryStore(tmp_path / 'store')
    store.init()
    store.register('fixture', [project])
    caller = dict(cwd=str(project), harness='pi', session_id='fixture-seed', actor='pi')
    for role, title, body in [('goal', 'goal', 'FIXTURE_BACKGROUND; not execution authority.'),
                              ('outcome', 'airport', 'FIXTURE_TASK: airport finite control; no transfer established.')]:
        record = dict(kind='observation', title=title, body=body, scope='project', sources=[{'uri': source.as_uri()}])
        store.capture(caller, record, title, {'reason': 'Synthetic source review only', 'evidence': record['sources']},
                      {'conditions': 'CPU fixture only; not scientific proof.',
                       'extensions': {'narrative': {'id': title, 'role': role}}})
    cli = tmp_path / 'shared-memory'
    calls = tmp_path / 'cli-calls.jsonl'
    failure = tmp_path / 'cli-failure'
    cli.write_text(f'#!{sys.executable}\nimport json, sys\nfrom pathlib import Path\n'
                   f'with open({str(calls)!r}, "a") as log: log.write(json.dumps(sys.argv[1:]) + "\\n")\n'
                   f'if Path({str(failure)!r}).exists(): print("null"); sys.exit(1)\n'
                   'from shared_memory_mcp.cli import main\nmain()\n')
    cli.chmod(0o700)
    options = dict(sdkRoot=str(SDK), adapter=str(ADAPTER), transport=transport,
                   project=str(project), agentDir=str(tmp_path / 'agent'), root=str(store.root),
                   cli=str(cli), calls=str(calls), failure=str(failure),
                   extension=os.environ.get('SHARED_MEMORY_TEST_PI_EXTENSION', str(PACKAGE / 'adapters/pi/shared-memory.ts')))
    config = tmp_path / 'options.json'
    config.write_text(json.dumps(options))
    env = {**os.environ, 'PYTHONPATH': str(PACKAGE / 'src'), 'RTK_HOOK_DISABLE': '1'}
    result = subprocess.run(['node', str(PACKAGE / 'tests/native/pi_operation_identity.mjs'), str(config)],
                            env=env, capture_output=True, text=True, timeout=120)
    artifacts = os.environ.get('PI_MEMORY_ARTIFACT_DIR')
    if artifacts:
        directory = Path(artifacts)
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f'{transport}-stdout.log').write_text(result.stdout)
        (directory / f'{transport}-stderr.log').write_text(result.stderr)
    assert result.returncode == 0, result.stdout + '\n' + result.stderr
    assert '"status":"passed"' in result.stdout
