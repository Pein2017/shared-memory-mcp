"""Source/visibility/pagination checks, never an arbitrary top-k quality gate."""
import json
from pathlib import Path
import subprocess
import sys

import pytest
from shared_memory_mcp.core import MemoryError

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
from retrieval_fixture import BASELINE, PACKAGE, corpus, qualify, seed, source, ranking_source_signature


def test_cases_bind_sources_applicability_and_seven_failure_classes():
    data = corpus()
    classes = {c for case in data['cases'] for c in case['failure_classes']}
    assert classes == {'identifier-vs-split-entity', 'version-or-condition', 'relevant-negative-result',
                       'long-vs-concise', 'cjk-curated-alias-and-unknown-paraphrase',
                       'derivative-vs-original', 'retired-handoff-and-foreign-scope'}
    keys = {r['key'] for r in data['records']}
    for case in data['cases']:
        assert case['task_question'] and case['applicability_rationale'] and case['queries']
        assert set(case['expected_useful'] + case['nearest_confusable'] + case['relevant_negative_evidence']) <= keys
        assert case['expected_useful'] and case['nearest_confusable']
    for record in data['records']:
        for src in record['sources']:
            assert src['locator']
            if src.get('derivative'):
                assert (PACKAGE / src['path']).is_file()
            else:
                checked = subprocess.run(['git', '-C', str(PACKAGE), 'show', BASELINE + ':' + src['path']],
                                         capture_output=True, text=True)
                assert checked.returncode == 0, checked.stderr
                # Source owners are checked symbols, not invented URI text.
                for symbol in src['locator'].split('; '):
                    assert 'def ' + symbol.rsplit('.', 1)[-1] + '(' in checked.stdout


def test_real_runtime_visibility_and_source_read_pointers(tmp_path):
    store, ctx, records = seed(tmp_path)
    result = store.search(ctx, 'retirement lifecycle projection', limit=1)
    assert result['omitted'] > 0 and result['next_offset'] == 1
    report = qualify(store, ctx, records, limit=1)
    observation = next(c for c in report['cases'] if c['id'] == 'visibility')['observations'][0]
    assert observation['pages'] > 1
    assert observation['distractor_ranks'] == {'retired-handoff': None, 'foreign-projection': None}
    original = store.read(ctx, [records['original-projection']['id']])['items'][0]
    assert original['body'] == records['original-projection']['body']
    hint = original['source_read_hints'][0]
    assert hint == {'kind': 'git', 'repository': str(PACKAGE), 'revision': BASELINE,
                    'path': 'src/shared_memory_mcp/curation.py', 'locator': 'projected_records; journals'}
    history = store.read(ctx, [records['retired-handoff']['id']], True)['items'][0]
    assert history['kind'] == 'handoff' and history['effective_status'] == 'retired'
    foreign = store.read(ctx, [records['foreign-projection']['id']], True)
    assert foreign['items'] == [] and foreign['missing_ids'] == [records['foreign-projection']['id']]
    derivative = store.read(ctx, [records['derivative-projection']['id']])['items'][0]
    assert derivative['details']['source_roles'][0]['role'] == 'derivative'


def test_alias_and_unknown_paraphrase_report_honest_miss(tmp_path):
    store, ctx, records = seed(tmp_path)
    case = next(c for c in qualify(store, ctx, records)['cases'] if c['id'] == 'cjk-alias')
    alias, unknown = case['observations']
    assert alias['useful_ranks']['register'] is not None
    assert unknown['empty_result'] and unknown['lexical_misses_after_complete_pagination'] == ['register']
    assert unknown['total_matches'] == 0


def test_rank_is_frozen_and_revision_fence_is_exercised(tmp_path):
    checked = subprocess.run(['git', '-C', str(PACKAGE), 'show', BASELINE + ':src/shared_memory_mcp/recall.py'],
                             capture_output=True, text=True, check=True)
    current = (PACKAGE / 'src/shared_memory_mcp/recall.py').read_text()
    assert ranking_source_signature(current) == ranking_source_signature(checked.stdout)
    # A real scoring change must still break this fence; no blanket baseline refresh.
    assert "'title': 4.0" in current
    assert ranking_source_signature(current.replace("'title': 4.0", "'title': 9.0", 1)) != ranking_source_signature(current)
    store, ctx, records = seed(tmp_path)
    first = store.search(ctx, 'retirement lifecycle projection', limit=1)
    original = records['original-projection']
    store.curate(ctx, original['id'], {'reason': 'Fixture revision change.', 'evidence': original['sources']},
                 'revision-change', details={'summary': 'Changed fixture projection summary.'})
    with pytest.raises(MemoryError) as error:
        store.search(ctx, 'retirement lifecycle projection', offset=first['next_offset'],
                     expected_revision=first['corpus_revision'])
    assert error.value.code == 'stale_search'


def test_isolated_cli_reports_without_live_store(tmp_path):
    result = subprocess.run(['python', str(SCRIPTS / 'qualify-retrieval.py'), '--limit', '1'],
                            cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert len(report['cases']) == 7 and report['ranking_changed'] is False
    assert report['ranking_source_matches_baseline'] is True
    assert report['recall_source_matches_baseline'] is False  # Dream source-use admission is intentionally new.
    assert list(tmp_path.iterdir()) == []
