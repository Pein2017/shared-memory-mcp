"""Public wire-schema fixtures only, not native paid-model qualification."""
import hashlib
import json
import os
from pathlib import Path

import pytest

from shared_memory_mcp.core import MemoryError
from shared_memory_mcp.dream_sources import read_source, check_snapshot, MAX_LINE


def line(value):
    return (json.dumps(value) + '\n').encode()


def source(tmp_path, harness, values, **options):
    path = tmp_path / f'{harness}.jsonl'
    path.write_bytes(b''.join(line(v) for v in values))
    formats = {'codex': 'codex-rollout-v1', 'pi': 'pi-session-v3', 'claude': 'claude-jsonl-v1'}
    return {'id': harness, 'path': str(path), 'format': harness, 'schema': formats[harness], **options}


def codex_message(text='Original expression.', *, role='user', identifier='u1'):
    return {'type': 'response_item', 'id': identifier, 'timestamp': '2026-10-07T00:00:00Z',
            'payload': {'type': 'message', 'role': role,
                        'content': [{'type': 'input_text' if role == 'user' else 'output_text', 'text': text}]}}


HEADER = {'type': 'session_meta', 'payload': {'id': 'fixture-session', 'cli_version': 'fixture-v1', 'source': 'cli'}}


def attest(event):
    return {hashlib.sha256(line(event)).hexdigest(): {'subject': 'Pein', 'basis': 'Synthetic operator fixture attestation'}}


@pytest.mark.parametrize('delegated', [False, True])
def test_user_role_needs_separate_operator_attestation_and_delegate_never_becomes_human(tmp_path, delegated):
    event = codex_message()
    header = json.loads(json.dumps(HEADER))
    if delegated:
        header['payload']['source'] = {'subagent': {'parent_thread_id': 'fixture-parent'}}
    spec = source(tmp_path, 'codex', [header, event], native_version='fixture-v1')
    assert read_source(spec)['events'][0]['human'] == 'unknown'
    spec['attestations'] = attest(event)
    projected = read_source(spec)
    assert projected['events'][0]['human'] == ('unknown' if delegated else 'attested-Pein')


def test_copied_user_text_is_not_independent_human_evidence(tmp_path):
    message = codex_message('Quoted report: user said "I prefer X".', role='assistant')
    spec = source(tmp_path, 'codex', [HEADER, message], native_version='fixture-v1', attestations=attest(message))
    event = read_source(spec)['events'][0]
    assert event['human'] == 'unknown' and event['role'] == 'assistant'


def test_codex_public_projection_excludes_instructions_thinking_tools_and_duplicate_event_channel(tmp_path):
    user = codex_message()
    values = [HEADER, codex_message('PRIVATE_SYSTEM', role='system', identifier='sys'),
              {'type': 'response_item', 'payload': {'type': 'reasoning', 'text': 'PRIVATE_THINKING'}},
              {'type': 'response_item', 'payload': {'type': 'function_call_output', 'output': 'PRIVATE_TOOL'}},
              {'type': 'event_msg', 'payload': {'type': 'user_message', 'message': 'Original expression.'}}, user, user]
    spec = source(tmp_path, 'codex', values, native_version='fixture-v1')
    before = Path(spec['path']).read_bytes()
    st = Path(spec['path']).stat()
    result = read_source(spec)
    assert len(result['events']) == 1
    public = json.dumps(result['events'])
    assert 'PRIVATE_' not in public
    assert Path(spec['path']).read_bytes() == before
    after = Path(spec['path']).stat()
    assert (st.st_size, st.st_mtime_ns, st.st_ino) == (after.st_size, after.st_mtime_ns, after.st_ino)
    assert result['coverage']['complete']


def test_pi_branches_shared_ancestor_once_and_compaction_gap(tmp_path):
    def event(identifier, parent, text, **extra):
        return {'type': 'message', 'id': identifier, 'parentId': parent,
                'message': {'role': 'user', 'content': [{'type': 'text', 'text': text}]}, **extra}
    ancestor = event('A', None, 'Shared original.')
    values = [{'type': 'session', 'id': 'fixture-pi', 'version': 3}, ancestor,
              event('B', 'A', 'Alternative branch.'), event('C', 'A', 'Active branch.', source='rpc'),
              {'type': 'compaction', 'id': 'compact', 'summary': 'No original transcript supplied.'}]
    spec = source(tmp_path, 'pi', values, leaf_id='C', attestations=attest(values[3]))
    result = read_source(spec)
    assert [e['event_id'] for e in result['events']] == ['A', 'C']
    assert all(e['branch'] == 'C' for e in result['events'])
    assert result['events'][1]['human'] == 'unknown'
    assert not result['coverage']['complete']
    assert any(g['reason'] == 'compaction_originals_not_proven' for g in result['coverage']['gaps'])


