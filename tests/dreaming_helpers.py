"""Disposable CPU-only Dreaming fixtures. All identities and claims are synthetic."""
import hashlib
import json

from shared_memory_mcp.core import MemoryStore
from shared_memory_mcp.dream_records import ACTIONS
from shared_memory_mcp.dreaming import Dreaming, configure_policy


def environment(tmp_path):
    target, executor = tmp_path / 'target', tmp_path / 'executor'
    target.mkdir(); executor.mkdir()
    owner = target / 'owner.md'
    owner.write_text('Fixture owner records coverage 7 under a fixed CPU control. Counterexample: no generalization is established.\n')
    human = target / 'human.jsonl'
    header = {'type': 'session_meta', 'payload': {'id': 'fixture-source-session', 'cli_version': 'fixture-v1', 'source': 'cli'}}
    message = {'type': 'response_item', 'id': 'human-1', 'timestamp': '2026-10-07T00:00:00Z',
               'payload': {'type': 'message', 'role': 'user', 'content': [{'type': 'input_text', 'text': 'For this fixture, research detail and brief acceptance reports are different scenarios.'}]}}
    raw_message = (json.dumps(message) + '\n').encode()
    human.write_bytes((json.dumps(header) + '\n').encode() + raw_message)
    sources = [{'id': 'owner', 'path': str(owner), 'format': 'document', 'schema': 'document-v1'},
               {'id': 'human', 'path': str(human), 'format': 'codex', 'schema': 'codex-rollout-v1', 'native_version': 'fixture-v1',
                'attestations': {hashlib.sha256(raw_message).hexdigest(): {'subject': 'Pein', 'basis': 'Synthetic fixture operator attestation; not a real user claim'}}}]
    store = MemoryStore(tmp_path / 'memory'); store.init()
    store.register('demo', [target]); store.register('runner', [executor])
    caller = {'cwd': str(executor), 'harness': 'codex', 'session_id': 'fixture-executor-A', 'actor': 'fixture-dreamer'}
    owner_caller = {'cwd': str(target), 'harness': 'codex', 'session_id': 'fixture-owner', 'actor': 'fixture-owner'}
    profile = {'target_projects': ['demo'], 'executor_projects': ['demo', 'runner'], 'source_grants': [{**s, 'kind': 'file'} for s in sources],
               'actions': sorted(ACTIONS), 'provider': 'none', 'transport': 'local-fixture',
               'budgets': {'source_bytes': 65536, 'events': 32, 'operations': 16, 'drafts': 8,
                           'view_chars': 4000, 'view_bytes': 16000, 'model_calls': 0, 'input_tokens': 0,
                           'output_tokens': 0, 'seconds': 3600, 'repair_rounds': 2},
               'scenarios': ['research', 'engineering', 'acceptance'], 'allow_inferred': True}
    policy = {'version': 2, 'subject': 'Pein', 'collaboration_projects': ['demo'], 'profiles': {'fixture': profile}}
    configure_policy(store, policy)
    engine = Dreaming(store, 'fixture', caller, publisher=True)
    return engine, store, caller, owner_caller, policy, owner, human


def claim(ref, *, level='recorded', text='The fixture owner records coverage 7.', scenario='research'):
    return {'topic': 'fixture-coverage', 'text': text, 'level': level,
            'conditions': 'Only the fixed disposable CPU fixture; not a scientific conclusion.',
            'exceptions': ['Does not grant execution authority.'], 'counterevidence': ['No generalization test.'],
            'scenarios': [scenario], 'projects': ['demo'], 'refs': [ref], 'risks': []}


def review(refs, *, decision='approve'):
    return {'decision': decision, 'reason': 'Synthetic fixture semantic review only.', 'scope_checked': True,
            'counterexamples_checked': True, 'checked_refs': list(refs)}


def begin(engine):
    result = engine.start()
    run_id, generation = result['run_id'], result['generation']
    material = engine.materials(run_id)['sources']
    owner_key = material['owner']['events'][0]['key']
    human_key = material['human']['events'][0]['key']
    return run_id, generation, owner_key, human_key


def record_op(identifier, c, *, visibility='active'):
    return {'id': identifier, 'action': 'record_create', 'claim': c, 'review': review(c['refs']), 'visibility': visibility}


def view_op(identifier, c, *, kind='research'):
    return {'id': identifier, 'action': 'view_publish', 'view': kind, 'claims': [c], 'review': review(c['refs'])}


def freeze_publish(engine, run_id, generation, operations, **kwargs):
    frozen = engine.freeze(run_id, generation, operations, **kwargs)
    result = engine.publish(run_id, generation, frozen['draft_revision'])
    return frozen, result
