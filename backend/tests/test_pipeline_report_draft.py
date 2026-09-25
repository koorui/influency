import json
from app.models import PipelineJob,Material,User,uid
from app.db import Session
from app.pipeline_api import directory
from app.pipeline_store import PipelineStore,atomic_json,fingerprint
from sqlalchemy import select
from test_codex_adapter import fixture_assessment


def test_completed_wu_report_enters_review_once(admin_client,client):
    id=uid()
    with Session() as db:
        user=db.scalar(select(User).where(User.username=='admin'))
        db.add(Material(id='material-1',filename='original.txt',storage_key='original.txt',sha256='0'*64,size=60,text='示例探针完成光谱验证。\n示例探针属于测试项目。',uploaded_by=user.id))
        db.add(PipelineJob(id=id,title='报告测试',project_id='P02',outcome_id='A',created_by=user.id,status='waiting'));db.commit()
    store=PipelineStore(directory(id));state=store.create({'title':'报告测试'})
    folder=store.root/'wu_evaluation/attempt-1';folder.mkdir(parents=True)
    output={'assessment':fixture_assessment(),'rubric_id':'wu-v2-six-levels'}
    atomic_json(folder/'output.json',output)
    state['stages']['wu_evaluation']={'status':'succeeded','attempts':1,'output':'wu_evaluation/attempt-1/output.json','output_hash':fingerprint(output)}
    atomic_json(store.path,state)
    endpoint=f'/api/admin/pipeline-reports/{id}/draft'
    assert client.post(endpoint).status_code==401
    one=admin_client.post(endpoint);assert one.status_code==201,one.text
    two=admin_client.post(endpoint);assert two.json()['id']==one.json()['id']
    assert one.json()['status']=='draft'
    assert one.json()['pipeline_id']==id
    assert client.get('/api/results/'+one.json()['id']).status_code==404
    assert one.json()['payload']['rubric_id']=='wu-v2-six-levels'
    # A new model result must not be hidden by the idempotent import shortcut.
    changed={**output,'assessment':{**output['assessment'],'summary':'补证后重新生成的评价摘要。'}}
    second=store.root/'wu_evaluation/attempt-2';second.mkdir()
    atomic_json(second/'output.json',changed)
    state['stages']['wu_evaluation'].update(attempts=2,output='wu_evaluation/attempt-2/output.json',output_hash=fingerprint(changed))
    atomic_json(store.path,state)
    assert admin_client.post(f"/api/admin/results/{one.json()['id']}/publish",json={'revision':1}).status_code==409
    refreshed=admin_client.post(endpoint)
    assert refreshed.status_code==201,refreshed.text
    assert refreshed.json()['id']==one.json()['id'] and refreshed.json()['revision']==2
    assert refreshed.json()['payload']['summary']=='补证后重新生成的评价摘要。'
    assert admin_client.post(endpoint).json()['revision']==2
    versions=admin_client.get(f"/api/admin/results/{one.json()['id']}/versions").json()
    assert {v['revision'] for v in versions}=={1,2}
    published=admin_client.post(f"/api/admin/results/{one.json()['id']}/publish",json={'revision':2})
    assert published.status_code==200,published.text
    third=store.root/'wu_evaluation/attempt-3';third.mkdir()
    newer={**output,'assessment':{**output['assessment'],'summary':'第三次模型结果，尚未审核。'}}
    atomic_json(third/'output.json',newer)
    state['stages']['wu_evaluation'].update(attempts=3,output='wu_evaluation/attempt-3/output.json',output_hash=fingerprint(newer));atomic_json(store.path,state)
    assert admin_client.post(endpoint).status_code==409
    assert client.get('/api/results/'+one.json()['id']).json()['payload']['summary']=='补证后重新生成的评价摘要。'
