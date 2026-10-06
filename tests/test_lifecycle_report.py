"""Current curation projection must not be inferred from historical creation."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

from shared_memory_mcp.core import MemoryError

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from retrieval_fixture import seed, seed_record

spec = importlib.util.spec_from_file_location('lifecycle_report', SCRIPTS / 'report-memory-lifecycle.py')
lifecycle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lifecycle)


def protected(store):
    return {str(p.relative_to(store.root)): p.read_bytes() for p in store.root.rglob('*')
            if p.is_file() and (p.suffix in ('.md', '.json'))}


def test_retired_creation_is_not_current_active_nearest_wrong_counterexample(tmp_path):
    store, ctx, records = seed(tmp_path)
    before = protected(store)
    handoff = records['retired-handoff']
    # Equivalent RED: the previous audit's nearest wrong raw-status projection
    # demonstrably calls this retired historical handoff active.
    raw = store._effective(store._load('example'))
    wrong = sum(r['kind'] == 'handoff' and r['effective_status'] == 'active' for r in raw)
    assert wrong == 1
    actual = lifecycle.report(store, '2026-10-04T00:00:00Z', '2026-10-05T00:00:00Z', 'example')
    assert actual['created_in_window']['handoffs'] == 1
    current = actual['current_projection_of_created_in_window']
    assert current['retired_handoffs'] == 1 and current['by_effective_status']['retired'] == 1
    assert current['by_lifecycle_status']['active'] == current['total']
    full = store.read(ctx, [handoff['id']], True)['items'][0]
    assert full['effective_status'] == 'retired' and full['lifecycle_status'] == 'active'
    assert protected(store) == before


def test_candidate_superseded_withdrawn_and_filters(tmp_path):
    store, ctx, records = seed(tmp_path)
    record = {'kind': 'observation', 'title': 'Status fixture', 'scope': 'project',
              'body': 'Synthesized lifecycle data.', 'sources': records['navigation']['sources']}
    candidate = seed_record(store, ctx, 'candidate', record, status='candidate')
    successor = seed_record(store, ctx, 'successor', record, status='candidate')
    review = {'reason': 'Isolated correction.', 'evidence': record['sources']}
    store.supersede(ctx, successor['id'], [records['navigation']['id']], review, 'supersede-fixture')
    store.delete(ctx, records['task-context']['id'], review, 'withdraw-fixture')
    current = lifecycle.report(store, project='example', harness='codex')['current_projection']
    assert current['by_effective_status']['candidate'] == 1
    assert current['by_effective_status']['superseded'] == 1
    assert current['by_effective_status']['withdrawn'] == 1
    assert current['by_effective_status']['withdrawal'] == 1
    assert current['by_harness'] == {'codex': current['total']}
    assert lifecycle.report(store, project='example', harness='pi')['current_projection']['total'] == 0
    since = lifecycle.report(store, '2026-10-04T12:00:00Z', '2026-10-04T12:00:01Z', 'example')
    assert since['created_in_window']['total'] == current['total'] - 1  # marker created now
    assert lifecycle.report(store, until='2026-10-04T12:00:00Z')['created_in_window']['total'] == 0


@pytest.mark.parametrize('kwargs', [
    {'since': '2026-10-04'}, {'until': '2026-10-04T12:00:00+01:00'},
    {'since': '2026-10-05T00:00:00Z', 'until': '2026-10-04T00:00:00Z'},
    {'project': 'unknown'}, {'harness': 'unknown'},
])
def test_invalid_filters_fail_closed(tmp_path, kwargs):
    store, _, _ = seed(tmp_path)
    with pytest.raises(MemoryError):
        lifecycle.report(store, **kwargs)


def test_corrupt_curation_fails_closed_and_cli_no_partial_report(tmp_path):
    store, _, records = seed(tmp_path)
    path = store.root / 'curation/example' / (records['retired-handoff']['id'] + '.json')
    data = json.loads(path.read_text()); data['content_digest'] = '0' * 64
    path.write_text(json.dumps(data))
    command = ['python', str(SCRIPTS / 'report-memory-lifecycle.py'), '--root', str(store.root)]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 2, result.stderr
    payload = json.loads(result.stdout)
    assert payload['status'] == 'invalid' and payload['diagnostic']['code'] == 'corrupt_curation'
    assert 'current_projection' not in payload


def test_cli_stdout_and_no_report_files(tmp_path):
    store, _, _ = seed(tmp_path)
    before = protected(store)
    result = subprocess.run(['python', str(SCRIPTS / 'report-memory-lifecycle.py'), '--root', str(store.root),
                             '--project', 'example', '--since', '2026-10-04T00:00:00Z',
                             '--until', '2026-10-05T00:00:00Z'], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)['current_projection']['retired_handoffs'] == 1
    assert protected(store) == before
