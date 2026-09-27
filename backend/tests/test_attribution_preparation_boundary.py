import pytest
from app.pipeline_contracts import Comparison, AttributionPreparation, SearchReplay, attribution_input


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


def legacy_handoff(value):
    prep=AttributionPreparation.model_validate({
        'schema_version':'attribution-preparation.v1','project_id':'P','project_name':'Project',
        'outcome_id':'O','outcome_name':'Outcome',
        'evidence':[{'id':'P1','project_id':'P','outcome_id':'O','source_type':'project','locator':'p1','text':'Evidence'}],
        'factors':[{'id':'AI','name':'AI'},{'id':'equipment','name':'Equipment'}],
        'comparisons':[value],'claims':[]})
    replay=SearchReplay.model_validate({'schema_version':'search-replay.v1','project_id':'P','outcome_id':'O',
        'mode':'historical_replay','original_run_id':'test','original_completed_at':'2026-09-26',
        'source_label':'test','evidence':[],'findings':[]})
    return attribution_input(prep,replay)


@pytest.mark.parametrize('observed_unit',[None,'seconds'])
def test_legacy_optional_fields_survive_handoff_and_real_engine(tmp_path,observed_unit):
    import json
    payload=comparison();payload.pop('notes')
    payload['baseline']={'value':100}
    payload['observed']={'value':60}
    if observed_unit:payload['observed']['unit']=observed_unit
    payload['source_context']={'page':1}
    handed=legacy_handoff(payload)
    assert handed['comparisons']==[payload]  # No invented labels/units or dropped metadata.
    import importlib,sys
    from pathlib import Path
    runtime=Path(__file__).resolve().parents[2]/'skills/data-purification-ai-attribution/runtime'
    sys.path.insert(0,str(runtime))
    try:
        engine=importlib.import_module('dca_integration')
        input_path=tmp_path/'input.json';input_path.write_text(json.dumps(handed),encoding='utf-8')
        engine.run_attribution(str(input_path),str(tmp_path/'output'))
        result=json.loads((tmp_path/'output/contribution_result.json').read_text(encoding='utf-8'))
        assert all(f['status']!='direct_increment_supported' for f in result['factor_results'])
    finally:sys.path.remove(str(runtime))
    with pytest.raises(ValueError):Comparison.model_validate(payload)


@pytest.mark.parametrize('field,value', [('evidence_ids',[]),('isolated_factor_ids',['AI','equipment']),
    ('isolated_factor_ids',['unknown']),('observed',{'value':1,'unit':'minutes'}),
    ('baseline',{'value':float('nan'),'unit':'秒'})])
def test_legacy_handoff_still_rejects_invalid_comparisons(field,value):
    payload=comparison();payload.pop('notes');payload[field]=value
    with pytest.raises(ValueError):legacy_handoff(payload)