def test_pi_active_branch_is_not_inferred_from_last_message(tmp_path):
    spec = source(tmp_path, 'pi', [{'type': 'session', 'id': 'p', 'version': 3},
                                  {'type': 'message', 'id': 'm', 'parentId': None,
                                   'message': {'role': 'user', 'content': 'Synthetic expression'}}])
    result = read_source(spec)
    assert not result['coverage']['complete']
    assert any(g['reason'] == 'active_branch_unverified' for g in result['coverage']['gaps'])


def test_claude_sidechain_attribution_and_exact_native_version(tmp_path):
    event = {'type': 'user', 'version': 'fixture-v1', 'uuid': 'u', 'parentUuid': None,
             'sessionId': 'fixture-c', 'isSidechain': True,
             'message': {'role': 'user', 'content': 'Worker delegated request'}}
    spec = source(tmp_path, 'claude', [event], native_version='fixture-v1', attestations=attest(event))
    projected = read_source(spec)
    assert projected['events'][0]['human'] == 'unknown'
    spec['native_version'] = 'unknown-new-version'
    unknown = read_source(spec)
    assert unknown['events'] == [] and unknown['coverage']['gaps'][0]['reason'] == 'unknown_native_version'


@pytest.mark.parametrize('suffix,reason', [(b'{broken}\n', 'malformed_event'),
                                          (b'{"type":"message"', 'partial_line'),
                                          (b'x' * (MAX_LINE * 3) + b'\n', 'oversized_event'),
                                          (line({'type': 'future-schema'}), 'unknown_event_schema')])
def test_corruption_large_partial_and_unknown_events_are_gaps_not_silence(tmp_path, suffix, reason):
    spec = source(tmp_path, 'codex', [HEADER], native_version='fixture-v1')
    with Path(spec['path']).open('ab') as stream:
        stream.write(suffix)
    result = read_source(spec, max_bytes=MAX_LINE * 4)
    assert any(g['reason'] == reason for g in result['coverage']['gaps'])
    assert not result['coverage']['complete']
    assert result['coverage']['read_bytes'] <= MAX_LINE * 4


def test_cursor_detects_prefix_edit_even_with_restored_mtime_and_same_size(tmp_path):
    spec = source(tmp_path, 'codex', [HEADER, codex_message('One'), codex_message('Two', identifier='u2')], native_version='fixture-v1')
    result = read_source(spec, max_events=1)
    path = Path(spec['path']); before = path.stat()
    data = path.read_bytes().replace(b'One', b'Ono')
    path.write_bytes(data); os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
    with pytest.raises(MemoryError) as error:
        read_source(spec, cursor=result['cursor'])
    assert error.value.code == 'source_changed'
    assert check_snapshot(spec, result['version']) == 'stale'


def test_cursor_continuation_uses_frozen_cutoff_not_appended_future(tmp_path):
    spec = source(tmp_path, 'codex', [HEADER, codex_message('One'), codex_message('Two', identifier='u2')], native_version='fixture-v1')
    first = read_source(spec, max_events=1)
    with Path(spec['path']).open('ab') as stream:
        stream.write(line(codex_message('Future', identifier='u3')))
    second = read_source(spec, cursor=first['cursor'])
    assert [e['text'] for e in second['events']] == ['Two']
    assert second['cursor']['cutoff'] == first['cursor']['cutoff']
    assert second['coverage']['verification_bytes'] > second['coverage']['read_bytes']


def test_path_replacement_and_symlink_are_not_silent_relocations(tmp_path):
    spec = source(tmp_path, 'codex', [HEADER, codex_message()], native_version='fixture-v1')
    first = read_source(spec)
    path = Path(spec['path']); replacement = tmp_path / 'replacement'
    replacement.write_bytes(path.read_bytes()); replacement.replace(path)
    with pytest.raises(MemoryError):
        read_source(spec, cursor=first['cursor'])
    assert check_snapshot(spec, first['version']) == 'unverifiable'
    other = tmp_path / 'link'; other.symlink_to(path)
    with pytest.raises(MemoryError):
        read_source({**spec, 'path': str(other)})


