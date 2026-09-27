import copy
import pytest
from app.evaluation_coordination import CoordinatedReport,validate_coordination
from test_teacher_integration import modern_assessment


def candidate():
    return CoordinatedReport.model_validate({'assessment':modern_assessment(),
        'review_items':[{'field':'D6','action':'retained','reason':'合作研发没有证明产品被实际持续调用','evidence_ids':['P1']}],
        'quality':{'fluent':True,'understandable':True,'actionable':True,'evidence_faithful':True,
            'revision_notes':'将抽象的协作表述改为具体产品使用与研发方法的区别'}})


def test_coordination_requires_coverage_frozen_facts_and_quality():
    original={'assessment':candidate().assessment.model_dump()}
    differences=[{'field':'D6'}]
    validate_coordination(candidate(),original,differences,{'P1'})
    for mutation in ('omission','foreign_source','fact_change','quality_fail','card_change'):
        response=candidate()
        if mutation=='omission':response.review_items=[]
        if mutation=='foreign_source':response.review_items[0].evidence_ids=['OTHER']
        if mutation=='fact_change':response.assessment.fact_ledger.impact_facts[0].fact_text='新增作用'
        if mutation=='card_change':response.assessment.outcome_card[0].value='不同成果'
        if mutation=='quality_fail':response.quality.actionable=False
        with pytest.raises(ValueError):validate_coordination(response,original,differences,{'P1'})


def test_omitted_registry_is_restored_without_changing_judgment(tmp_path):
    from app.evaluation_coordination import normalize_coordination
    raw=candidate().model_dump();original=copy.deepcopy(raw['assessment'])
    raw['assessment']['evidence_index']=[]
    response=normalize_coordination(raw,{'management_draft':original,'fact_ledger':original['fact_ledger']},tmp_path)
    assert response.assessment.model_dump()==original
    assert response.review_items[0].action=='retained'


def test_export_delivers_coordinated_report_and_preserves_draft(tmp_path,monkeypatch):
    import json
    from app.pipeline_v19 import export_stage
    from app.skill_loader import contract
    from app.evaluation_runtime import CURRENT
    assessment=candidate().assessment.model_dump()
    common={'project_id':'P','outcome_id':'O','grading_standard':CURRENT,'rubric_version':contract.RUBRIC_VERSION,'rubric_id':'fixture'}
    draft={**common,'assessment':assessment}
    dimensions={**common,'result':{'outcomes':[{'outcome_id':'O','dimensions':[
        {'dimension_id':f'D{i}','grade':{'level':None,'assessment_state':'insufficient_evidence','reason':'材料不足'}} for i in range(1,8)],
        'synthesis':{'impact_level':{'level':'L1'}}}]}}
    final=copy.deepcopy(draft);final['assessment'].update(current_level=None,level_name=None,attainment_fact_ids=[])
    monkeypatch.setattr('app.evaluation_coordination.coordinate_report',lambda *args:(final,{'status':'completed'}))
    result=export_stage({}, {'wu_evaluation':draft,'v19_evaluation':dimensions},tmp_path)
    assert result['management_final']['assessment']['current_level'] is None
    assert json.loads((tmp_path/'wu-evaluation.json').read_text(encoding='utf-8'))['assessment']['current_level']==1
    assert json.loads((tmp_path/'unified-evaluation.json').read_text(encoding='utf-8'))['current_level'] is None


def test_finalization_is_used_for_delivery_and_cannot_silently_fall_back(monkeypatch,tmp_path):
    from types import SimpleNamespace
    from app import project_service as service
    from app.pipeline_store import PipelineStore,atomic_json
    store=PipelineStore(tmp_path/'job');store.create({})
    state=store.read();state['stages']['export']['status']='succeeded';atomic_json(store.path,state)
    monkeypatch.setattr(service,'job_directory',lambda _:store.root)
    outputs={'export':{'management_final':{'assessment':{'current_level':1}}},'wu_evaluation':{'assessment':{'current_level':2}}}
    monkeypatch.setattr(service,'stage_output',lambda _,name:outputs[name])
    assert service.final_management(SimpleNamespace(id='job'))['assessment']['current_level']==1
    outputs['export']={}
    with pytest.raises(ValueError):service.final_management(SimpleNamespace(id='job'))


