"""Run and publish one authorized new local evaluation, preserving prior reports."""
import argparse
import sys
from pathlib import Path
from datetime import datetime
parser=argparse.ArgumentParser()
parser.add_argument('--runtime',type=Path,required=True)
parser.add_argument('--outcome',required=True)
parser.add_argument('--receipt',required=True)
args=parser.parse_args()
sys.path.insert(0,str(args.runtime/'backend'))
from app.db import Session
from app.models import PipelineJob, Ticket, Project, User, uid, now
from app.config import settings
from app.pipeline_service import run_pipeline
from app.pipeline_store import PipelineStore,atomic_json
from app.project_service import create_ticket_job,job_directory,deliver_report

root=Path(settings().storage_dir)/'teacher-v4-comparison'/args.receipt
root.mkdir(parents=True,exist_ok=False)
sys.stdout=(root/'run.log').open('w',encoding='utf-8',buffering=1);sys.stderr=sys.stdout
with Session() as db:
    previous=db.get(PipelineJob,'c6a13644-cdc1-4487-9d69-3eb92088d9d0')
    project=db.get(Project,previous.project_ref);user=db.get(User,previous.created_by)
    ticket=Ticket(id=uid(),project_id=project.id,owner='user:'+user.id,query=args.outcome,normalized_query=args.outcome.casefold())
    db.add(ticket);db.flush()
    job=create_ticket_job(db,project,ticket,user,'按已确认的吴老师v3融合计划开展真实完整评价；不预设等级，不代替专家认定。')
    job.status='running';job.started_at=now()
    ticket.status='processing';ticket.received_at=now();ticket.received_by=user.id
    db.add(job);db.commit();identifier=job.id
    atomic_json(root/'receipt.json',{'pipeline_id':identifier,'ticket_id':ticket.id,'outcome':args.outcome,
        'model':settings().codex_model,'reasoning_effort':settings().codex_reasoning_effort,'fresh_search':True})
try:
    state=run_pipeline(job_directory(identifier))
    with Session() as db:
        job=db.get(PipelineJob,identifier);job.status=state['status'];job.finished_at=now();job.revision+=1
        if state['status']=='succeeded':
            result=deliver_report(db,job)
            atomic_json(root/'publication.json',{'result_id':result.id,'url':'http://localhost:18080/results/'+result.id})
        else:job.error=next((s.get('error','') for s in state['stages'].values() if s['status'] in ('waiting','failed')),'')
        db.commit()
    atomic_json(root/'status.json',{'status':state['status'],'pipeline_id':identifier})
except Exception as exc:
    with Session() as db:
        job=db.get(PipelineJob,identifier);job.status='failed';job.error=str(exc);job.finished_at=now();db.commit()
    atomic_json(root/'status.json',{'status':'failed','pipeline_id':identifier,'error':str(exc)})
    raise
