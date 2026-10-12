import json

import pytest

from shared_memory_mcp.core import MemoryStore
from shared_memory_mcp.dream_records import render_claim
from shared_memory_mcp.operations import call
from shared_memory_mcp.recall import semantic_body


DIGEST = 'a' * 64
MACHINE_NOTE = 'dream-source-v1:{"source_grant":"' + DIGEST + '","source_spec":{"digest":"' + DIGEST + '"}}'


@pytest.fixture
def memory(tmp_path, monkeypatch):
    monkeypatch.setattr('shared_memory_mcp.dreaming.record_use_filter',
                        lambda store, **kwargs: lambda record: True)
    project = tmp_path / 'project'
    project.mkdir()
    store = MemoryStore(tmp_path / 'memory')
    store.init()
    store.register('demo', [project])
    caller = {'cwd': str(project), 'harness': 'codex', 'session_id': 'semantic-render', 'actor': 'test'}
    sources = [
        {'uri': 'file:///tmp/owner.md', 'locator': 'L12', 'note': MACHINE_NOTE},
        {'uri': 'file:///tmp/review.md', 'locator': 'L30', 'note': 'Human review note retained.'},
    ]
    record = {'kind': 'observation', 'title': 'Qualified semantic finding',
              'body': 'The bounded result remains unresolved.\nConditions: one reviewed fixture.\nSources: ' + DIGEST + ', ' + DIGEST,
              'scope': 'project', 'sources': sources}
    review = {'reason': 'Reviewed the source text and scope.', 'evidence': sources}
    candidate = store.propose(caller, record, 'semantic-render')['record']
    accepted = store.promote(caller, candidate['id'], review, 'semantic-render:approve')['record']
    routing = store.root / 'routing'
    routing.mkdir()
    (routing / 'demo.json').write_text(json.dumps({'version': 1, 'description': 'Find the reviewed owner route.',
        'topics': [{'id': 'owner', 'title': 'Owner route', 'when': 'When checking this finding.',
                    'aliases': ['unresolved'], 'sources': sources}]}))
    return store, caller, accepted, sources


def test_compact_claim_keeps_semantics_and_opaque_refs_but_hides_digest_inventory():
    claim = {'topic': 'Qualified result', 'text': 'The result remains unresolved.', 'level': 'report',
             'conditions': 'One reviewed fixture.', 'exceptions': [], 'counterevidence': [],
             'scenarios': ['research'], 'projects': ['demo'], 'refs': [DIGEST, 'owner-event-L12'], 'risks': []}

    rendered = render_claim(claim, compact=True)

    assert 'The result remains unresolved.' in rendered
    assert 'Conditions: One reviewed fixture.' in rendered
    assert 'research' in rendered and 'demo' in rendered
    assert 'owner-event-L12' in rendered and DIGEST not in rendered
    assert DIGEST in render_claim(claim)
    assert semantic_body('Claim\nSources: ' + DIGEST + ', owner.md\n') == 'Claim\nSources: owner.md\n'


def test_ordinary_consumers_show_routes_and_clean_legacy_internals_while_audit_stays_raw(memory):
    store, caller, record, sources = memory

    card = store.search(caller, 'unresolved')['items'][0]
    search = store.search(caller, 'unresolved')
    context = store.context(caller, query='unresolved')
    ordinary = call(store, 'read', {'caller': caller, 'ids': [record['id']]})['items'][0]
    audited = call(store, 'read', {'caller': caller, 'ids': [record['id']], 'audit': True})['items'][0]

    assert DIGEST not in card['body'] and DIGEST not in context['text'] and DIGEST not in ordinary['body']
    assert '/tmp/owner.md' in context['text']
    assert ordinary['source_read_hints'][0]['path'] == '/tmp/owner.md'
    assert 'dream-source-v1:' not in json.dumps(search['routes'])
    assert 'dream-source-v1:' not in json.dumps(context['routes'])
    assert not {'content_digest', 'curation_revision', 'proposal', 'promotion', 'review', 'curation_audit'} & ordinary.keys()
    assert 'dream-source-v1:' not in json.dumps(card['sources'])
    assert 'dream-source-v1:' not in json.dumps(ordinary['sources'])
    assert any(source.get('note') == 'Human review note retained.' for source in ordinary['sources'])
    assert audited['body'] == record['body'] and audited['sources'] == sources
    assert {'content_digest', 'curation_revision', 'proposal', 'promotion', 'review', 'curation_audit'} <= audited.keys()


def test_ordinary_detail_continuation_reassembles_the_sanitized_account(memory):
    store, caller, record, sources = memory
    long_record = {'kind': record['kind'], 'scope': record['scope'], 'sources': sources,
                   'title': 'Long qualified semantic finding',
                   'body': record['body'] + '\n' + ('A bounded qualification remains part of the semantic account. ' * 80)}
    candidate = store.propose(caller, long_record, 'long-semantic-render')['record']
    record = store.promote(caller, candidate['id'], {'reason': 'Reviewed the source text and scope.',
                            'evidence': sources}, 'long-semantic-render:approve')['record']

    first = call(store, 'read', {'caller': caller, 'ids': [record['id']], 'max_bytes': 1280})
    page = first['items'][0]['cursor']
    fragments = []
    while page:
        result = call(store, 'read', {'caller': caller, 'ids': [record['id']], 'max_bytes': 1280, 'cursor': page})
        fragments.append(result['detail_page']['text'])
        page = result['next_cursor']

    detail = json.loads(''.join(fragments))
    assert 'A bounded qualification remains part of the semantic account.' in detail['body']
    assert DIGEST not in detail['body']
    assert 'dream-source-v1:' not in json.dumps(detail['sources'])
