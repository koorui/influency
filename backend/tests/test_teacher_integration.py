import copy
from uuid import uuid4
import pytest
from sqlalchemy import select
from app.db import Session
from app.models import Result, User, ReviewDecision
from app.skill_loader import contract
from app.unified_evaluation import combine_evaluations
from test_codex_adapter import fixture_assessment
from test_project_workflow import create_project, user_client


def modern_assessment():
    v=fixture_assessment()
    v.update(schema_version='outcome-evaluation.v3',evaluation_status='system_preliminary',
        current_level=1,level_name=contract.LEVELS[0],upgrade_plus_1=None,upgrade_plus_2=None,
        stage_references=[],attainment_fact_ids=['fact-1'],boundary_fact_ids=['fact-2'])
    v['key_judgments']=[dict(topic=t,project_claim='项目陈述',assessment='核验边界',project_evidence_ids=['P1'],evaluation_evidence_ids=['P1']) for t in ('成果价值与先进性','AI与项目贡献','实际影响')]
    for d in v['dimensions']:d.update(grade=None,assessment_state='insufficient_evidence',conclusion='本轮证据不足')
    v['fact_ledger']={'schema_version':'outcome-facts.v1','project_id':'P','outcome_id':'O','primary_object_id':'probe',
        'evaluation_cutoff':'2026-04-30','claims':[],
        'impact_facts':[dict(id=f'fact-{i}',category=f'F{i}',object_id='probe',fact_text='形成验证' if i==1 else '本轮未发现该类作用',
            assessment_status='completed',state='verified' if i==1 else 'not_found_as_of_cutoff',
            evidence_ids=['P1'] if i==1 else [],counter_evidence_ids=[],event_date=None,
            time_basis='原始记录明确了阶段内验证',search_coverage='本轮送检材料',needs_expert_confirmation=False,notes='') for i in range(1,7)],
        'value_and_attribution':{k:dict(conclusion='未建立独立结论',evidence_ids=[],limitations=['材料不足']) for k in
            ('scientific_or_technical_value','project_additionality','ai_contribution','future_potential','management_action')}}
    return v


def test_missing_grade_is_legal_but_fabricated_g1_is_not():
    v=modern_assessment();a=contract.FinalAssessment.model_validate(v)
    contract.validate_completed_assessment(a)
    v['dimensions'][0]['grade']='G1'
    with pytest.raises(ValueError):contract.FinalAssessment.model_validate(v)
    v['dimensions'][0]['assessment_state']='assessed';v['dimensions'][0]['evidence_ids']=[]
    with pytest.raises(ValueError):contract.FinalAssessment.model_validate(v)


def test_unknown_l_and_fact_states_do_not_become_failure_or_false_absence():
    v=modern_assessment();v.update(current_level=None,level_name=None,attainment_fact_ids=[])
    contract.validate_completed_assessment(contract.FinalAssessment.model_validate(v))
    v['fact_ledger']['impact_facts'][1]['assessment_status']='pending'
    with pytest.raises(ValueError):contract.FinalAssessment.model_validate(v)
    v['fact_ledger']['impact_facts'][1]['state']=None
    contract.FinalAssessment.model_validate(v)


def test_model_cannot_sign_or_borrow_another_objects_facts():
    v=modern_assessment();v['evaluation_status']='formal'
    with pytest.raises(ValueError):contract.FinalAssessment.model_validate(v)
    v=modern_assessment();v['fact_ledger']['impact_facts'][0]['object_id']='method'
    with pytest.raises(ValueError):contract.FinalAssessment.model_validate(v)
    v=modern_assessment();v['attainment_fact_ids']=['fact-2']
    with pytest.raises(ValueError):contract.FinalAssessment.model_validate(v)


def test_null_dimension_completes_and_management_remains_authoritative():
    v=modern_assessment()
    common=dict(project_id='P',outcome_id='O',rubric_version=contract.RUBRIC_VERSION,grading_standard=contract.GRADING_VERSION)
    m={**common,'assessment':v}
    d={**common,'result':{'outcomes':[{'outcome_id':'O','dimensions':[
        {'dimension_id':f'D{i}','grade':{'level':None,'assessment_state':'insufficient_evidence','reason':'材料不足'}} for i in range(1,8)],
        'synthesis':{'impact_level':{'level':'L1'}}}]}}
    c=combine_evaluations(m,d);assert c['complete'] and c['current_level']=='L1'
    d['result']['outcomes'][0]['synthesis']['impact_level']['level']='L2'
    c=combine_evaluations(m,d);assert c['complete'] and c['current_level']=='L1' and not c['blocking_disagreement']
    assert c['differences'][0]['field']=='impact_level'
    m['assessment']['current_level']=None
    c=combine_evaluations(m,d);assert c['current_level'] is None and c['blocking_disagreement']


