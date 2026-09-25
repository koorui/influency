from uuid import uuid4
from app.db import Session
from app.models import Material, OutcomeSubmission


def form(**extra):
    value = {'request_key':str(uuid4()),'project_name':'有机化学项目','outcome_name':'测试拉曼分子',
             'outcome_type':'分子','description':'具体分子探针，用于实验测量与验证。','ai_involved':True,
             'ai_role':'候选分子筛选','organizations':'测试大学：实验验证','members':'测试成员：合成与测量'}
    value.update(extra)
    return value


def register(client, name='researcher'):
    result=client.post('/api/auth/register',json={'username':name,'password':'test-password-123'})
    assert result.status_code==201,result.text


def test_submit_material_ownership_idempotency_and_admin_handoff(client,admin_client):
    assert client.post('/api/submissions',json=form()).status_code==401
    register(client)
    uploaded=client.post('/api/submission-materials/batch',files=[('files',('experiment.txt','实测结果：91±5。'.encode()))])
    assert uploaded.status_code==207,uploaded.text
    material=uploaded.json()['accepted'][0]
    payload=form(material_ids=[material['id']])
    response=client.post('/api/submissions',json=payload)
    assert response.status_code==201,response.text
    submission=response.json()
    repeat=client.post('/api/submissions',json=payload)
    assert repeat.json()['id']==submission['id']
    assert client.post('/api/submissions',json={**payload,'description':'改变内容不能复用同一提交编号。'}).status_code==409
    ticket=submission['ticket_id']
    assert client.get('/api/tickets').json()[0]['id']==ticket
    assert admin_client.get(f'/api/admin/submissions/{ticket}').json()['material_ids']==submission['material_ids']
    assert len(submission['material_ids'])==2
    with Session() as db:
        generated=db.get(Material,submission['material_ids'][0])
        assert '项目方填写' in generated.text and payload['ai_role'] in generated.text
    client.post('/api/auth/logout')
    register(client,'another-researcher')
    assert client.get(f'/api/submissions/{ticket}').status_code==404
    assert client.post('/api/submissions',json=form(material_ids=[material['id']])).status_code==403
    assert client.get(f'/api/admin/submissions/{ticket}').status_code==403


def test_form_validation_keeps_insufficient_evidence_honest(client):
    register(client)
    assert client.post('/api/submissions',json=form(ai_role='')).status_code==422
    assert client.post('/api/submissions',json=form(project_name=' ')).status_code==422
    assert client.post('/api/submissions',json=form(review_cutoff='2025-01-01',project_start_date='2026-01-01',cutoff_basis='report')).status_code==422
    # Unknown dates and no external validation are permitted as a pending submission, never an evaluation.
    response=client.post('/api/submissions',json=form(ai_involved=False,ai_role=''))
    assert response.status_code==201,response.text
    assert client.get('/api/tickets').json()[0]['status']=='pending'


def test_submission_can_enter_full_pipeline_once(client,admin_client,monkeypatch):
    from app.pipeline_worker import run_once
    register(client)
    submission=client.post('/api/submissions',json=form()).json()
    payload={'title':'测试拉曼分子','project_id':'P-test','project_name':'有机化学项目','outcome_id':'A-test',
             'ticket_id':submission['ticket_id'],'material_ids':submission['material_ids']}
    created=admin_client.post('/api/admin/pipelines',json=payload)
    assert created.status_code==201,created.text
    assert created.json()['ticket_id']==submission['ticket_id']
    assert client.get('/api/tickets').json()[0]['status']=='processing'
    assert admin_client.post('/api/admin/pipelines',json=payload).status_code==409
    monkeypatch.setattr('app.pipeline_worker.run_pipeline',lambda root:{'status':'waiting','stages':{'search_replay':{'status':'waiting','error':'需确认评审日'}}})
    assert run_once()
    assert '补充材料或确认范围' in client.get('/api/tickets').json()[0]['note']
