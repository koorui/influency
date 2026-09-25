"""MySQL-backed durable queue; a separate process claims one task at a time.
Conditional UPDATE also permits multiple workers without duplicate claims.
"""
import logging
import time
from datetime import timedelta
from sqlalchemy import select, update
from .config import settings
from .db import Session
from .models import Task, Ticket, Material, Result, ResultVersion, now
from .schema import Evaluation
from .evaluator import get_adapter

log = logging.getLogger(__name__)


def search_text(payload):
    return ' '.join([payload['title'], *payload['keywords'], payload['summary']]).casefold()


def run_once():
    with Session() as db:
        # Expired leases become visible failures, never silent permanently-running tasks.
        cutoff = now() - timedelta(seconds=settings().task_timeout_seconds)
        expired_ids = list(db.scalars(select(Task.id).where(Task.status == 'running', Task.started_at < cutoff)))
        # Update specific primary keys to avoid locking an empty status-index range
        # while another MySQL worker changes a queued task to running.
        for expired_id in expired_ids:
            db.execute(update(Task).where(Task.id == expired_id, Task.status == 'running', Task.started_at < cutoff).values(
                status='failed', error='任务执行超时或进程中断，请检查后重试', finished_at=now()))
        db.commit()
        task_id = db.scalar(select(Task.id).where(Task.status == 'queued').order_by(Task.created_at).limit(1))
        if not task_id:
            return False
        claimed = db.execute(update(Task).where(Task.id == task_id, Task.status == 'queued').values(status='running', started_at=now(), attempts=Task.attempts + 1))
        db.commit()
        if not claimed.rowcount:
            return True
        task = db.get(Task, task_id)
        attempt = task.attempts
        material_rows=list(db.scalars(select(Material).where(Material.id.in_(task.material_ids))))
        valid_materials=len(material_rows)==len(set(task.material_ids)) and all(m.purpose=='project' for m in material_rows)
        inputs = [{'id': m.id, 'filename': m.filename, 'text': m.text} for m in material_rows]
        title, keywords, adapter_name = task.title, task.keywords, task.adapter
        project_context, confirmed_scope = task.project_context, task.confirmed_scope
        recorded_version = task.skill_version
    adapter = None
    try:
        if not valid_materials:raise ValueError('原始材料已缺失或用途已改为参考/流程说明，请重新核验材料后创建任务')
        adapter = get_adapter(adapter_name)
        if adapter.version != recorded_version:
            raise ValueError('任务入队后Skill版本已变更，请创建新任务，避免规则漂移')
        if adapter_name == 'codex':
            result = adapter.evaluate(title,keywords,inputs,task_id=task_id,attempt=attempt,project_context=project_context,confirmed_scope=confirmed_scope)
        else:
            result = adapter.evaluate(title, keywords, inputs)
        payload = Evaluation.model_validate(result).model_dump()
        with Session() as db:
            # Lock/fence completion against timeout, retry, or another process.
            task = db.scalar(select(Task).where(Task.id == task_id).with_for_update())
            if task.status != 'running' or task.attempts != attempt:
                return True
            task.raw_output = getattr(adapter,'raw_output','') or result.model_dump_json()
            row = Result(task_id=task_id, title=payload['title'], search_text=search_text(payload), payload=payload)
            db.add(row)
            db.flush()
            db.add(ResultVersion(result_id=row.id, revision=1, payload=payload, editor='system'))
            task.status, task.finished_at = 'succeeded', now()
            if task.ticket_id:
                ticket = db.get(Ticket, task.ticket_id)
                ticket.status = 'review'
            db.commit()
    except Exception as exc:
        log.exception('Evaluation failed: %s', task_id)
        with Session() as db:
            db.execute(update(Task).where(Task.id == task_id, Task.status == 'running', Task.attempts == attempt).values(status='failed', error=str(exc)[:2000], raw_output=getattr(adapter,'raw_output',''), finished_at=now()))
            db.commit()
    return True


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    while True:
        try:
            worked = run_once()
        except Exception:
            log.exception('Queue unavailable')
            worked = False
        if not worked:
            time.sleep(2)
