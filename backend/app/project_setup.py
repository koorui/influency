"""Idempotently attach the existing chemistry deployment to the project model."""
import json
import secrets
from pathlib import Path
from sqlalchemy import select
from .db import Session
from .config import settings
from .models import Project, Material, PipelineJob, Result, Ticket, User, uid
from .project_service import set_access_code, job_directory
from .pipeline_store import PipelineStore


def initialize():
    root=Path(settings().storage_dir)
    with Session() as db:
        if db.scalar(select(Project.id).limit(1)):return
        if not db.scalar(select(Material.id).limit(1)):return
        source=db.scalar(select(PipelineJob).where(PipelineJob.id=='35d14b2e-e919-4aa9-ba6e-4222d7824a9d'))
        boundary=PipelineStore(job_directory(source.id)).read()['inputs'].get('search_boundary') if source else None
        p=Project(id=uid(),name='人工智能赋能有机化学',code='P02',access_prefix=secrets.token_hex(4),
            access_version=1,evaluation_config={'search_boundary':boundary})
        code=set_access_code(p);db.add(p);db.flush()
        for material in db.scalars(select(Material)):
            material.project_id=p.id
            material.use_in_workflow=int(not material.filename.startswith('历史交付/') and material.purpose=='project')
        for job in db.scalars(select(PipelineJob).where(PipelineJob.project_id=='P02')):
            job.project_ref=p.id
            if job.status=='succeeded' and not job.ticket_id:
                ticket=Ticket(id=uid(),project_id=p.id,owner='user:'+job.created_by,query=job.title,
                    normalized_query=job.title.casefold(),status='processing',note='历史完整工作流',created_at=job.created_at)
                db.add(ticket);db.flush();job.ticket_id=ticket.id
        for report in db.scalars(select(Result)):
            job=db.get(PipelineJob,report.pipeline_id) if report.pipeline_id else None
            if job and job.project_ref:report.project_id=job.project_ref
        # Save before commit so the one-time code remains recoverable if the process exits.
        (root/'project-access-codes.json').write_text(json.dumps({p.id:{'name':p.name,'access_code':code}},ensure_ascii=False,indent=2),encoding='utf-8')
        db.commit()
    print('Chemistry project created; access code stored privately in the material volume.')


if __name__=='__main__':initialize()
