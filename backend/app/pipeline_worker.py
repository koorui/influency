"""Dedicated durable queue for multi-stage jobs; does not share the short task lease."""
import logging
import time
from sqlalchemy import select,update
from .db import Session
from .models import PipelineJob,Ticket,now
from .pipeline_api import directory
from .pipeline_service import run_pipeline
from .pipeline_store import PipelineStore, WaitingForInput, atomic_json

log=logging.getLogger(__name__)


def run_once():
    from .pipeline_liveness import recover_interrupted
    recover_interrupted()
    with Session() as db:
        id=db.scalar(select(PipelineJob.id).where(PipelineJob.status=='queued').order_by(PipelineJob.created_at).limit(1))
        if not id:return False
    from .pipeline_liveness import worker_guard
    try:
        with worker_guard(directory(id)):
            return run_claimed(id)
    except FileExistsError:
        return False


def run_claimed(id):
    with Session() as db:
        claimed=db.execute(update(PipelineJob).where(PipelineJob.id==id,PipelineJob.status=='queued').values(status='running',started_at=now(),finished_at=None,error=''))
        db.commit()
        if not claimed.rowcount:return True
    try:
        state=run_pipeline(directory(id))
        status=state['status']
        error=next((v.get('error','') for v in state['stages'].values() if v['status'] in ('failed','waiting')),'')
    except WaitingForInput as exc:
        status,error='waiting',str(exc)[:2000]
        store=PipelineStore(directory(id));state=store.read()
        state['status']='waiting';state['runtime_waiting']={'message':str(exc),'details':exc.details}
        atomic_json(store.path,state)
    except Exception as exc:
        log.exception('Pipeline failed: %s',id)
        status,error='failed',str(exc)[:2000]
    with Session() as db:
        db.execute(update(PipelineJob).where(PipelineJob.id==id,PipelineJob.status=='running').values(status=status,error=error,finished_at=now(),revision=PipelineJob.revision+1))
        job=db.get(PipelineJob,id)
        ticket=db.get(Ticket,job.ticket_id) if job and job.ticket_id else None
        if ticket and ticket.status=='processing':
            ticket.note={'waiting':'等待管理员补充材料或确认范围','failed':'处理异常，等待管理员处理','succeeded':'正在生成报告'}.get(status,'评价工作流处理中')
        if job and status=='succeeded':
            from .project_service import deliver_report
            try:deliver_report(db,job)
            except Exception as exc:
                log.exception('Report delivery failed: %s',id)
                job.status='failed';job.error='报告生成失败：'+str(exc)[:1800]
                if ticket:ticket.note='报告生成异常，等待管理员处理'
        db.commit()
    return True


if __name__=='__main__':
    logging.basicConfig(level=logging.INFO)
    while True:
        try:worked=run_once()
        except Exception:log.exception('Pipeline queue unavailable');worked=False
        if not worked:time.sleep(2)