def review_report(admin_client):
    p=create_project(admin_client)
    with Session() as db:
        row=Result(project_id=p['id'],title='审阅成果',search_text='审阅成果',status='published',payload={
            'fact_ledger':modern_assessment()['fact_ledger'],
            'evidence':[{'id':'P1','title':'原始材料'}],
            'follow_ups':[{'title':'核对记录','kind':'material','body':'原始草稿','detail':'核对统计口径'}]})
        db.add(row);db.commit();return p,row.id


def test_review_requires_assignment_and_current_revision(admin_client,monkeypatch):
    p,rid=review_report(admin_client);url='/api/reports/'+rid
    body=dict(revision=1,fact_id='fact-1',verdict='confirmed',reason='原始验证支持此事实',evidence_ids=['P1'])
    assert admin_client.post(url+'/decisions',json=body).status_code==403
    assert admin_client.post(url+'/reviewers',json=dict(revision=1,username='admin')).status_code==200
    response=admin_client.post(url+'/decisions',json=body)
    assert response.status_code==201,response.text
    assert response.json()['adjudication_status']=='system_preliminary'
    assert admin_client.post(url+'/decisions',json={**body,'revision':2}).status_code==409
    assert admin_client.post(url+'/decisions',json={**body,'evidence_ids':['unknown']}).status_code==422
    monkeypatch.setattr('app.project_api.report_comparison',lambda job:{'blocking_disagreement':False,'complete':True})
    response=admin_client.post(url+'/decisions',json={**body,'fact_id':'__overall__'})
    assert response.status_code==201,response.text
    assert response.json()['adjudication_status']=='expert_confirmed'
    response=admin_client.post(url+'/decisions',json={**body,'verdict':'conflict'})
    assert response.json()['adjudication_status']=='system_preliminary'
    # A database with second-resolution timestamps must retain append order.
    from datetime import datetime
    with Session() as db:
        for entry in db.scalars(select(ReviewDecision).where(ReviewDecision.result_id==rid)):
            entry.created_at=datetime(2026,9,27,12,0,0)
        db.commit()
    review=admin_client.get(url+'/review').json()
    assert review['adjudication_status']=='system_preliminary'
    assert [d['sequence'] for d in review['decisions']]==[1,2,3]
    with user_client('review-outsider') as outsider:
        assert outsider.get(url+'/review').status_code==404


def test_draft_persists_and_stale_edits_do_not_overwrite(admin_client):
    _,rid=review_report(admin_client);url='/api/reports/'+rid
    task=admin_client.post(url+'/followups',json={'revision':1,'source_index':0}).json()
    assert admin_client.post(url+'/followups',json={'revision':1,'source_index':0}).json()['id']==task['id']
    edit=dict(result_revision=1,revision=1,body='编辑后的统一草稿',status='draft',deadline=None,resolution_refs=[])
    response=admin_client.post(url+'/followups/'+task['id'],json=edit)
    assert response.status_code==200,response.text
    assert admin_client.get(url+'/review').json()['tasks'][0]['body']==edit['body']
    assert admin_client.post(url+'/followups/'+task['id'],json=edit).status_code==409
    assert admin_client.post(url+'/followups/'+task['id'],json={**edit,'revision':2,'status':'resolved'}).status_code==422


def test_incomparable_units_remain_descriptive_without_blocking_intake():
    from app.pipeline_contracts import Comparison
    from test_evaluation_audit import comparison, engine
    from dca_integration.comparison import calculate_comparison
    raw=comparison(comparability_status='partial',comparison_kind='threshold_check',notes='计量口径未锁定')
    raw['observed']['unit']='条记录';raw['baseline']['unit']='条有效记录'
    Comparison.model_validate(raw)
    result=calculate_comparison(raw)
    assert result['effect_outcome']=='threshold_unresolved'
    assert result['absolute_difference'] is None and result['percent_change_from_baseline'] is None
    assert result['baseline_unit']!=result['observed_unit']
    raw['comparability_status']='established'
    with pytest.raises(ValueError):Comparison.model_validate(raw)


