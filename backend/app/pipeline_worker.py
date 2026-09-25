"""Dedicated durable queue for multi-stage jobs; does not share the short task lease."""
import logging
import time
from sqlalchemy import select,update
from .db import Session
from .models import PipelineJob,Ticket,now
from .pipeline_api import directory
from .pipeline_service import run_pipeline
from .pipeline_store import PipelineStore

log=logging.getLogger(__name__)


def run_once():
    with Session() as db:
        id=db.scalar(select(PipelineJob.id).where(PipelineJob.status=='queued').order_by(PipelineJob.created_at).limit(1))
        if not id:return False
        claimed=db.execute(update(PipelineJob).where(PipelineJob.id==id,PipelineJob.status=='queued').values(status='running',started_at=now(),finished_at=None,error=''))
        db.commit()
        if not claimed.rowcount:return True
    try:
        state=run_pipeline(directory(id))
        status=state['status']
        error=next((v.get('error','') for v in state['stages'].values() if v['status'] in ('failed','waiting')),'')
    except Exception as exc:
        log.exception('Pipeline failed: %s',id)
        status,error='failed',str(exc)[:2000]
    with Session() as db:
        db.execute(update(PipelineJob).where(PipelineJob.id==id,PipelineJob.status=='running').values(status=status,error=error,finished_at=now(),revision=PipelineJob.revision+1))
        job=db.get(PipelineJob,id)
        ticket=db.get(Ticket,job.ticket_id) if job and job.ticket_id else None
        if ticket and ticket.status=='processing':
            ticket.note={'waiting':'评测需要补充材料或确认范围，管理员正在处理。','failed':'评测执行失败，管理员将查看底稿并处理。','succeeded':'评测已完成，等待管理员审核发布。'}.get(status,'评价工作流处理中。')
            if status=='succeeded':ticket.status='review'
        db.commit()
    return True


if __name__=='__main__':
    logging.basicConfig(level=logging.INFO)
    while True:
        try:worked=run_once()
        except Exception:log.exception('Pipeline queue unavailable');worked=False
        if not worked:time.sleep(2)
