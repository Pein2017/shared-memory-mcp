"""The fixed-Run delegation and dated-profile gateway are retired (2.9); no Run or registration results."""
import importlib
import json
import subprocess
import sys

import pytest

from dreaming_helpers import begin, claim, environment, freeze_publish, record_op
from test_dream_transport import ENV, args_for


def store_bytes(store):
    return {p: p.read_bytes() for p in sorted(store.root.rglob('*')) if p.is_file() and 'catalog.sqlite3' not in p.name}


@pytest.mark.parametrize('invocation', ['gateway', 'gateway-publisher', 'fixed-run'])
def test_retired_fixed_run_paths_return_a_diagnostic_without_side_effects(tmp_path, invocation):
    engine, store, caller, *_ = environment(tmp_path)
    rid, gen, key, _ = begin(engine)
    _, published = freeze_publish(engine, rid, gen, [record_op('A', claim(key))])
    assert published['status'] == 'applied'
    receipts = json.dumps(engine._run(rid)['receipts'], sort_keys=True)
    before = store_bytes(store)
    if invocation.startswith('gateway'):
        args = ['-m', 'shared_memory_mcp.cli', '--root', str(store.root), 'dream', 'gateway', '--profile', 'fixture',
                *(['--enable-publisher'] if invocation == 'gateway-publisher' else [])]
    else:
        args = args_for(store, caller, 'serve', '--run-id', rid, '--generation', str(gen), '--enable-publisher')
    result = subprocess.run([sys.executable, *args], env=ENV, capture_output=True, text=True, timeout=15)
    assert result.returncode == 2, result.stderr
    diagnostic = json.loads(result.stdout)['diagnostic']
    assert diagnostic['code'] == 'retired' and 'dream_start' in diagnostic['message']
    assert store_bytes(store) == before  # no Run, lane, registration or receipt change
    assert json.dumps(engine._run(rid)['receipts'], sort_keys=True) == receipts


def test_gateway_module_is_removed():
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module('shared_memory_mcp.dream_gateway')