def test_citation_repair_keeps_bound_document_and_rejects_nonliteral_quote(tmp_path,monkeypatch):
    from app.citation_repair import repair_intake_citations, CitationRepair
    from app.pipeline_contracts import IntakeEvidence
    from types import SimpleNamespace
    class Candidate(SimpleNamespace):
        def model_copy(self,**kwargs):return copy.deepcopy(self)
    candidate=Candidate(canonical_name='探针',evidence=[IntakeEvidence(id='E1',material_id='M1',locator='旧定位',quote='第一句。第三句。')])
    materials=[{'id':'M1','filename':'原始.txt','text':'第一句。第二句。第三句。'}]
    fixed=CitationRepair(evidence=[IntakeEvidence(id='E1',material_id='M1',locator='第1行',quote=materials[0]['text'])])
    monkeypatch.setattr('app.citation_repair.execute_json_stage',lambda *a,**k:fixed)
    result=repair_intake_citations(candidate,materials,['E1'],tmp_path)
    assert result.evidence[0].quote==materials[0]['text']
    assert candidate.evidence[0].quote=='第一句。第三句。'
    for i,change in enumerate(({'material_id':'M2'},{'quote':'原文里没有这句话'})):
        next_dir=tmp_path/str(i);next_dir.mkdir()
        fixed.evidence[0]=fixed.evidence[0].model_copy(update=change)
        with pytest.raises(ValueError):repair_intake_citations(candidate,materials,['E1'],next_dir)


def test_reevaluation_is_idempotent_and_pins_primary_object(admin_client):
    from app.models import PipelineJob
    from app.pipeline_store import PipelineStore,atomic_json
    from app.project_service import job_directory
    p,rid=review_report(admin_client)
    with Session() as db:
        user=db.scalar(select(User).where(User.username=='admin'))
        job=PipelineJob(id=str(uuid4()),title='审阅成果',project_id=p['code'],project_ref=p['id'],outcome_id='OUT-fixed',created_by=user.id,status='succeeded')
        db.add(job);db.flush();row=db.get(Result,rid);row.pipeline_id=job.id
        store=PipelineStore(job_directory(job.id));state=store.create({'title':job.title})
        atomic_json(store.root/'intake.json',{'intake':{'canonical_name':'探针产品','primary_object_id':'probe','evaluation_objects':[
            {'id':'probe','name':'探针产品','kind':'product','version':'本期','relation_to_primary':'primary','evidence_ids':['P1']}]}})
        state['stages']['wu_intake'].update(status='succeeded',output='intake.json');atomic_json(store.path,state);db.commit()
    body=dict(revision=1,request_key=str(uuid4()),change_reason='additional_evidence',description='补充使用记录')
    response=admin_client.post('/api/reports/'+rid+'/reevaluate',json=body)
    assert response.status_code==201,response.text
    again=admin_client.post('/api/reports/'+rid+'/reevaluate',json=body)
    assert again.json()['id']==response.json()['id']
    state=PipelineStore(job_directory(response.json()['pipeline_id'])).read()
    assert state['inputs']['outcome_id']=='OUT-fixed'
    assert state['inputs']['frozen_primary_object']['id']=='probe'
    assert state['inputs']['supersedes_result_id']==rid
    assert response.json()['status']=='pending_acceptance'
    assert admin_client.post('/api/reports/'+rid+'/reevaluate',json={**body,'description':'另一个请求'}).status_code==409


def test_export_uses_saved_text_and_escapes_user_content(admin_client,monkeypatch):
    from app.codex_adapter import to_report
    _,rid=review_report(admin_client)
    value=to_report(contract.FinalAssessment.model_validate(modern_assessment()),['示例探针']).model_dump(mode='json')
    with Session() as db:
        row=db.get(Result,rid);row.payload={**value,'follow_ups':[{'title':'核验','kind':'material','detail':'原文','body':'原文'}]};db.commit()
    url='/api/reports/'+rid
    task=admin_client.post(url+'/followups',json={'revision':1,'source_index':0}).json()
    text='<script>alert(1)</script>已保存的新草稿'
    assert admin_client.post(url+'/followups/'+task['id'],json=dict(result_revision=1,revision=1,body=text,status='draft',deadline=None,resolution_refs=[])).status_code==200
    monkeypatch.setattr('app.project_api.report',lambda id,db,user:{'payload':{**db.get(Result,str(id)).payload,'adjudication_status':'system_preliminary'}})
    response=admin_client.get(url+'/export')
    assert response.status_code==200,response.text
    assert '&lt;script&gt;alert(1)&lt;/script&gt;已保存的新草稿' in response.text
    assert '<script>alert(1)</script>' not in response.text
    assert '系统初步判断' in response.text
    with user_client('export-outsider') as outsider:
        assert outsider.get(url+'/export').status_code==404