def test_one_expert_cannot_overwrite_anothers_objection(admin_client,monkeypatch):
    from app.db import Session
    from app.models import ReviewDecision,User
    from sqlalchemy import select
    from test_teacher_integration import review_report
    _,rid=review_report(admin_client)
    url='/api/reports/'+rid
    assert admin_client.post(url+'/reviewers',json={'revision':1,'username':'admin'}).status_code==200
    with Session() as db:
        other=User(username='other-reviewer',password_hash='unused',role='user');db.add(other);db.flush()
        db.add(ReviewDecision(result_id=rid,result_revision=1,sequence=1,user_id=other.id,fact_id='fact-1',verdict='conflict',reason='该记录不足以确认真实使用',evidence_ids=['P1']));db.commit()
    monkeypatch.setattr('app.project_api.report_comparison',lambda _: {'blocking_disagreement':False,'complete':True})
    body={'revision':1,'fact_id':'fact-1','verdict':'confirmed','reason':'另一位专家认为可确认','evidence_ids':['P1']}
    assert admin_client.post(url+'/decisions',json=body).status_code==201
    assert admin_client.post(url+'/decisions',json={**body,'fact_id':'__overall__'}).status_code==409


def test_subcall_reuse_requires_exact_input_and_valid_sources(tmp_path,monkeypatch):
    import json
    from app import v19_codex_transport as transport
    calls=[]
    def execute(*args,**kwargs):
        calls.append(args[2])
        return transport.ModelReply(result_json='{"answer": "saved"}')
    monkeypatch.setattr(transport,'execute_json_stage',execute)
    first=transport.CodexV19Client(tmp_path/'first')
    assert first.chat_json('rule','{}').ok
    second=transport.CodexV19Client(tmp_path/'second',cache_roots=[tmp_path/'first'])
    assert second.chat_json('rule','{}').ok and len(calls)==1
    assert second.chat_json('changed rule','{}').ok and len(calls)==2
    (tmp_path/'first/call-001/parsed-result.json').write_text('{"source_ids":["invented"]}',encoding='utf-8')
    third=transport.CodexV19Client(tmp_path/'third',cache_roots=[tmp_path/'first'])
    assert third.chat_json('rule','{}').ok and len(calls)==3


def test_preview_is_project_bound_and_preserves_exact_quote(admin_client):
    from uuid import uuid4
    from app.db import Session
    from app.models import Material,Result
    from app.models import User
    from sqlalchemy import select
    from test_teacher_integration import review_report
    from test_project_workflow import user_client
    p,rid=review_report(admin_client);mid=str(uuid4())
    with Session() as db:
        admin_id=db.scalar(select(User.id).where(User.username=='admin'))
        db.add(Material(id=mid,project_id=p['id'],filename='原件.txt',storage_key='not-used',size=100,
            text='前文。精确原文。后文。',uploaded_by=admin_id,use_in_workflow=1))
        row=db.get(Result,rid);row.payload={**row.payload,'evidence':[{'id':'P1','title':'原件','material_id':mid,'excerpt':'精确原文。'}]};db.commit()
    url='/api/reports/'+rid
    preview=admin_client.get(url+'/evidence/P1/context')
    assert preview.status_code==200 and preview.json()['quote']=='精确原文。'
    assert preview.json()['before']=='前文。' and preview.json()['after']=='后文。'
    with Session() as db:
        db.get(Material,mid).text='前文。精确\n原文。后文。';db.commit()
    located=admin_client.get(url+'/evidence/P1/context').json()
    assert located['match_mode']=='whitespace_only' and located['matched_text']=='精确\n原文。'
    assert located['quote']=='精确原文。'
    with Session() as db:
        db.get(Material,mid).text='前文。不同原文。后文。';db.commit()
    assert not admin_client.get(url+'/evidence/P1/context').json()['matched']
    snapshot=admin_client.get(url+'/reevaluation-preview').json()
    assert snapshot['expected_inputs']['material_ids']==[mid]
    response=admin_client.post(url+'/reevaluate',json={'revision':1,'request_key':str(uuid4()),
        'change_reason':'additional_evidence','expected_inputs':{'material_ids':[],'search_boundary':None}})
    assert response.status_code==409 and '预览' in response.json()['detail']
    with user_client('preview-outsider') as outsider:
        assert outsider.get(url+'/evidence/P1/context').status_code==404
        assert outsider.get(url+'/reevaluation-preview').status_code==404
