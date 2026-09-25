import json
from app.db import Session
from app.models import Task, Result
from app.worker import run_once
from app.codex_adapter import CodexAdapter, to_report
from app.skill_loader import contract
from test_codex_adapter import fixture_assessment


def test_admin_codex_queue_dossier_and_scope_publish_gate(admin_client,monkeypatch):
    data=fixture_assessment()
    data.update(evaluation_status='needs_scope_confirmation',current_level=None,level_name=None,upgrade_plus_1=None,upgrade_plus_2=None)
    data['outcome_resolution']['resolution_confidence']='medium'
    def evaluate(self,title,keywords,materials,**context):
        assert context['project_context']=='测试项目'
        assert context['confirmed_scope']==''
        for ev in data['evidence_index']:ev['material_id']=materials[0]['id']
        self.raw_output=json.dumps(data,ensure_ascii=False)
        return to_report(contract.Assessment.model_validate(data),keywords)
    monkeypatch.setattr(CodexAdapter,'evaluate',evaluate)
    monkeypatch.setattr('app.codex_adapter.codex_command',lambda:['codex'])
    upload=admin_client.post('/api/admin/materials',files={'file':('test.txt','示例探针完成光谱验证。示例探针属于测试项目。'.encode())}).json()
    created=admin_client.post('/api/admin/tasks',json={'title':'示例探针','keywords':['示例'],'material_ids':[upload['id']],'adapter':'codex','project_context':'测试项目'})
    assert created.status_code==201,created.text
    assert run_once()
    with Session() as db:
        task=db.get(Task,created.json()['id'])
        assert task.status=='succeeded'
        assert json.loads(task.raw_output)['outcome_card']
    row=admin_client.get('/api/admin/results').json()[0]
    assert row['payload']['level'] is None
    assert admin_client.post(f"/api/admin/results/{row['id']}/publish",json={'revision':1}).status_code==409
    # Editing the display payload cannot bypass a pending-scope decision in the original dossier.
    row['payload']['evaluation_status']='preliminary'
    edited=admin_client.put(f"/api/admin/results/{row['id']}",json={'revision':1,'payload':row['payload']})
    assert edited.status_code==200
    assert admin_client.post(f"/api/admin/results/{row['id']}/publish",json={'revision':2}).status_code==409
