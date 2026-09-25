"""Real DCA -> Wu -> v19 -> export using a verified current Search collection.
No teacher assessment or historical Search conclusion is admitted as source evidence.
"""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.pipeline_store import atomic_json,fingerprint,implementation_fingerprint,timestamp
from app.pipeline_stages import attribution_stage,wu_evaluation_stage
from app.pipeline_v19 import v19_evaluation_stage,export_stage

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--search',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    folder=a.output.resolve();folder.mkdir(parents=True,exist_ok=False)
    prior=ROOT/'backend/storage/pipelines/3a90af73-833f-4ef2-ac03-2778dd4d25e7'
    state=json.loads((prior/'pipeline.json').read_text(encoding='utf-8'))
    record=state['stages']['wu_intake'];intake=json.loads((prior/record['output']).read_text(encoding='utf-8'))
    if fingerprint(intake)!=record['output_hash']:raise ValueError('成果定位底稿发生变化')
    search=json.loads((a.search.resolve()/'output.json').read_text(encoding='utf-8'))
    if search['replay']['mode']!='live_search' or fingerprint(search['replay'])!=search['source_hash']:raise ValueError('Search不是校验后的本轮采集')
    if search['replay']['project_id']!=intake['project_id'] or search['replay']['outcome_id']!=intake['outcome_id']:raise ValueError('成果范围不匹配')
    inputs={k:v for k,v in state['inputs'].items() if k not in ('search_replay','v19_workspace','v19_scope_mapping')}
    inputs['search_mode']='live'
    inputs['v19_workspace']=json.loads((ROOT.parent/'9.23/双层影响力工具_v19_交付包_20260923_0735/系统运行版/backend/workspace_snapshots/P02.json').read_text(encoding='utf-8'))
    inputs['v19_scope_mapping']={'outcome_id':intake['outcome_id'],'canonical_name':intake['intake']['canonical_name'],'reviewed':True,'frozen_child_id':'ACH-002',
        'evidence_routes':{'D1':['E1','E2','E3','E5','E6','E8'],'D2':['E5','E7'],'D3':[],'D4':[],'D5':['E1','E2','E3','E4','E7'],'D6':[],'D7':[]},
        'review_note':'仅评冻结子成果ACH-002累积五烯探针及报告中的两轮筛选验证，不包含MAIN-003其他成果。新Search暂无通过完整日期审计的正式外部证据；不得沿用历史Search证据、结论或旧评测等级。D3/D4/D6/D7不猜测外部部署、复现、主线接入和传播。'}
    outputs={'wu_intake':intake,'search_replay':search}
    atomic_json(folder/'inputs.json',inputs);atomic_json(folder/'upstream.json',outputs)
    journal={'status':'running','started_at':timestamp(),'implementation_fingerprint':implementation_fingerprint(),'intake_source':str(prior/record['output']),
        'search_source':str(a.search.resolve()),'search_collection_reused':True,'stages':{}}
    atomic_json(folder/'test-run.json',journal)
    for name,executor in [('attribution',attribution_stage),('wu_evaluation',wu_evaluation_stage),('v19_evaluation',v19_evaluation_stage),('export',export_stage)]:
        stage=folder/name;stage.mkdir()
        journal['stages'][name]={'status':'running','started_at':timestamp()};atomic_json(folder/'test-run.json',journal)
        print(name+': started',flush=True)
        try:
            value=executor(inputs,outputs,stage);outputs[name]=value;atomic_json(stage/'output.json',value)
            journal['stages'][name].update(status='succeeded',finished_at=timestamp(),output_hash=fingerprint(value))
            atomic_json(folder/'test-run.json',journal);print(name+': succeeded',flush=True)
        except Exception as exc:
            journal['status']='failed';journal['stages'][name].update(status='failed',error=str(exc),finished_at=timestamp())
            atomic_json(folder/'test-run.json',journal);raise
    journal.update(status='succeeded',finished_at=timestamp());atomic_json(folder/'test-run.json',journal)