def test_derived_source_keeps_lineage_and_does_not_change_human_type(tmp_path):
    event = codex_message(role='assistant')
    spec = source(tmp_path, 'codex', [HEADER, event], native_version='fixture-v1', derived=True, lineage=['worker-origin'])
    item = read_source(spec)['events'][0]
    assert item['evidence'] == 'derivative' and item['human'] == 'unknown'
    assert item['lineage'] == ['worker-origin']


def test_codex_fork_keeps_rollout_owner_and_delegation_after_inherited_header(tmp_path):
    child = {'type': 'session_meta', 'payload': {'id': 'child', 'cli_version': 'fixture-v1',
             'source': {'subagent': {'parent_thread_id': 'fixture-session'}},
             'forked_from_id': 'fixture-session'}}
    inherited = codex_message('Inherited parent expression.')
    spec = source(tmp_path, 'codex', [child, HEADER, inherited],
                  native_version='fixture-v1', attestations=attest(inherited))
    result = read_source(spec)
    assert result['events'][0]['session'] == 'child'
    assert result['events'][0]['session_parent'] == 'fixture-session'
    assert result['events'][0]['delegated']
    assert result['events'][0]['human'] == 'unknown'
    assert not result['coverage']['complete']


def test_codex_later_header_cannot_attest_ambiguous_user_even_for_cli_owner(tmp_path):
    event = codex_message()
    spec = source(tmp_path, 'codex', [HEADER, HEADER, event],
                  native_version='fixture-v1', attestations=attest(event))
    first = read_source(spec, max_bytes=len(line(HEADER)))
    result = read_source(spec, cursor=first['cursor'])
    assert result['events'][0]['session'] == 'fixture-session'
    assert result['events'][0]['human'] == 'unknown'
    assert not result['coverage']['complete']


def claude_message(identifier, parent, *, role='assistant', text=None):
    return {'type': role, 'version': 'fixture-v1', 'uuid': identifier, 'parentUuid': parent,
            'sessionId': 'fixture-c',
            'message': {'role': role, 'content': text or f'Synthetic branch {identifier} report.'}}


def test_claude_selects_only_verified_leaf_ancestors(tmp_path):
    spec = source(tmp_path, 'claude', [claude_message('A', None, role='user'),
                  claude_message('B', 'A'), claude_message('C', 'A')],
                  native_version='fixture-v1', leaf_id='C')
    result = read_source(spec)
    assert [e['event_id'] for e in result['events']] == ['A', 'C']
    assert all(e['branch'] == 'C' for e in result['events'])
    assert result['coverage']['complete']
    assert result['coverage']['excluded'] == 1


@pytest.mark.parametrize('values,leaf', [
    ([claude_message('C', 'missing')], 'C'),
    ([claude_message('C', 'C')], 'C'),
    ([claude_message('A', 'C'), claude_message('C', 'A')], 'C'),
    ([claude_message('A', None)], 'missing'),
    ([claude_message('A', None), claude_message('C', 'A'),
      claude_message('C', 'A', text='Conflicting selected event')], 'C'),
    ([claude_message('A', None), claude_message('C', 42)], 'C'),
    ([{k: v for k, v in claude_message('C', None).items() if k != 'parentUuid'}], 'C'),
])
def test_claude_unverified_or_ambiguous_chain_is_never_admitted(tmp_path, values, leaf):
    options = {'leaf_id': leaf} if leaf else {}
    spec = source(tmp_path, 'claude', values, native_version='fixture-v1', **options)
    result = read_source(spec)
    assert result['events'] == []
    assert not result['coverage']['complete']
    assert result['coverage']['gaps']


def test_claude_without_selected_leaf_preserves_public_projection_with_gap(tmp_path):
    spec = source(tmp_path, 'claude', [claude_message('A', None)], native_version='fixture-v1')
    result = read_source(spec)
    assert result['events'][0]['event_id'] == 'A'
    assert result['events'][0]['branch'] == 'unspecified'
    assert not result['coverage']['complete']
    assert any(g['reason'] == 'active_branch_unverified' for g in result['coverage']['gaps'])


def test_claude_incomplete_bounded_ancestry_is_not_usable_evidence(tmp_path):
    spec = source(tmp_path, 'claude', [claude_message('A', None), claude_message('C', 'A')],
                  native_version='fixture-v1', leaf_id='C')
    first = read_source(spec, max_events=1)
    second = read_source(spec, cursor=first['cursor'])
    assert first['events'] == second['events'] == []
    assert not first['coverage']['complete'] and not second['coverage']['complete']
