from pathlib import Path
from unittest.mock import Mock
import pytest
from sqlalchemy import select, func
from app.db import Session
from app.models import (Material, PipelineJob, Ticket, Result, ResultVersion, QueryRecord,
                        OutcomeSubmission, Project, ProjectMember)
from app.config import settings
from app.project_service import job_directory
from app.project_deletion import commit_with_files
from test_project_workflow import create_project, user_client, submit


def upload(admin, project, name='source.txt'):
    r=admin.post('/api/admin/projects/'+project['id']+'/materials',files={'files':(name,b'original project evidence','text/plain')})
    assert r.status_code==207,r.text
    identifier=r.json()['accepted'][0]['id']
    with Session() as db:path=Path(settings().storage_dir)/db.get(Material,identifier).storage_key
    return identifier,path


def test_delete_material_checks_role_project_and_workflow_references(admin_client):
    p=create_project(admin_client);other=create_project(admin_client,'Other','OTHER')
    mid,path=upload(admin_client,p)
    with user_client('delete_user') as user:
        user.post('/api/projects/unlock',json={'code':p['access_code']})
        endpoint=f"/api/admin/projects/{p['id']}/materials/{mid}"
        assert user.delete(endpoint).status_code==403
        assert admin_client.delete(f"/api/admin/projects/{other['id']}/materials/{mid}").status_code==404
        request=submit(user,p).json()
        assert user.post('/api/admin/requests/'+request['id']+'/receive',json={'revision':1}).status_code==403
        assert user.post('/api/requests/'+request['id']+'/accept-report').status_code==409
        assert admin_client.delete(endpoint).status_code==409
        assert path.is_file()
        assert admin_client.delete('/api/admin/requests/'+request['id']).status_code==200
        assert not job_directory(request['pipeline_id']).exists()
        assert path.is_file()
        assert user.get('/api/requests').json()==[]
        assert admin_client.delete(endpoint).status_code==200
        assert not path.exists()


def test_delete_project_cascades_completed_records_but_refuses_running(admin_client):
    p=create_project(admin_client);other=create_project(admin_client,'Keep','KEEP')
    mid,path=upload(admin_client,p);other_mid,other_path=upload(admin_client,other)
    with user_client('project_delete_user') as user:
        user.post('/api/projects/unlock',json={'code':p['access_code']})
        ticket=submit(user,p).json()
        endpoint='/api/admin/projects/'+p['id']
        assert user.delete(endpoint).status_code==403
        with Session() as db:
            job=db.get(PipelineJob,ticket['pipeline_id']);job.status='running';db.commit()
        assert admin_client.delete(endpoint).status_code==409
        assert path.is_file()
        with Session() as db:
            job=db.get(PipelineJob,ticket['pipeline_id']);job.status='succeeded'
            result=Result(project_id=p['id'],pipeline_id=job.id,title='report',search_text='report',payload={},status='published')
            db.add(result);db.flush()
            db.add(ResultVersion(result_id=result.id,revision=1,payload={},editor='workflow'))
            db.add(QueryRecord(owner='user',result_id=result.id,result_revision=1,project_title='p',task_type='view',detail='',prompt_version='',prompt=''))
            db.get(Ticket,ticket['id']).result_id=result.id;db.commit()
        r=admin_client.delete(endpoint)
        assert r.status_code==200,r.text
        assert r.json()['reports']==1 and r.json()['materials']==1
        assert not path.exists() and not job_directory(ticket['pipeline_id']).exists()
        assert other_path.is_file()
        with Session() as db:
            assert db.get(Project,p['id']) is None and db.get(Project,other['id'])
            for model in (Ticket,PipelineJob,OutcomeSubmission,Result,ResultVersion,QueryRecord,ProjectMember):
                assert db.scalar(select(func.count()).select_from(model))==0
            assert db.get(Material,other_mid)
        assert user.get('/api/projects').json()==[]


def test_file_staging_rolls_back_on_database_commit_failure(tmp_path,monkeypatch):
    import app.project_deletion as module
    monkeypatch.setattr(module,'settings',lambda:Mock(storage_dir=str(tmp_path)))
    file=tmp_path/'original.txt';file.write_text('keep')
    db=Mock();db.commit.side_effect=RuntimeError('commit failed')
    with pytest.raises(RuntimeError):commit_with_files(db,['original.txt'])
    assert file.read_text()=='keep'
    db.rollback.assert_called_once()
    with pytest.raises(ValueError):commit_with_files(Mock(),['../outside'])
