"""Run only the actual frozen Raman child from independently generated input evidence.
Never reads Wu evaluation or the teacher's reference answer.
"""
import argparse
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.v19_child_scope import child_workspace
from app.pipeline_v19 import wrapper
from app.v19_codex_transport import run_codex_v19
from app.pipeline_store import atomic_json,fingerprint

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--run',action='store_true');a=p.parse_args()
    a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=False)
    prior=ROOT/'backend/storage/pipelines/3a90af73-833f-4ef2-ac03-2778dd4d25e7'
    state=json.loads((prior/'pipeline.json').read_text(encoding='utf-8'))
    def stage(name):
        rec=state['stages'][name];value=json.loads((prior/rec['output']).read_text(encoding='utf-8'))
        if rec['status']!='succeeded' or fingerprint(value)!=rec['output_hash']:raise ValueError('上游底稿不完整或已被修改')
        return value
    delivery=json.loads((ROOT.parent/'9.23/双层影响力工具_v19_交付包_20260923_0735/系统运行版/backend/workspace_snapshots/P02.json').read_text(encoding='utf-8'))
    routes={'D1':['E1','E2','E3','E5','E6','E8','NEW-RAM-003'],
            'D2':['E5','E7','IMP-E036','NEW-PRE-001','NEW-GH-001'],
            'D3':['IMP-E036','SEARCH-RAM'],'D4':['NEW-GH-001','SEARCH-RAM'],
            'D5':['E1','E2','E3','E4','E7','SEARCH-RAM'],'D6':[],
            'D7':['NEW-MED-001','SEARCH-RAM']}
    workspace=child_workspace(delivery,stage('wu_intake'),stage('search_replay')['replay'],stage('attribution'),child_id='ACH-002',routes=routes,
        review_note='依据冻结清单ACH-002新型拉曼探针与报告物理350/367/369页两种探针及筛选验证记录，仅评探针形成和研发应用；不包含MAIN-003其他子成果。所引OCNet资料只能支持基础模型背景，不能迁移为探针独立影响。D6无主线接入证据。')
    atomic_json(a.output/'workspace.json',workspace);atomic_json(a.output/'routes.json',routes)
    engine=wrapper();check=engine.inspect_workspace(a.output/'workspace.json');atomic_json(a.output/'preflight.json',check)
    print(json.dumps(check,ensure_ascii=False),flush=True)
    if a.run:
        if not check['formal_input_ready']:raise SystemExit('Input gate failed')
        run_codex_v19(workspace,a.output/'artifacts',engine)
        print('Raman child v19 run completed and validated.',flush=True)
