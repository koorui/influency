from pathlib import Path
import pytest
from app.pipeline_worker import run_once
from app.pipeline_store import PipelineStore,WaitingForInput,STAGES
from app.pipeline_api import directory


def create_job(admin_client):
    upload=admin_client.post('/api/admin/materials',files={'file':('pipeline.txt','测试项目：成果验证材料。'.encode())})
    assert upload.status_code==201
    response=admin_client.post('/api/admin/pipelines',json={'title':'工作流测试成果','project_id':'P02','project_name':'测试项目','outcome_id':'MAIN-001','material_ids':[upload.json()['id']]})
    assert response.status_code==201,response.text
    return response.json()


def test_pipeline_admin_queue_wait_amend_resume_and_download(admin_client,client,monkeypatch):
    assert client.get('/api/admin/pipelines').status_code==401
    assert client.post('/api/admin/pipelines',json={}).status_code==401
    job=create_job(admin_client)
    calls=[]
    def runner(root):
        def intake(inputs,outputs,folder):
            calls.append('intake')
            if not inputs.get('confirmed_scope'):raise WaitingForInput('请选择成果',{'candidates':['A','B']})
            return {'canonical_name':inputs['confirmed_scope']}
        return PipelineStore(root).execute({name:intake if name=='wu_intake' else lambda *args:{'ok':True} for name in STAGES})
    monkeypatch.setattr('app.pipeline_worker.run_pipeline',runner)
    assert run_once()
    detail=admin_client.get(f"/api/admin/pipelines/{job['id']}").json()
    assert detail['status']=='waiting'
    assert detail['waiting']['wu_intake']['details']['candidates']==['A','B']
    assert admin_client.patch(f"/api/admin/pipelines/{job['id']}",json={'revision':1,'confirmed_scope':'A'}).status_code==409
    changed=admin_client.patch(f"/api/admin/pipelines/{job['id']}",json={'revision':detail['revision'],'confirmed_scope':'A'})
    assert changed.status_code==200,changed.text
    assert run_once()
    done=admin_client.get(f"/api/admin/pipelines/{job['id']}").json()
    assert done['status']=='succeeded'
    assert done['stages']['wu_intake']['attempts']==2
    assert len(done['amendments'])==1
    assert admin_client.get(f"/api/admin/pipelines/{job['id']}/artifact",params={'path':'export/attempt-1/output.json'}).status_code==200
    table=directory(job['id'])/'report.csv';table.write_text('证据ID,状态\nE1,待核验\n',encoding='utf-8-sig')
    assert admin_client.get(f"/api/admin/pipelines/{job['id']}/artifact",params={'path':'report.csv'}).status_code==200
    assert any(f['path']=='report.csv' for f in admin_client.get(f"/api/admin/pipelines/{job['id']}").json()['files'])
    assert admin_client.get(f"/api/admin/pipelines/{job['id']}/artifact",params={'path':'../../../../.env'}).status_code==404
    assert client.get(f"/api/admin/pipelines/{job['id']}/artifact",params={'path':'pipeline.json'}).status_code==401


def test_running_pipeline_cannot_be_edited(admin_client):
    job=create_job(admin_client)
    assert admin_client.patch(f"/api/admin/pipelines/{job['id']}",json={'revision':job['revision'],'confirmed_scope':'changed'}).status_code==409


def test_cross_project_delivery_rejected_before_queue(admin_client):
    upload=admin_client.post('/api/admin/materials',files={'file':('test.txt',b'test')}).json()
    body={'title':'测试','project_id':'P02','project_name':'测试','outcome_id':'MAIN-001','material_ids':[upload['id']],
          'v19_workspace':{'schema_version':'indicator-workspace.v6','project_profile':{'project_id':'P01'}}}
    response=admin_client.post('/api/admin/pipelines',json=body)
    assert response.status_code==422


def test_scope_controls_read_verified_sources_and_upstream_change_invalidates_review(admin_client):
    from app.db import Session
    from app.models import PipelineJob
    from app.pipeline_store import atomic_json,fingerprint
    material=admin_client.post('/api/admin/materials',files={'file':('source.txt','原始试验记录。'.encode())}).json()
    mapping={'outcome_id':'LOCAL-A','canonical_name':'测试成果','reviewed':True,'frozen_child_id':'CHILD-A','evidence_routes':{'D1':['E1']},'review_note':'只评子成果'}
    workspace={'schema_version':'indicator-workspace.v6','project_profile':{'project_id':'P02'},
        'step3_frozen_outcomes':{'outcomes':[{'outcome_id':'MAIN-A','title':'父成果','child_outcomes':[{'outcome_id':'CHILD-A','title':'子成果'}]}]}}
    response=admin_client.post('/api/admin/pipelines',json={'title':'测试成果','project_id':'P02','project_name':'测试项目','outcome_id':'LOCAL-A',
        'material_ids':[material['id']],'v19_workspace':workspace,'v19_scope_mapping':mapping})
    assert response.status_code==201,response.text
    identifier=response.json()['id'];store=PipelineStore(directory(identifier));state=store.read()
    folder=store.root/'wu_intake/attempt-1';folder.mkdir(parents=True)
    output={'intake':{'canonical_name':'测试成果','evidence':[{'id':'E1','locator':'第1页','quote':'原始试验记录。'}]}}
    atomic_json(folder/'output.json',output)
    state['stages']['wu_intake']={'status':'succeeded','attempts':1,'output':'wu_intake/attempt-1/output.json','output_hash':fingerprint(output)}
    state['status']='waiting';atomic_json(store.path,state)
    with Session() as db:
        row=db.get(PipelineJob,identifier);row.status='waiting';db.commit()
    detail=admin_client.get(f'/api/admin/pipelines/{identifier}').json()
    assert detail['scope_options'][0]['id']=='CHILD-A'
    assert detail['scope_evidence'][0]['quote']=='原始试验记录。'
    amended=admin_client.patch(f'/api/admin/pipelines/{identifier}',json={'revision':detail['revision'],'search_mode':'live',
        'search_boundary':{'project_start_date':'2025-06-01','review_cutoff':'2026-04-30','cutoff_basis':'原报告统计日'}})
    assert amended.status_code==200,amended.text
    assert store.read()['inputs']['v19_scope_mapping']['reviewed'] is False
