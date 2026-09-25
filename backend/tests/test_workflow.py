import io
from datetime import timedelta
from concurrent.futures import ThreadPoolExecutor
from fastapi.testclient import TestClient
from sqlalchemy import select
from docx import Document
from app.main import app
from app.db import Session
from app.models import Task, Result, now
from app.worker import run_once


def upload(admin_client, filename='evidence.txt', content='科研材料。独立用户验证与应用情况。'.encode()):
    r = admin_client.post('/api/admin/materials', files={'file': (filename, content)})
    assert r.status_code == 201, r.text
    return r.json()['id']


def task(admin_client, material_id, ticket_id=None):
    r = admin_client.post('/api/admin/tasks', json={'title': '量子拉曼探针', 'keywords': ['拉曼探针', '量子检测'], 'material_ids': [material_id], 'ticket_id': ticket_id})
    assert r.status_code == 201, r.text
    return r.json()['id']


def test_search_ticket_evaluate_review_publish_withdraw(client, admin_client):
    miss = admin_client.post('/api/admin/search', json={'query': '量子拉曼探针'}).json()
    ticket_id = miss['ticket']['id']
    assert admin_client.post('/api/admin/search', json={'query': '  量子拉曼探针  '}).json()['ticket']['id'] == ticket_id
    with TestClient(app) as other:
        assert other.get('/api/tickets').json() == []
    assert client.get('/api/admin/results').status_code == 401
    material_id = upload(admin_client)
    task_id = task(admin_client, material_id, ticket_id)
    assert run_once()
    rows = admin_client.get('/api/admin/results').json()
    assert len(rows) == 1
    result = rows[0]
    assert result['payload']['is_demo'] is True
    assert result['payload']['level'] is None
    assert result['payload']['evidence'][0]['material_id'] == material_id
    assert client.get('/api/results/' + result['id']).status_code == 404
    assert admin_client.get('/api/tickets').json()[0]['status'] == 'review'
    result['payload']['summary'] = '管理员已审阅的演示摘要。'
    saved = admin_client.put('/api/admin/results/' + result['id'], json={'revision': 1, 'payload': result['payload']})
    assert saved.status_code == 200, saved.text
    assert admin_client.put('/api/admin/results/' + result['id'], json={'revision': 1, 'payload': result['payload']}).status_code == 409
    published = admin_client.post(f"/api/admin/results/{result['id']}/publish", json={'revision': 2})
    assert published.status_code == 200
    found = admin_client.post('/api/admin/search', json={'query': '量子检测'}).json()
    assert found['results'][0]['payload']['summary'] == '管理员已审阅的演示摘要。'
    assert admin_client.get('/api/tickets').json()[0]['result_id'] == result['id']
    assert len(admin_client.get(f"/api/admin/results/{result['id']}/versions").json()) == 3
    assert admin_client.post(f"/api/admin/tasks/{task_id}/retry").status_code == 409
    assert admin_client.post(f"/api/admin/results/{result['id']}/withdraw", json={'revision': 3}).status_code == 200
    assert client.get('/api/results/' + result['id']).status_code == 404
    assert admin_client.get('/api/tickets').json()[0]['status'] == 'review'
    assert len(admin_client.get('/api/admin/audit').json()) >= 5


def test_auth_and_origin(client, admin_client):
    assert client.post('/api/auth/register', json={'username': 'member', 'password': 'member-password-123', 'role': 'admin'}).status_code == 422
    assert client.post('/api/auth/register', json={'username': 'member', 'password': 'member-password-123'}).status_code == 201
    assert client.get('/api/admin/tickets').status_code == 403
    assert client.post('/api/admin/tasks').status_code == 403
    assert client.post('/api/auth/logout', headers={'Origin': 'https://untrusted.invalid'}).status_code == 403
    assert client.post('/api/auth/login', json={'username': 'admin', 'password': 'wrong-password'}).status_code == 401
    assert admin_client.post('/api/auth/logout').status_code == 200
    assert admin_client.get('/api/admin/results').status_code == 401


def test_validation_and_material_access(client, admin_client):
    assert admin_client.post('/api/admin/search', json={'query': '   '}).status_code == 422
    assert admin_client.post('/api/admin/materials', files={'file': ('bad.exe', b'executable')}).status_code == 422
    assert admin_client.post('/api/admin/materials', files={'file': ('empty.txt', b'  ')}).status_code == 422
    assert admin_client.post('/api/admin/materials', files={'file': ('bad.pdf', b'not a pdf')}).status_code == 422
    doc = Document(); doc.add_paragraph('文档内容'); stream = io.BytesIO(); doc.save(stream)
    mid = upload(admin_client, 'doc.docx', stream.getvalue())
    assert '文档内容' in admin_client.get(f'/api/admin/materials/{mid}').json()['text']
    assert client.get(f'/api/admin/materials/{mid}/download').status_code == 401
    assert admin_client.get(f'/api/admin/materials/{mid}/download').content == stream.getvalue()
    task(admin_client, mid); run_once()
    row = admin_client.get('/api/admin/results').json()[0]
    row['payload']['dimensions'][0]['evidence_ids'] = ['missing-evidence']
    assert admin_client.put(f"/api/admin/results/{row['id']}", json={'revision': 1, 'payload': row['payload']}).status_code == 422
    row['payload']['dimensions'][0]['evidence_ids'] = ['E1']
    row['payload']['is_demo'] = False
    assert admin_client.put(f"/api/admin/results/{row['id']}", json={'revision': 1, 'payload': row['payload']}).status_code == 422


def test_failure_retry_and_expired_lease(admin_client):
    mid = upload(admin_client)
    tid = task(admin_client, mid)
    with Session() as db:
        row = db.get(Task, tid); row.adapter = 'not-installed'; db.commit()
    run_once()
    row = admin_client.get('/api/admin/tasks').json()[0]
    assert row['status'] == 'failed'
    assert row['error']
    with Session() as db:
        row = db.get(Task, tid); row.adapter = 'mock'; db.commit()
    assert admin_client.post(f'/api/admin/tasks/{tid}/retry').status_code == 200
    run_once()
    assert admin_client.get('/api/admin/tasks').json()[0]['attempts'] == 2
    second = task(admin_client, mid)
    with Session() as db:
        row = db.get(Task, second); row.status = 'running'; row.started_at = now() - timedelta(hours=1); db.commit()
    run_once()
    with Session() as db:
        assert db.get(Task, second).status == 'failed'


def test_two_workers_do_not_duplicate_result(admin_client):
    tid = task(admin_client, upload(admin_client))
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(run_once) for _ in range(2)]
        for f in futures:
            f.result()
    with Session() as db:
        assert len(list(db.scalars(select(Result).where(Result.task_id == tid)))) == 1
        assert db.get(Task, tid).attempts == 1


def test_search_wildcards_are_literal(client, admin_client):
    task(admin_client, upload(admin_client)); run_once()
    row = admin_client.get('/api/admin/results').json()[0]
    admin_client.post(f"/api/admin/results/{row['id']}/publish", json={'revision':1})
    assert admin_client.post('/api/admin/search', json={'query':'%'}).json()['results'] == []
    assert admin_client.post('/api/admin/search', json={'query':'_'}).json()['results'] == []
