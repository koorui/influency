"""Remove the reviewed delivery's demo/single-task history; preserve real full runs."""
import argparse
import json
import shutil
from pathlib import Path
from sqlalchemy import select, delete
from .db import Session
from .config import settings
from .models import Material, PipelineJob, Task, Result, ResultVersion, QueryRecord, OutcomeSubmission, Ticket, Audit
from .project_service import job_directory, deliver_report
from .pipeline_store import PipelineStore

KEEP={'35d14b2e-e919-4aa9-ba6e-4222d7824a9d','3a90af73-833f-4ef2-ac03-2778dd4d25e7','6c4d17c7-7356-437d-b5e4-81e497d9ffeb'}


def main(apply=False):
    root=Path(settings().storage_dir).resolve();receipt=root/'legacy-cleanup-completed.json'
    if receipt.exists():print('Cleanup already completed.');return
    with Session() as db:
        jobs=list(db.scalars(select(PipelineJob)));materials=list(db.scalars(select(Material)))
        if any(j.status in ('queued','running') for j in jobs):raise ValueError('Active workflow; cleanup refused')
        known={m.id for m in materials};referenced=set()
        def scan(value):
            if isinstance(value,dict):
                for v in value.values():scan(v)
            elif isinstance(value,list):
                for v in value:scan(v)
            elif isinstance(value,str) and value in known:referenced.add(value)
        for job in jobs:
            if job.id in KEEP:
                scan(PipelineStore(job_directory(job.id)).read())
                # Retain evidence mentioned only in final output, too.
                for path in job_directory(job.id).glob('*/attempt-*/output.json'):scan(json.loads(path.read_text(encoding='utf-8')))
        keep_materials=referenced|{m.id for m in materials if not m.filename.startswith('历史交付/')}
        removed_materials=[m for m in materials if m.id not in keep_materials]
        removed_jobs=[j.id for j in jobs if j.id not in KEEP]
        old_tasks=list(db.scalars(select(Task.id)))
        keep_tickets={j.ticket_id for j in jobs if j.id in KEEP and j.ticket_id}
        removed_results=list(db.scalars(select(Result.id).where((Result.pipeline_id.is_(None))|(~Result.pipeline_id.in_(KEEP)))))
        report={'kept_materials':len(keep_materials),'removed_materials':len(removed_materials),
            'kept_workflows':len([j for j in jobs if j.id in KEEP]),'removed_workflows':len(removed_jobs),
            'removed_single_tasks':len(old_tasks),'removed_reports':len(removed_results)}
        print(json.dumps(report,ensure_ascii=False))
        if not apply:return
        db.execute(delete(QueryRecord))
        db.execute(delete(ResultVersion).where(ResultVersion.result_id.in_(removed_results)))
        db.execute(delete(Result).where(Result.id.in_(removed_results)))
        db.execute(delete(OutcomeSubmission).where(~OutcomeSubmission.ticket_id.in_(keep_tickets)))
        db.execute(delete(Task))
        db.execute(delete(PipelineJob).where(PipelineJob.id.in_(removed_jobs)))
        db.execute(delete(Ticket).where(~Ticket.id.in_(keep_tickets)))
        db.execute(delete(Material).where(Material.id.in_([m.id for m in removed_materials])))
        valid=keep_materials|KEEP|keep_tickets|set(db.scalars(select(Result.id)))
        db.execute(delete(Audit).where(~Audit.target.in_(valid)))
        for job in jobs:
            if job.id in KEEP:deliver_report(db,job)
        db.add(Audit(actor='admin',action='legacy_cleanup',target=next(iter(KEEP))))
        db.commit()
    # Only paths belonging to deleted rows, inside this deployment's material volume.
    for relative in [*(m.storage_key for m in removed_materials),
                     *('pipelines/'+i for i in removed_jobs), *('evaluations/'+i for i in old_tasks)]:
        path=(root/relative).resolve()
        if not path.is_relative_to(root) or path==root:raise ValueError('Unsafe cleanup path')
        if path.is_dir():shutil.rmtree(path)
        else:path.unlink(missing_ok=True)
    receipt.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--apply',action='store_true')
    main(parser.parse_args().apply)
