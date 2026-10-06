"""Isolated example corpus only. Never points at or seeds an existing store."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

from shared_memory_mcp.core import MemoryStore, _digest, _json

BASELINE = '7963ccaa59abf8a27a1f86f4e517da124019fd5b'
PACKAGE = Path(__file__).resolve().parents[1]
FIXTURE = PACKAGE / 'tests/fixtures/retrieval-cases.json'


def corpus():
    return json.loads(FIXTURE.read_text('utf-8'))


def source(spec):
    if spec.get('derivative'):
        return {'uri': (PACKAGE / spec['path']).as_uri(), 'locator': spec['locator']}
    return {'uri': PACKAGE.as_uri().replace('file:', 'git+file:', 1)
            + '?rev=' + BASELINE + '&path=' + spec['path'], 'locator': spec['locator']}


def seed_record(store, ctx, key, record, *, created_at='2026-10-04T12:00:00Z', status='active'):
    """Write validated legacy canonical fixture bytes; does not bypass admission in production.

    New handoff API admission intentionally cannot construct historical test data.
    The test-only deterministic header retains the existing version-1 format.
    """
    identity = hashlib.md5(key.encode(), usedforsecurity=False).hexdigest()
    provenance = {k: ctx[k] for k in ('cwd', 'harness', 'session_id', 'actor')}
    r = {**record, 'version': 1, 'id': identity, 'project_id': ctx['project_id'],
         'created_at': created_at, 'status': status, 'provenance': provenance,
         'proposal': {'key': key, 'digest': _digest({'fixture': key})}}
    if status == 'active':
        r.update(review={'reason': 'Synthesized qualification fixture; not production evidence.',
                         'evidence': record['sources'], 'reviewer': provenance, 'reviewed_at': created_at},
                 promotion={'key': key + ':review', 'digest': _digest({'fixture_review': key})})
    r['content_digest'] = _digest(store._content(r))
    path = store.root / 'records' / ctx['project_id'] / (identity + '.md')
    header = {k: v for k, v in r.items() if k != 'body'}
    store._validate_canonical(header, r['body'], path, ctx['project_id'])
    with store._gate():
        store._write(r, create=True)
    return r


def seed(base):
    """base must be a newly allocated empty directory, e.g. TemporaryDirectory."""
    base = Path(base)
    if list(base.iterdir()):
        raise ValueError('Fixture base must be empty')
    projects = {}
    store = MemoryStore(base / 'memory')
    store.init()
    for project in ('example', 'foreign'):
        path = base / project
        path.mkdir()
        store.register(project, [path])
        projects[project] = {'cwd': str(path), 'harness': 'codex', 'session_id': 'isolated-qualification',
                             'actor': 'fixture', 'project_id': project}
    data = corpus()
    records = {}
    for spec in data['records']:
        ctx = projects[spec.get('project', 'example')]
        record = {k: spec[k] for k in ('kind', 'title', 'body')}
        record.update(scope='project', sources=[source(s) for s in spec['sources']])
        r = seed_record(store, ctx, spec['key'], record)
        records[spec['key']] = r
        details = {**spec.get('details', {}), 'source_roles': [
            {'uri': uri['uri'], 'role': 'derivative' if s.get('derivative') else 'owner'}
            for s, uri in zip(spec['sources'], r['sources'])]}
        if details or spec.get('retired'):
            store.curate(ctx, r['id'], {'reason': 'Isolated fixture metadata.', 'evidence': r['sources']},
                         spec['key'] + ':curate', details=details, retired=spec.get('retired'))
    directory = store.root / 'routing'
    directory.mkdir()
    routing = {**data['routing']}
    routing['topics'] = [{**t, 'sources': [source(s) for s in t['sources']]} for t in routing['topics']]
    (directory / 'example.json').write_text(_json(routing), encoding='utf-8')
    return store, projects['example'], records


def qualify(store, context, records, limit=2):
    """Observe complete revision-fenced lexical ranks; top page absence is not failure."""
    results = []
    for case in corpus()['cases']:
        observations = []
        for form, query in case['queries'].items():
            first = store.search(context, query, limit=limit)
            pages, cards = [first], list(first['items'])
            page = first
            while page['next_offset'] is not None:
                page = store.search(context, query, limit=limit, offset=page['next_offset'],
                                    expected_revision=first['corpus_revision'])
                pages.append(page)
                cards.extend(page['items'])
            ids = [r['id'] for r in cards]
            def position(key):
                identity = records[key]['id']
                return ids.index(identity) + 1 if identity in ids else None
            expected = case['expected_useful']
            reads = store.read(context, [records[k]['id'] for k in expected]) if expected else {'items': []}
            observations.append({
                'form': form, 'query': query, 'total_matches': first['total_matches'],
                'first_page_ids': [r['id'] for r in first['items']],
                'first_page_omitted': first['omitted'], 'first_page_truncated': first['truncated'],
                'pages': len(pages), 'complete_rank_ids': ids,
                'useful_ranks': {k: position(k) for k in expected},
                'distractor_ranks': {k: position(k) for k in case['nearest_confusable']},
                'negative_evidence_ranks': {k: position(k) for k in case['relevant_negative_evidence']},
                'lexical_misses_after_complete_pagination': [k for k in expected if position(k) is None],
                'source_reads': [{'id': r['id'], 'sources': r['sources'],
                                 'source_read_hints': r['source_read_hints']} for r in reads['items']],
                'empty_result': not ids,
            })
        results.append({**case, 'observations': observations})
    baseline = subprocess.run(['git', '-C', str(PACKAGE), 'show', BASELINE + ':src/shared_memory_mcp/recall.py'],
                              capture_output=True, text=True, check=True).stdout
    unchanged = (PACKAGE / 'src/shared_memory_mcp/recall.py').read_text('utf-8') == baseline
    return {'status': 'ok', 'evidence_boundary': corpus()['evidence_boundary'], 'baseline': BASELINE,
            'cases': results, 'recall_source_matches_baseline': unchanged,
            'ranking_changed': False if unchanged else None,
            'limitations': [
                'This explicitly synthesized bounded corpus checks plumbing and observes ranks; it does not establish production retrieval quality.',
                'Useful targets and distractors are source/applicability judgments recorded before retrieval, not lexical truth labels.',
                'No aggregate quality threshold; misses are reported, including unknown paraphrases without curated expansion.',
                'A recall source mismatch requires source review; it alone does not prove a ranking behavior change.',
                'Complete ranks follow revision-fenced pagination; previews and first-page omissions are not missing evidence.',
                'Full reads verify recoverable pointers; this runner does not automatically inspect or certify original source contents.',
                'No model/provider calls, token savings, invocation frequency, latency, or scientific truth conclusions.',
            ]}
