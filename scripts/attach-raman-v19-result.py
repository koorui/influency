"""Attach a verified, independently executed v19 tail to its originating pipeline.
Preserves original inputs, upstream stage hashes, rule versions, and earlier waiting record.
"""
import argparse
import json
import os
import shutil
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.pipeline_store import PipelineStore,atomic_json,fingerprint,timestamp,implementation_fingerprint
from app.pipeline_v19 import wrapper,export_stage
from app.db import Session
from app.models import PipelineJob,Audit,now
from sqlalchemy import select


def attach(pipeline_root,run_root):
    store=PipelineStore(pipeline_root)
    lock=store.root/'execution.lock'
    descriptor=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    os.write(descriptor,str(os.getpid()).encode());os.close(descriptor)
    try:
        state=store.read()
        if state['status']!='waiting' or state['stages']['v19_evaluation']['status']!='waiting':
            raise ValueError('只接受已经在v19阶段等待的原任务；不会覆盖成功结果或执行中流程')
        workspace=json.loads((run_root/'workspace.json').read_text(encoding='utf-8'))
        raw=json.loads((run_root/'artifacts/evaluation-run.json').read_text(encoding='utf-8'))
        if not wrapper().validate_result(raw)['valid']:raise ValueError('v19结果不完整')
        outputs={}
        for stage in ['wu_intake','search_replay','attribution','wu_evaluation']:
            record=state['stages'][stage]
            if record['status']!='succeeded':raise ValueError('前置阶段未完成')
            value=json.loads((store.root/record['output']).read_text(encoding='utf-8'))
            if fingerprint(value)!=record['output_hash']:raise ValueError('前置底稿哈希错误')
            outputs[stage]=value
        prov=workspace['pipeline_provenance']
        if [prov[k] for k in ['intake_hash','search_hash','attribution_hash']]!=[fingerprint(outputs['wu_intake']),fingerprint(outputs['search_replay']['replay']),fingerprint(outputs['attribution'])]:
            raise ValueError('独立运行与本任务的上游来源不一致')
        if workspace['project_profile']['project_id']!=state['inputs']['project_id'] or prov['local_outcome_id']!=state['inputs']['outcome_id']:
            raise ValueError('项目或成果关联错误')
        current_ids={x['outcome_id'] for x in raw['outcomes']}
        if current_ids!={prov['frozen_child_id']}:raise ValueError('v19结果扩大了评测范围')
        with Session() as db:
            row=db.scalar(select(PipelineJob).where(PipelineJob.id==store.root.name).with_for_update())
            if not row or row.status!='waiting':raise ValueError('数据库任务状态不允许回挂')
            previous=state['stages']['v19_evaluation']
            number=previous['attempts']+1
            folder=store.root/'v19_evaluation'/f'attempt-{number}'
            folder.mkdir(parents=True,exist_ok=False)
            shutil.copytree(run_root/'artifacts',folder/'artifacts')
            shutil.copy2(run_root/'workspace.json',folder/'workspace.json')
            value={'rubric_id':'outcome-d1-d7-evaluation.v19','project_id':row.project_id,'outcome_id':row.outcome_id,
                'workspace_hash':fingerprint(workspace),'result':raw,'execution_mode':'verified_external_run',
                'source_run':str(run_root),'upstream_lineage':prov,'attachment_implementation_hash':implementation_fingerprint()}
            atomic_json(folder/'output.json',value)
            state.setdefault('stage_history',[]).append({'stage':'v19_evaluation',**previous})
            state['stages']['v19_evaluation']={'status':'succeeded','attempts':number,'output':(folder/'output.json').relative_to(store.root).as_posix(),
                'output_hash':fingerprint(value),'finished_at':timestamp(),'execution_mode':'verified_external_run','source_run':str(run_root)}
            outputs['v19_evaluation']=value
            export_folder=store.root/'export'/'attempt-1';export_folder.mkdir(parents=True,exist_ok=False)
            final=export_stage(state['inputs'],outputs,export_folder);atomic_json(export_folder/'output.json',final)
            state['stages']['export']={'status':'succeeded','attempts':1,'output':'export/attempt-1/output.json','output_hash':fingerprint(final),'finished_at':timestamp()}
            state['status']='succeeded'
            state.setdefault('external_run_attachments',[]).append({'source_run':str(run_root),'attached_at':timestamp(),'upstream_verified':True,'frozen_child_id':prov['frozen_child_id']})
            atomic_json(store.path,state)
            row.status='succeeded';row.error='';row.finished_at=now();row.revision+=1
            db.add(Audit(actor=row.created_by,action='attach_verified_v19_run',target=row.id));db.commit()
            print('Verified v19 tail attached; two result files exported. Nothing published.')
    finally:lock.unlink(missing_ok=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--pipeline',type=Path,required=True);p.add_argument('--v19',type=Path,required=True);a=p.parse_args();attach(a.pipeline.resolve(),a.v19.resolve())
