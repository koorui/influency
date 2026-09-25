"""Real stage transformations and DCA/v19 engines; only model transports are replaced.
Nothing in this test constitutes an actual evaluation of a project.
"""
import importlib.util
import json
from pathlib import Path
from app.pipeline_service import run_pipeline
from app.pipeline_store import PipelineStore
from app.pipeline_contracts import WuIntake
from app.skill_loader import contract
from test_codex_adapter import fixture_assessment,material


def test_full_pipeline_separates_results_and_runs_original_engines(tmp_path,monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings(),'v19_transport','provider')
    source=Path(__file__).resolve().parents[3]/'9.23/双层影响力工具_v19_交付包_20260923_0735/系统运行版/backend/workspace_snapshots/P02.json'
    workspace=json.loads(source.read_text(encoding='utf-8'))
    frozen=workspace['evaluation_framework']['outcome_cards'][0]
    assessment=fixture_assessment()
    intake={'status':'ready','project_name':'测试项目','canonical_name':'示例探针','confidence':'high',
            'candidates':[{'name':'示例探针','scope':'已冻结范围','evidence_ids':['P1','P2']}],
            'outcome_card':assessment['outcome_card'],
            'evidence':[{'id':e['id'],'material_id':e['material_id'],'locator':e['locator'],'quote':e['quote']} for e in assessment['evidence_index']],
            'factors':[{'id':'AI','name':'AI参与因素','type':'ai','role':'仅测试','role_in_attribution':'target','evaluate_independent_increment':True}],
            'comparisons':[],'claims':[{'id':'C1','text':'项目声称AI参与','factor_id':'AI','evidence_ids':['P1']}],'gaps':['缺少隔离实验']}
    search={'schema_version':'search-replay.v1','project_id':'P02','outcome_id':frozen['outcome_id'],'mode':'historical_replay','original_run_id':'offline-test','original_completed_at':'2026-09-23','source_label':'合成接口测试，不代表实际检索','evidence':[],'findings':[]}
    inputs={'project_id':'P02','project_name':'测试项目','outcome_id':frozen['outcome_id'],'title':'示例探针','materials':material(),
            'search_replay':search,'v19_workspace':workspace,'v19_scope_mapping':{'outcome_id':frozen['outcome_id'],'canonical_name':'示例探针','reviewed':True}}
    phases=[]
    def model(folder,cls,payload,instruction,**kwargs):
        phases.append(folder.parent.name)
        if cls is WuIntake:return cls.model_validate(intake)
        assert payload['search_replay']['fresh_search_executed'] is False
        assert payload['attribution']['engine']=='dca-integration/1.1.0'
        return cls.model_validate(assessment)
    monkeypatch.setattr('app.pipeline_stages.execute_json_stage',model)
    # Execute original v19 pipeline with a deterministic no-network model fixture.
    import app.pipeline_v19 as v19
    actual_wrapper=v19.wrapper()
    fixture_script=Path(__file__).resolve().parents[2]/'scripts/verify-v19-skill.py'
    spec=importlib.util.spec_from_file_location('v19_offline_fixture',fixture_script)
    fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
    def engine_run(args):
        w=json.loads(args.workspace.read_text(encoding='utf-8'))
        assert 'wu-v2-six-levels' not in json.dumps(w)
        result=fixture.IndicatorEvaluationPipeline(fixture.OfflineClient.settings,fixture.OfflineClient()).run(w,model='offline-test-only',parallelism=2)
        assert result['run']['completed_call_count']==9
        assert actual_wrapper.validate_result(result)['valid']
        args.output_dir.mkdir()
        (args.output_dir/'evaluation-run.json').write_text(json.dumps(result,ensure_ascii=False),encoding='utf-8')
        return 0
    actual_wrapper.run=engine_run
    monkeypatch.setattr(v19,'wrapper',lambda:actual_wrapper)
    for key in ['V19_API_KEY','V19_BASE_URL','V19_MODEL']:monkeypatch.setenv(key,'offline-test-no-provider')
    store=PipelineStore(tmp_path/'pipeline');store.create(inputs)
    state=run_pipeline(store.root)
    assert state['status']=='succeeded'
    assert phases==['wu_intake','wu_evaluation']
    final=store.root/'export/attempt-1'
    wu=json.loads((final/'wu-evaluation.json').read_text(encoding='utf-8'))
    double=json.loads((final/'v19-evaluation.json').read_text(encoding='utf-8'))
    assert wu['assessment']['current_level']==1
    assert double['result']['outcomes'][0]['synthesis']['impact_level']['level']=='待确认'
    assert double['result']['llm_trace']['summary']['provider_request_count']==0
    assert wu['rubric_id']!=double['rubric_id']
    assert not json.loads((final/'manifest.json').read_text(encoding='utf-8'))['published']
    assert run_pipeline(store.root)['status']=='succeeded'
    assert len(phases)==2
