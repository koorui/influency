"""Submit the prepared original-only case once, or inspect that same live job."""
import json
from pathlib import Path
import httpx

ROOT=Path(__file__).resolve().parents[1]
CASE=ROOT/'backend/storage/raman-case-source-v1'
STATE=CASE/'submitted-job.json'

if __name__=='__main__':
    with httpx.Client(base_url='http://127.0.0.1:8000',trust_env=False,timeout=120) as c:
        c.post('/api/auth/login',json={'username':'admin','password':'123456'}).raise_for_status()
        if STATE.exists():
            row=c.get('/api/admin/pipelines/'+json.loads(STATE.read_text(encoding='utf-8'))['id'])
            row.raise_for_status();d=row.json()
            print(json.dumps({'id':d['id'],'status':d['status'],'error':d['error'],'stages':d['stages']},ensure_ascii=False,indent=2))
        else:
            original=CASE/'project-original-pages.txt'
            r=c.post('/api/admin/materials',files={'file':(original.name,original.read_bytes(),'text/plain')})
            r.raise_for_status()
            body={'title':'累积五烯拉曼生物探针','project_id':'P02','project_name':'人工智能赋能有机化学（2025ZD0121900）',
                  'outcome_id':'RAMAN-CASE-001','material_ids':[r.json()['id']],
                  'confirmed_scope':'累积五烯拉曼生物探针',
                  'search_replay':json.loads((CASE/'search-replay.json').read_text(encoding='utf-8'))}
            response=c.post('/api/admin/pipelines',json=body);response.raise_for_status()
            STATE.write_text(json.dumps(response.json(),ensure_ascii=False,indent=2),encoding='utf-8')
            print('Created source-only Raman pipeline:',response.json()['id'])
