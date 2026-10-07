#!/usr/bin/env python3
"""Generate a source-linked Dreaming delivery example in a disposable store.

Checkout qualification only: imports synthetic test helpers, never a configured
production store, native session history, model/provider or research runner.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import tempfile

PACKAGE = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PACKAGE / 'src'), str(PACKAGE / 'tests')]
from dreaming_helpers import environment, begin, claim, review, record_op, view_op
from shared_memory_mcp.dream_transport import capabilities


def write_json(output, name, value):
    (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New or empty output directory for synthetic evidence')
    args = parser.parse_args()
    output = args.output.absolute()
    if any(p.is_symlink() for p in (output, *output.parents)):
        parser.error('Output path must not contain a symlink')
    if output.exists() and (not output.is_dir() or any(output.iterdir())):
        parser.error('Output must be a new or empty directory; existing evidence is never overwritten')
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='dream-v02-delivery-fixture-') as temporary:
        engine, store, caller, owner_caller, policy, owner, human = environment(Path(temporary))
        before = {p: (p.read_bytes(), p.stat().st_size, p.stat().st_mtime_ns, p.stat().st_ino) for p in (owner, human)}
        rid, gen, owner_key, human_key = begin(engine)
        materials = engine.materials(rid)
        write_json(output, 'materials.json', materials)
        c = claim(human_key, level='explicit', text='Synthetic fixture only: detailed research and brief acceptance are separate scenarios.')
        collab = {'id': 'C', 'action': 'collaboration_create', 'claim': c, 'review': review(c['refs']), 'visibility': 'active'}
        vc = deepcopy(c); vc['refs'] = ['op:C']
        risk = claim(owner_key); risk['risks'] = ['execution-authority']
        operations = [record_op('A', claim(owner_key)), record_op('B-rejected', risk), collab,
                      view_op('research-view', claim('op:A')), view_op('collaboration-view', vc, kind='collaboration')]
        frozen = engine.freeze(rid, gen, operations)
        write_json(output, 'draft-input.json', operations)
        write_json(output, 'candidate-diff.json', engine.candidate_diff(rid, frozen['draft_revision']))
        result = engine.publish(rid, gen, frozen['draft_revision'])
        assert result['status'] == 'partial' and [x['operation_id'] for x in result['unresolved']] == ['B-rejected']
        views = {name: engine.overview(name, scenario='research') for name in ('research', 'collaboration')}
        assert all(v['status'] == 'valid' for v in views.values())
        record_id = frozen['operations'][0]['reserved_id']
        canonical = store.root / 'records/demo' / (record_id + '.md')
        original = canonical.read_bytes()
        store.delete(owner_caller, record_id, {'reason': 'Synthetic dependency withdrawal', 'evidence': [{'uri': owner.as_uri()}]}, 'fixture-withdraw')
        assert canonical.read_bytes() == original
        current = engine.overview('research', scenario='research')
        historical = engine.overview('research', scenario='research', historical=views['research']['revision'])
        assert current['status'] == historical['status'] == 'invalidated'
        assert current['text'] == historical['text'] == ''
        assert engine.overview('collaboration', scenario='research')['status'] == 'valid'
        engine.close(rid, gen, abandon_reason='Rejected risky claim; externally withdrawn dependency requires explicit partial close')
        sources = []
        for path, (raw, size, mtime, inode) in before.items():
            st = path.stat()
            assert (path.read_bytes(), st.st_size, st.st_mtime_ns, st.st_ino) == (raw, size, mtime, inode)
            name = 'source-' + path.name
            (output / name).write_bytes(raw)
            sources.append({'original_fixture_uri': path.as_uri(), 'archived_file': name,
                            'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': size,
                            'content_size_mtime_inode_unchanged': True})
        write_json(output, 'source-manifest.json', {'synthetic_only': True, 'temporary_originals_removed_after_run': True,
                   'sources': sources, 'event_refs': {'owner': owner_key, 'human': human_key}})
        write_json(output, 'publication.json', result)
        write_json(output, 'views-before.json', views)
        write_json(output, 'views-after-withdrawal.json', {'current': current, 'historical': historical})
        write_json(output, 'run-after.json', engine.inspect(rid))
        write_json(output, 'capabilities.json', capabilities())
        write_json(output, 'receipt.json', {'status': 'passed', 'boundary': 'synthetic disposable canonical store only',
                   'models_called': 0, 'production_memory_writes': 0, 'native_harness_qualification': False,
                   'partial_publication': True, 'withdrawn_default_and_historical_hidden': True,
                   'collaboration_independent': True, 'source_files_unchanged': True,
                   'run_id': rid, 'draft_revision': frozen['draft_revision'], 'actual_fixture_executor': caller})
    print(json.dumps({'status': 'passed', 'output': str(output), 'synthetic_only': True, 'model_calls': 0}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
