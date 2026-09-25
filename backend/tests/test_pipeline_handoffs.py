import json
from pathlib import Path
import pytest
from app.pipeline_contracts import SearchReplay,AttributionPreparation,attribution_input
from app.pipeline_stages import attribution_stage,search_replay_stage
from app.pipeline_store import WaitingForInput


def inputs():
    fixture=Path(__file__).resolve().parents[3]/'9.23/数据提纯与AI贡献归因_代码包_20260923/examples/attribution/input.json'
    data=json.loads(fixture.read_text(encoding='utf-8'))
    project=data['project']['id'];outcome=data['target']['id']
    scoped=lambda e:{**e,'project_id':project,'outcome_id':outcome,'url':None}
    prep={'schema_version':'attribution-preparation.v1','project_id':project,'project_name':data['project']['name'],'outcome_id':outcome,'outcome_name':data['target']['name'],
          'evidence':[scoped(e) for e in data['evidence'] if e['source_type']=='project'],**{k:data[k] for k in ['factors','comparisons','claims']}}
    replay={'schema_version':'search-replay.v1','project_id':project,'outcome_id':outcome,'mode':'historical_replay','original_run_id':'test-fixture-only','original_completed_at':'2026-09-23','source_label':'归因包回归夹具，非新检索',
            'evidence':[scoped(e) for e in data['evidence'] if e['source_type']=='search'],
            'findings':[{k:f[k] for k in ['id','status','statement','reason','related_claim_ids','evidence_ids']} for f in data['search_findings']]}
    return prep,replay


def test_search_and_real_dca_preserve_identity_and_replay(tmp_path):
    prep,replay=inputs()
    scope={k:prep[k] for k in ['project_id','outcome_id']};scope['attribution_preparation']=prep
    outputs={'wu_intake':scope}
    outputs['search_replay']=search_replay_stage({'search_replay':replay},outputs,tmp_path)
    assert outputs['search_replay']['fresh_search_executed'] is False
    result=attribution_stage({},outputs,tmp_path)
    assert result['project_id']==prep['project_id']
    assert result['search_mode']=='historical_replay'
    assert result['contribution_result'] and result['unresolved_items']
    assert (tmp_path/'artifacts/AI贡献归因结果.html').exists()


def test_cross_project_replay_and_conflicting_ids_rejected():
    prep,replay=inputs()
    replay['project_id']='wrong'
    with pytest.raises(ValueError):SearchReplay.model_validate(replay)
    prep,replay=inputs();replay['outcome_id']='wrong'
    for e in replay['evidence']:e['outcome_id']='wrong'
    with pytest.raises(ValueError,match='对象'):
        attribution_input(AttributionPreparation.model_validate(prep),SearchReplay.model_validate(replay))
    prep,replay=inputs();replay['findings'][0]['related_claim_ids']=['missing']
    with pytest.raises(ValueError,match='声明'):
        attribution_input(AttributionPreparation.model_validate(prep),SearchReplay.model_validate(replay))


def test_missing_search_waits_instead_of_fabricating(tmp_path):
    with pytest.raises(WaitingForInput):
        search_replay_stage({}, {'wu_intake':{'project_id':'P02','outcome_id':'A'}},tmp_path)
