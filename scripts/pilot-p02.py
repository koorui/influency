"""Submit a real Codex draft pilot from supplied P02 ledger excerpts, not invented material.
This never publishes and does not treat upstream ledger summaries as original project documents.
"""
import hashlib
import json
import re
from pathlib import Path
import httpx

root=Path(__file__).resolve().parents[1]
source=root.parent/'9.23/双层影响力工具_v19_交付包_20260923_0735/系统运行版/backend/workspace_snapshots/P02.json'
state=root/'backend/storage/pilot-p02.json'

if __name__=='__main__':
    access=(root/'.local-access.md').read_text(encoding='utf-8')
    password=re.search(r'Password: (.+)',access).group(1).strip()
    with httpx.Client(base_url='http://localhost:5173',trust_env=False,timeout=60) as client:
        client.post('/api/auth/login',json={'username':'admin','password':password}).raise_for_status()
        if state.exists():
            saved=json.loads(state.read_text(encoding='utf-8'))
            rows=client.get('/api/admin/tasks').json()
            task=next((r for r in rows if r['id']==saved['task_id']),None)
            if task:
                print(json.dumps({k:task[k] for k in ['id','status','error','attempts']},ensure_ascii=False))
                raise SystemExit(0)
        workspace=json.loads(source.read_text(encoding='utf-8'))
        excerpts=[]
        def walk(value,path):
            if isinstance(value,dict):
                for k,v in value.items():
                    if isinstance(v,str) and ('拉曼' in v or 'Raman' in v) and len(v)<10000:
                        excerpts.append({'json_path':path+'/'+k,'value':v})
                    else:walk(v,path+'/'+k)
            elif isinstance(value,list):
                for i,v in enumerate(value):walk(v,path+f'/{i}')
        walk(workspace['project_materials'],'/project_materials')
        if not excerpts:raise SystemExit('No matching supplied material; no task created')
        digest=hashlib.sha256(source.read_bytes()).hexdigest()
        text=('项目：人工智能赋能有机化学，交付包编号 P02。\n'
              '本材料是用户提供的v19工作区上游台账摘录，不是项目原始PDF。以下内容按JSON路径逐字提取；它只能证明台账如何记载，不能替代原始材料或独立核验。'
              '原件不随摘录提供，对其缺口必须如实说明。不得导入台账中的历史等级。\n'
              f'来源：{source.name}；SHA256：{digest}\n\n'+json.dumps(excerpts,ensure_ascii=False,indent=2))
        if len(text)>100000:raise SystemExit('Pilot material too large; inspect scope first')
        material=client.post('/api/admin/materials',files={'file':('P02-raman-ledger-excerpts.md',text.encode('utf-8'),'text/markdown')})
        material.raise_for_status()
        task=client.post('/api/admin/tasks',json={'title':'拉曼探针','keywords':['拉曼探针','拉曼','P02'],'material_ids':[material.json()['id']],'adapter':'codex','project_context':'P02：人工智能赋能有机化学','confirmed_scope':''})
        task.raise_for_status()
        record={'task_id':task.json()['id'],'material_id':material.json()['id'],'source_sha256':digest,'excerpt_count':len(excerpts),'text_characters':len(text)}
        state.parent.mkdir(parents=True,exist_ok=True);state.write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps(record,ensure_ascii=False))