def test_unversioned_legacy_job_waits_instead_of_guessing_rules(tmp_path):
    from app.pipeline_store import PipelineStore,atomic_json,WaitingForInput
    from app.evaluation_runtime import dispatch_archived
    store=PipelineStore(tmp_path/'job');state=store.create({'title':'旧任务'})
    state['inputs'].pop('runtime_version');atomic_json(store.path,state)
    with pytest.raises(WaitingForInput,match='未记录运行版本'):dispatch_archived(store.root)


def test_reevaluation_cannot_silently_replace_primary_product_with_method(tmp_path):
    from app.pipeline_stages import finish_intake
    from app.pipeline_store import WaitingForInput
    from types import SimpleNamespace
    inputs={'frozen_primary_object':{'id':'probe','name':'探针','kind':'product','relation_to_primary':'primary'}}
    value=SimpleNamespace(primary_object_id='method',evaluation_objects=[SimpleNamespace(id='method',name='设计方法',kind='method')])
    with pytest.raises(WaitingForInput,match='改变了冻结主对象'):finish_intake(inputs,tmp_path,value)


def test_fact_reference_expansion_preserves_grades_and_frozen_ledger(tmp_path):
    from app.pipeline_model import expand_fact_citations
    raw=modern_assessment();raw['dimensions'][0]['evidence_ids']=['fact-1']
    value=expand_fact_citations(raw,{'fact_ledger':raw['fact_ledger']},tmp_path)
    assert value['dimensions'][0]['evidence_ids']==['P1']
    assert value['fact_ledger']==raw['fact_ledger']
    assert [d['grade'] for d in value['dimensions']]==[d['grade'] for d in raw['dimensions']]
    assert raw['dimensions'][0]['evidence_ids']==['fact-1']
    raw['dimensions'][0]['evidence_ids']=['invented']
    with pytest.raises(ValueError):contract.FinalAssessment.model_validate(expand_fact_citations(raw,{'fact_ledger':raw['fact_ledger']},tmp_path))


def test_associated_method_fact_is_archived_without_becoming_product_attainment(tmp_path):
    import json
    from app.pipeline_model import bind_fact_objects
    raw=modern_assessment()['fact_ledger']
    method={**raw['impact_facts'][0],'id':'method-use','category':'F2','object_id':'method','fact_text':'方法用于候选筛选'}
    raw['impact_facts'].append(method)
    payload={'intake':{'primary_object_id':'probe','evaluation_objects':[{'id':'probe'},{'id':'method'}],'evidence':[{'id':'P1'}]},'search_replay':{'replay':{'evidence':[]}}}
    value=bind_fact_objects(raw,payload,tmp_path)
    contract.FactLedger.model_validate(value)
    assert method not in value['impact_facts'] and method in raw['impact_facts']
    archived=json.loads((tmp_path/'associated-object-facts.json').read_text(encoding='utf-8'))
    assert archived['facts']==[method] and not archived['usable_as_primary_attainment']


def test_original_download_requires_project_and_report_binding(admin_client):
    from pathlib import Path
    from app.config import settings
    from app.models import Material
    p,rid=review_report(admin_client);mid=str(uuid4())
    root=Path(settings().storage_dir);root.mkdir(parents=True,exist_ok=True)
    (root/'private-source.txt').write_bytes(b'original source')
    with Session() as db:
        user=db.scalar(select(User).where(User.username=='admin'))
        db.add(Material(id=mid,project_id=p['id'],filename='private-source.txt',storage_key='private-source.txt',size=15,text='original source',uploaded_by=user.id))
        row=db.get(Result,rid);row.payload={**row.payload,'evidence':[{'id':'P1','material_id':mid,'title':'原始记录'}]};db.commit()
    url='/api/reports/'+rid+'/materials/'+mid
    assert admin_client.get(url).content==b'original source'
    assert admin_client.get('/api/reports/'+rid+'/materials/'+str(uuid4())).status_code==404
    with user_client('material-outsider') as outsider:assert outsider.get(url).status_code==404
    with Session() as db:
        material=db.get(Material,mid);material.storage_key='../outside.txt';db.commit()
    assert admin_client.get(url).status_code==404


def test_current_single_call_protocol_cannot_generate_legacy_formal():
    with pytest.raises(ValueError):contract.CurrentAssessment.model_validate(fixture_assessment())
    value=modern_assessment();value.update(evaluation_status='needs_scope_confirmation',current_level=None,level_name=None,fact_ledger=None,attainment_fact_ids=[],boundary_fact_ids=[],stage_references=[])
    assessment=contract.CurrentAssessment.model_validate(value)
    with pytest.raises(ValueError):contract.validate_completed_assessment(assessment)
