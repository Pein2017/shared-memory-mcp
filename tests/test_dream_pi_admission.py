"""Legacy frozen branch labels cannot substitute for a structural proof."""
import pytest
from dreaming_helpers import begin, claim, environment, record_op, view_op


@pytest.mark.parametrize('operation', [record_op, view_op])
def test_legacy_pi_frozen_branch_cannot_publish(tmp_path, operation):
    engine, store, *_ = environment(tmp_path)
    rid, gen, key, _ = begin(engine)
    # Model the pre-fix persisted public projection: a selected suffix had a
    # branch label but no proof of complete ancestry.
    with store._gate():
        run = engine._run(rid, gen)
        event = run['materials']['owner']['events'][0]
        event.update(harness='pi', branch='selected-leaf', evidence='report')
        event.pop('ancestry_verified', None)
        engine._save(run)
    c = claim(key, level='report')
    frozen = engine.freeze(rid, gen, [operation('legacy', c)])
    result = engine.publish(rid, gen, frozen['draft_revision'])
    assert result['status'] == 'blocked', result
    assert result['unresolved'][0]['code'] == 'unverified_branch'
    assert not list((store.root / 'records/demo').glob('*.md'))
    assert not (store.root / 'dreaming/views/demo/research/current.json').exists()
