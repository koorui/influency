import json
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from app.main import app
from app.db import Session
from app.models import User, Project, Material, PipelineJob, Result, ResultVersion
from app.pipeline_store import PipelineStore, STAGES
from app.project_service import job_directory
from test_codex_adapter import fixture_assessment


def create_project(admin_client,name='化学项目',code='CHEM'):
    response=admin_client.post('/api/admin/projects',json={'name':name,'code':code,
        'search_boundary':{'project_start_date':'2025-06-01','review_cutoff':'2026-04-30','cutoff_basis':'项目阶段记录'}})
    assert response.status_code==201,response.text
    return response.json()


def user_client(name):
    client=TestClient(app)
    assert client.post('/api/auth/register',json={'username':name,'password':'project-test-password'}).status_code==201
    return client


def submit(client,p,**kwargs):
    return client.post('/api/requests',json={'project_id':p['id'],'outcome_name':'自定义成果',
        'request_key':str(uuid4()),'description':'',**kwargs})


def completed_outputs():
    assessment=fixture_assessment()
    for d in assessment['dimensions']:d['grade']='G1'
    return {'wu_intake':{'intake':{}},'search_replay':{'replay':{}},'attribution':{},
        'wu_evaluation':{'assessment':assessment},
        'v19_evaluation':{'result':{'schema_version':'indicator-evaluation.run.v5','formal':True,
            'run':{'standard_version':'outcome-d1-d7-evaluation.v19','expected_call_count':9,'completed_call_count':9},
            'outcomes':[{'outcome_id':'ONE','title':'示例探针','dimensions':[{'dimension_id':f'D{i}','grade':{'level':'G1'}} for i in range(1,8)],
                         'synthesis':{'impact_level':{'level':'L1'}}}],
            'project_synthesis':{'scope_impact_level':{'level':'L1'}}}},'export':{'completed':True,'management_final':{'assessment':assessment}}}


def test_project_code_is_required_and_rotation_revokes_access(admin_client):
    p=create_project(admin_client);other=create_project(admin_client,'另一个项目','OTHER')
    with user_client('member') as c:
        assert c.get('/api/projects').json()==[]
        assert submit(c,p).status_code==404
        assert c.get('/api/reports?project_id='+p['id']).status_code==404
        assert c.post('/api/projects/unlock',json={'code':p['access_code']}).status_code==200
        assert [v['id'] for v in c.get('/api/projects').json()]==[p['id']]
        assert 'access_secret' not in json.dumps(c.get('/api/projects').json())
        assert submit(c,other).status_code==404
        for path in ('/api/admin/projects','/api/admin/requests','/api/admin/materials/anything'):
            assert c.get(path).status_code==403
        rotated=admin_client.post('/api/admin/projects/'+p['id']+'/access-code').json()['access_code']
        assert c.get('/api/projects').json()==[]
        assert submit(c,p).status_code==404
        assert c.post('/api/projects/unlock',json={'code':p['access_code']}).status_code==400
        assert c.post('/api/projects/unlock',json={'code':rotated}).status_code==200


def test_ticket_runs_full_workflow_and_shares_completed_report_only_inside_project(admin_client,monkeypatch):
    p=create_project(admin_client)
    with Session() as db:
        admin=db.scalar(select(User).where(User.username=='admin'))
        db.add(Material(id='material-1',project_id=p['id'],filename='original.txt',storage_key='project-test.txt',
            size=12,text='项目原始材料',uploaded_by=admin.id,use_in_workflow=1));db.commit()
    with user_client('applicant') as applicant,user_client('colleague') as colleague,user_client('outsider') as outsider:
        for c in (applicant,colleague):assert c.post('/api/projects/unlock',json={'code':p['access_code']}).status_code==200
        key=str(uuid4());one=submit(applicant,p,request_key=key);assert one.status_code==201,one.text
        two=submit(applicant,p,request_key=key);assert two.json()['id']==one.json()['id']
        assert submit(applicant,p,request_key=key,outcome_name='不同成果').status_code==409
        assert len(applicant.get('/api/requests').json())==1
        assert colleague.get('/api/requests').json()==[]
        assert applicant.get('/api/reports').json()==[]
        job_id=one.json()['pipeline_id'];snapshot=PipelineStore(job_directory(job_id)).read()['inputs']
        assert [m['id'] for m in snapshot['materials']]==['material-1']
        assert snapshot['search_mode']=='live' and snapshot['automatic_workspace'] is True
        def execute(root):
            outputs=completed_outputs()
            return PipelineStore(root).execute({name:(lambda i,o,f,n=name:outputs[n]) for name in STAGES})
        monkeypatch.setattr('app.pipeline_worker.run_pipeline',execute)
        from app.pipeline_worker import run_once
        assert not run_once()
        assert one.json()['status']=='pending_acceptance'
        assert admin_client.post('/api/admin/requests/'+one.json()['id']+'/receive',json={'revision':1}).status_code==200
        assert run_once()
        ticket=applicant.get('/api/requests').json()[0]
        assert ticket['status']=='awaiting_acceptance' and all(s['status']=='succeeded' for s in ticket['steps'])
        identifier=ticket['result_id'];assert identifier
        assert len(colleague.get('/api/reports').json())==1
        assert colleague.get('/api/reports/'+identifier).json()['v19']['formal'] is True
        assert outsider.get('/api/reports').json()==[]
        assert outsider.get('/api/reports/'+identifier).status_code==404
        assert outsider.get('/api/results/'+identifier).status_code==404
        assert colleague.post('/api/requests/'+ticket['id']+'/accept-report').status_code==404
        assert colleague.get('/api/reports/'+identifier).json()['can_accept'] is False
        assert applicant.get('/api/reports/'+identifier).json()['can_accept'] is True
        accepted=applicant.post('/api/requests/'+ticket['id']+'/accept-report')
        assert accepted.status_code==200 and accepted.json()['status']=='accepted'
        assert applicant.post('/api/requests/'+ticket['id']+'/accept-report').json()['accepted_at']==accepted.json()['accepted_at']
        assert not run_once()
        with Session() as db:assert db.scalar(select(func.count()).select_from(ResultVersion))==1


