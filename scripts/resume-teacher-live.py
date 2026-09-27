"""Resume a failed live run, keeping its raw response and journal history."""
import argparse
import json
import sys
from pathlib import Path
parser=argparse.ArgumentParser()
parser.add_argument('--runtime',type=Path,required=True)
parser.add_argument('--job',required=True)
parser.add_argument('--receipt',required=True)
parser.add_argument('--saved-intake',type=Path)
parser.add_argument('--repair-intake',action='store_true')
parser.add_argument('--saved-management',type=Path)
parser.add_argument('--saved-ledger',type=Path)
args=parser.parse_args();sys.path.insert(0,str(args.runtime/'backend'))
from app.db import Session
from app.models import PipelineJob,now
from app.config import settings
from app.pipeline_store import PipelineStore,atomic_json
from app.pipeline_contracts import CurrentWuIntake
from app.pipeline_stages import finish_intake,wu_intake_stage,search_replay_stage,attribution_stage,wu_evaluation_stage
from app.pipeline_v19 import v19_evaluation_stage,export_stage
from app.project_service import job_directory,deliver_report
if args.saved_ledger:
    from app import evaluation_facts
    original_prepare=evaluation_facts.prepare_fact_ledger
    evaluation_facts.prepare_fact_ledger=lambda inputs,outputs,payload,folder:original_prepare(inputs,outputs,payload,folder,saved_response=args.saved_ledger)
root=Path(settings().storage_dir)/'teacher-v4-comparison'/args.receipt
sys.stdout=(root/'resume.log').open('w',encoding='utf-8',buffering=1);sys.stderr=sys.stdout
def intake(inputs,outputs,folder):
    if not args.saved_intake:return wu_intake_stage(inputs,outputs,folder)
    raw=json.loads(args.saved_intake.read_text(encoding='utf-8'))
    if args.repair_intake:
        from app.pipeline_model import execute_json_stage
        value=execute_json_stage(folder,CurrentWuIntake,{'candidate':raw},
            'Repair only inconsistent factor declarations/references in this previous intake. '
            'All involved_factor_ids, isolated_factor_ids and claim factor_id must reference factors actually declared. '
            'If a real contributor was omitted, declare it from the existing source-backed candidate; do not drop a needed factor to meet an arbitrary count. '
            'Do not add sources, change quotes, change the outcome card, scope, use records, measurements or scientific claims. '
            'Do not perform Search. Preserve all other fields exactly. Return the complete corrected intake.',inline_input=True)
        corrected=value.model_dump()
        for key in ('outcome_card','evidence','evaluation_objects','primary_object_id','use_records','canonical_name'):
            if corrected.get(key)!=raw.get(key):raise ValueError('修复因素引用时改变了冻结材料或对象')
        for old,new in zip(raw['comparisons'],corrected['comparisons']):
            for key in ('baseline','observed','comparison_kind','evidence_ids','comparability_status'):
                if old.get(key)!=new.get(key):raise ValueError('修复因素引用时改变了比较事实')
    else:value=CurrentWuIntake.model_validate(raw)
    atomic_json(folder/'reuse-receipt.json',{'original_response':str(args.saved_intake),'source_text_edited':False,
        'reason':'保留原始响应与科学事实，按当前校验规则恢复；如需修复因素引用或原文引文，另存修复回执。'})
    return finish_intake(inputs,folder,value)

def management(inputs,outputs,folder):
    if not args.saved_management:return wu_evaluation_stage(inputs,outputs,folder)
    from app.pipeline_model import expand_fact_citations,preserve_frozen_card
    from app.pipeline_stages import finish_wu_evaluation
    from app.skill_loader import contract
    payload=json.loads((args.saved_management.parent/'input.json').read_text(encoding='utf-8'))
    raw=json.loads(args.saved_management.read_text(encoding='utf-8'))
    value,labels=contract.normalize_level_labels(raw)
    value,card=preserve_frozen_card(value,payload)
    value=expand_fact_citations(value,payload,folder)
    atomic_json(folder/'input.json',payload)
    atomic_json(folder/'reuse-receipt.json',{'original_response':str(args.saved_management),
        'grade_edited':False,'label_corrections':labels,'card_binding':card})
    return finish_wu_evaluation(inputs,outputs,folder,contract.FinalAssessment.model_validate(value),payload)
try:
    with Session() as db:
        job=db.get(PipelineJob,args.job)
        if job.status not in ('failed','waiting'):raise ValueError('只续跑失败或等待中的任务')
        job.status='running';job.error='';db.commit()
    atomic_json(root/'status.json',{'status':'running','pipeline_id':args.job,'resumed':True})
    state=PipelineStore(job_directory(args.job)).execute({'wu_intake':intake,'search_replay':search_replay_stage,
        'attribution':attribution_stage,'wu_evaluation':management,'v19_evaluation':v19_evaluation_stage,'export':export_stage})
    with Session() as db:
        job=db.get(PipelineJob,args.job);job.status=state['status'];job.finished_at=now();job.revision+=1
        if state['status']=='succeeded':
            result=deliver_report(db,job);atomic_json(root/'publication.json',{'result_id':result.id,'url':'http://localhost:18080/results/'+result.id})
        else:job.error=next((s.get('error','') for s in state['stages'].values() if s['status'] in ('failed','waiting')),'')
        db.commit()
    atomic_json(root/'status.json',{'status':state['status'],'pipeline_id':args.job})
except Exception as exc:
    with Session() as db:
        job=db.get(PipelineJob,args.job);job.status='failed';job.error=str(exc);job.finished_at=now();db.commit()
    atomic_json(root/'status.json',{'status':'failed','error':str(exc),'pipeline_id':args.job})
    raise
