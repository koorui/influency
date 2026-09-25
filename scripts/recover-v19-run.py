"""Re-run original v19 orchestration, reusing only verified identical model requests."""
import argparse
import json
from pathlib import Path
import shutil
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.pipeline_v19 import wrapper
from app.v19_codex_transport import run_codex_v19
from app.pipeline_store import atomic_json,fingerprint,implementation_fingerprint,timestamp

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True);p.add_argument('--cache-calls',type=Path,action='append',default=[]);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    folder=a.output.resolve();folder.mkdir(parents=True,exist_ok=False)
    workspace=json.loads(a.workspace.read_text(encoding='utf-8'));engine=wrapper()
    shutil.copyfile(a.workspace,folder/'workspace.json')
    inspection=engine.inspect_workspace(folder/'workspace.json');atomic_json(folder/'preflight.json',inspection)
    if not inspection['formal_input_ready']:raise ValueError('v19工作区未通过输入检查')
    journal={'status':'running','started_at':timestamp(),'workspace_source':str(a.workspace.resolve()),'workspace_hash':fingerprint(workspace),
        'implementation_fingerprint':implementation_fingerprint(),'cache_roots':[str(p.resolve()) for p in a.cache_calls],
        'boundary':'只复用相同请求且原始响应/解析结果一致、来源编号通过核验的调用；不复用输入变化后的综合判断。'}
    atomic_json(folder/'recovery.json',journal)
    try:
        result=run_codex_v19(workspace,folder/'artifacts',engine,cache_roots=a.cache_calls)
        value={'rubric_id':'outcome-d1-d7-evaluation.v19','project_id':workspace['project_profile']['project_id'],
            'outcome_id':workspace['pipeline_provenance']['local_outcome_id'],'workspace_hash':fingerprint(workspace),
            'result':result,'execution_mode':'verified_same_input_recovery','upstream_lineage':workspace['pipeline_provenance']}
        atomic_json(folder/'output.json',value);journal.update(status='succeeded',finished_at=timestamp(),output_hash=fingerprint(value));atomic_json(folder/'recovery.json',journal)
        print('v19 recovery completed and validated.',flush=True)
    except Exception as exc:
        journal.update(status='failed',finished_at=timestamp(),error=str(exc));atomic_json(folder/'recovery.json',journal);raise