def test_failed_stage_never_delivers_a_partial_report(admin_client,monkeypatch):
    p=create_project(admin_client)
    with user_client('failure_case') as c:
        c.post('/api/projects/unlock',json={'code':p['access_code']})
        one=submit(c,p);assert one.status_code==201
        assert admin_client.post('/api/admin/requests/'+one.json()['id']+'/receive',json={'revision':1}).status_code==200
        def execute(root):
            def fail(*args):raise RuntimeError('external service failed')
            return PipelineStore(root).execute({'wu_intake':lambda *a:{},'search_replay':fail})
        monkeypatch.setattr('app.pipeline_worker.run_pipeline',execute)
        from app.pipeline_worker import run_once
        assert run_once()
        ticket=c.get('/api/requests').json()[0]
        assert ticket['status']=='failed' and ticket['result_id'] is None
        assert c.get('/api/reports').json()==[]
        assert ticket['steps'][0]['status']=='succeeded' and ticket['steps'][1]['status']=='failed'


def test_code_rate_limit_and_retired_entry_points(admin_client):
    with user_client('code_attempts') as c:
        for _ in range(5):assert c.post('/api/projects/unlock',json={'code':'wrong'}).status_code==400
        assert c.post('/api/projects/unlock',json={'code':'wrong'}).status_code==429
    for path in ('/api/admin/tasks','/api/submissions','/api/search','/api/admin/pipelines'):
        assert admin_client.post(path,json={}).status_code in (404,405)


def test_projects_cannot_select_another_projects_material(admin_client):
    p=create_project(admin_client);other=create_project(admin_client,'第二项目','SECOND')
    response=admin_client.post('/api/admin/projects/'+p['id']+'/materials',files={'files':('original.txt','原始证据'.encode(),'text/plain')})
    assert response.status_code==207,response.text
    material=response.json()['accepted'][0]['id']
    assert admin_client.get('/api/admin/projects/'+other['id']+'/materials').json()==[]
    assert admin_client.patch(f"/api/admin/projects/{other['id']}/materials/{material}",json={'use_in_workflow':True}).status_code==404


def test_current_card_can_prepare_v19_without_historical_evaluation(tmp_path,monkeypatch):
    from app.pipeline_workspace import current_workspace,EvidenceRoutes
    from app.pipeline_v19 import wrapper
    from app.pipeline_store import atomic_json
    def route(*args,**kwargs):return EvidenceRoutes(D1=['E1'],D2=[],D3=[],D4=[],D5=[],D6=[],D7=[],explanation='仅原始专业事实')
    monkeypatch.setattr('app.pipeline_workspace.execute_json_stage',route)
    scope={'project_id':'P','outcome_id':'NEW','intake':{'canonical_name':'新成果','outcome_card':[]},
        'attribution_preparation':{'evidence':[{'id':'E1','text':'新成果的原始事实','locator':'第1页'}]}}
    replay={'project_id':'P','outcome_id':'NEW','mode':'live_search','evidence':[]}
    outputs={'wu_intake':scope,'search_replay':{'replay':replay},'attribution':{'contribution_result':{},'unresolved_items':{}}}
    workspace=current_workspace({'project_name':'新项目','search_boundary':{}},outputs,tmp_path)
    atomic_json(tmp_path/'workspace.json',workspace)
    assert wrapper().inspect_workspace(tmp_path/'workspace.json')['formal_input_ready']
    assert workspace['evaluation_framework']['outcome_cards'][0]['outcome_id']=='NEW'
    assert workspace['pipeline_provenance']['wu_evaluation_used'] is False
