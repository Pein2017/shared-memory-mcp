"""Final-budget regressions with real bounded file owners, not mocked owner metadata."""
from copy import deepcopy
import json

from dreaming_helpers import environment
from shared_memory_mcp.context_packet import exposure_size
from shared_memory_mcp.core import _digest
from shared_memory_mcp.dreaming import configure_policy
from test_context_modes_budgets import capture
from test_foreground_owner import bind_owner


def pressure_fixture(tmp_path):
    engine, store, _, caller, _, owner, _ = environment(tmp_path)
    bind_owner(store)
    routing_path = store.root / 'routing/demo.json'
    routing = json.loads(routing_path.read_text())
    policy, _ = engine._policy()
    policy = deepcopy(policy)
    # All literal excerpts have qualifiers and source identities; no generated summaries.
    owner.write_text('Current airport result: OWNER_INDEX; fixed CPU fixture, no transfer.\n' +
                     ('airport frozen conditions and counterevidence; no generalization.\n' * 25))
    for i, role in enumerate(['result', 'question', 'result', 'question']):
        path = owner.parent / (f'owner-{i}-' + 'long-source-name-' * 5 + '.md')
        path.write_text(f'Current airport {role}: OWNER_{i}; bounded CPU only.\n' +
                        ('airport frozen conditions and counterevidence; no generalization.\n' * 25))
        identifier = f'owner-{i}'
        routing['context']['owners'].append(dict(id=identifier, topic_ids=['research-entry'],
                                                 grant_id=identifier, role=role))
        policy['profiles']['fixture']['source_grants'].append(dict(id=identifier, kind='file', path=str(path),
                                                                  format='document', schema='document-v1'))
    configure_policy(store, policy, expected_revision=_digest(engine._policy()[0]))
    store._publish(routing_path, (json.dumps(routing) + '\n').encode())
    return store, caller, owner


def test_late_owner_omission_repackages_whole_evidence_instead_of_empty_diagnostic(tmp_path):
    store, caller, owner = pressure_fixture(tmp_path)
    for cap in [8000]:
        packet = store.context(caller, query='airport research status', task_mode='research', current_status=True, max_bytes=cap)
        assert packet['status'] == 'ok', packet
        assert packet['items'], 'A whole owner excerpt fits; do not lose it to late gap metadata'
        assert 'literal excerpt' in packet['text'] and 'no generalization' in packet['text']
        assert 'Original owner:' in packet['text'] and packet.get('continuation')
        assert packet['budget']['serialized_bytes'] == exposure_size(packet) <= cap
        status = packet['owner_checks']
        presented = {item['unit_id'] for item in packet['items'] if item['id'].startswith('owner:')}
        assert status['undelivered'] == [item['id'] for item in status['items'] if item['id'] not in presented]
        omitted = [gap for gap in status['gaps'] if gap['reason'] == 'owner_excerpt_budget_omitted']
        assert len(omitted) == 1 and omitted[0]['ids'] == status['undelivered']
        assert len({json.dumps(g, sort_keys=True) for g in status['gaps']}) == len(status['gaps'])
        assert len(status['gaps']) <= 16 + 1
        assert 'larger explicit supported cap' not in json.dumps(packet)


def test_final_pressure_never_separates_claim_from_counterevidence(tmp_path):
    store, caller, owner = pressure_fixture(tmp_path)
    claim = capture(store, caller, owner, 'airport-claim', 'CLAIM_FIXED_PANEL; airport finite control only. ' * 12, 'outcome')
    qualifier = capture(store, caller, owner, 'airport-qualifier', 'QUALIFIER_NO_TRANSFER; airport control did not generalize. ' * 12,
                        'outcome', relations=[{'type': 'conflicts_with', 'uri': 'record:' + claim['id']}])
    for cap in [128, 512, 1800, 3400, 6000, 7000, 8000]:
        result = store.context(caller, query='airport', current_status=True, max_bytes=cap)
        assert exposure_size(result) <= cap
        ids = {item['id'] for item in result.get('items', [])}
        assert (claim['id'] in ids) == (qualifier['id'] in ids)
        if claim['id'] in ids:
            assert 'CLAIM_FIXED_PANEL' in result['text'] and 'QUALIFIER_NO_TRANSFER' in result['text']
            assert 'Frozen fixture conditions; not transfer evidence.' in result['text']
        if result.get('continuation'):
            assert not isinstance(result['continuation'], str), 'Continuation is an exact read pointer, not cap-increase advice'
