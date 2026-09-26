import pytest
from app.pipeline_contracts import Comparison


def comparison(**changes):
    return dict(id='C1',name='耗时对照',baseline={'label':'原流程','value':100,'unit':'秒'},
                observed={'label':'新流程','value':60,'unit':'秒'},direction='lower_is_better',
                comparability_status='partial',evidence_ids=['P1'],involved_factor_ids=['AI','equipment'],
                isolated_factor_ids=[],notes='数据和设备同时变化，不能分离AI贡献',**changes)


def test_combined_effect_preserves_nonisolated_comparison():
    value=Comparison.model_validate(comparison())
    assert value.isolated_factor_ids==[]
    assert value.observed.value==60


@pytest.mark.parametrize('field,value', [('evidence_ids',[]),('isolated_factor_ids',['AI','equipment']),
                                      ('isolated_factor_ids',['unknown']),
                                      ('observed',{'label':'新流程','value':1,'unit':'分钟'})])
def test_unjustified_independent_attribution_is_rejected(field,value):
    payload=comparison();payload[field]=value
    with pytest.raises(ValueError):Comparison.model_validate(payload)
