"""Submit a deliberately insufficient-context live stage check; never auto-publish."""
from pathlib import Path
import json
import re
import httpx

root=Path(__file__).resolve().parents[1]
state=root/'backend/storage/pipeline-live-smoke.json'
if __name__=='__main__':
    with httpx.Client(base_url='http://localhost:5173',trust_env=False,timeout=30) as c:
        password=re.search(r'Password: (.+)',(root/'.local-access.md').read_text(encoding='utf-8')).group(1).strip()
        c.post('/api/auth/login',json={'username':'admin','password':password}).raise_for_status()
        if state.exists():
            id=json.loads(state.read_text(encoding='utf-8'))['id']
            response=c.get('/api/admin/pipelines/'+id);response.raise_for_status()
            result=response.json()
            print(json.dumps({k:result[k] for k in ['id','status','error','stages']},ensure_ascii=False,indent=2))
        else:
            material=c.post('/api/admin/materials',files={'file':('pipeline-connectivity.txt','本文件仅用于接口连通性检查。没有提供科研项目编号、成果描述、实验数据或比较基线，不能作为正式成果评价依据。'.encode())})
            material.raise_for_status()
            response=c.post('/api/admin/pipelines',json={'title':'工作流连通性检查（非科研评价）','project_id':'PIPELINE-SMOKE','project_name':'接口测试上下文','outcome_id':'UNRESOLVED','material_ids':[material.json()['id']]})
            response.raise_for_status();state.parent.mkdir(parents=True,exist_ok=True);state.write_text(json.dumps(response.json(),ensure_ascii=False),encoding='utf-8')
            print('Queued pipeline:',response.json()['id'])
