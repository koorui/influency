"""Delete project-owned records and files together, with rollback staging."""
import json
import logging
import shutil
from pathlib import Path
from fastapi import HTTPException
from sqlalchemy import select, delete, or_
from .config import settings
from .models import (Project, ProjectMember, Material, PipelineJob, Ticket, OutcomeSubmission,
                     Task, Result, ResultVersion, QueryRecord, Audit, uid)
from .project_service import job_directory
from .pipeline_store import PipelineStore

log = logging.getLogger(__name__)


def lock_project(db, identifier):
    project = db.scalar(select(Project).where(Project.id == str(identifier)).with_for_update())
    if not project:
        raise HTTPException(404, '项目不存在')
    return project


def ensure_idle(jobs, tasks=()):
    if any(j.status == 'running' or (job_directory(j.id)/'execution.lock').exists() for j in jobs):
        raise HTTPException(409, '工作流正在运行，完成或停止后才能删除')
    if any(t.status == 'running' for t in tasks):
        raise HTTPException(409, '项目仍有任务正在运行')


def commit_with_files(db, relatives):
    """Move files before commit; restore on failure. Never follow paths outside storage."""
    root = Path(settings().storage_dir).resolve()
    paths = []
    for relative in dict.fromkeys(relatives):
        path = (root/relative).resolve()
        if path == root or not path.is_relative_to(root) or '.deletion-trash' in path.relative_to(root).parts:
            raise ValueError('删除路径不在项目存储范围内')
        if path.exists(): paths.append(path)
    trash = root/'.deletion-trash'/uid()
    moved = []
    try:
        if paths:
            trash.mkdir(parents=True)
            (trash/'manifest.json').write_text(json.dumps([str(p.relative_to(root)) for p in paths]), encoding='utf-8')
        for index, path in enumerate(paths):
            target = trash/str(index)
            path.rename(target)
            moved.append((path, target))
        db.commit()
    except Exception:
        db.rollback()
        for path, target in reversed(moved):
            path.parent.mkdir(parents=True, exist_ok=True)
            target.rename(path)
        if trash.exists(): shutil.rmtree(trash)
        raise
    if trash.exists():
        try: shutil.rmtree(trash)
        except OSError: log.exception('Deleted files await removal in %s', trash)


def remove_records(db, jobs, tickets, tasks, actor, *, project=None, materials=()):
    ensure_idle(jobs, tasks)
    job_ids = [j.id for j in jobs]; ticket_ids = [t.id for t in tickets]; task_ids = [t.id for t in tasks]
    predicate = or_(Result.pipeline_id.in_(job_ids), Result.task_id.in_(task_ids))
    if project: predicate = or_(predicate, Result.project_id == project.id)
    result_ids = list(db.scalars(select(Result.id).where(predicate)))
    db.execute(delete(QueryRecord).where(QueryRecord.result_id.in_(result_ids)))
    db.execute(delete(ResultVersion).where(ResultVersion.result_id.in_(result_ids)))
    db.execute(delete(Result).where(Result.id.in_(result_ids)))
    db.execute(delete(OutcomeSubmission).where(OutcomeSubmission.ticket_id.in_(ticket_ids)))
    db.execute(delete(Task).where(Task.id.in_(task_ids)))
    db.execute(delete(PipelineJob).where(PipelineJob.id.in_(job_ids)))
    db.execute(delete(Ticket).where(Ticket.id.in_(ticket_ids)))
    db.execute(delete(Material).where(Material.id.in_([m.id for m in materials])))
    targets = job_ids + ticket_ids + task_ids + result_ids + [m.id for m in materials]
    if project:
        db.execute(delete(ProjectMember).where(ProjectMember.project_id == project.id))
        db.execute(delete(Project).where(Project.id == project.id))
        targets.append(project.id)
    db.execute(delete(Audit).where(Audit.target.in_(targets)))
    db.add(Audit(actor=actor, action='delete_project' if project else 'delete_workflow', target=project.id if project else ticket_ids[0]))
    paths = ['pipelines/'+i for i in job_ids] + ['evaluations/'+i for i in task_ids] + [m.storage_key for m in materials]
    commit_with_files(db, paths)
    return {'deleted': True, 'workflows': len(job_ids), 'tickets': len(ticket_ids), 'reports': len(result_ids), 'materials': len(materials)}


def remove_request(db, identifier, actor):
    ticket = db.get(Ticket, str(identifier))
    if not ticket: raise HTTPException(404, '工单不存在')
    lock_project(db, ticket.project_id)
    jobs = list(db.scalars(select(PipelineJob).where(PipelineJob.ticket_id == ticket.id).with_for_update()))
    tasks = list(db.scalars(select(Task).where(Task.ticket_id == ticket.id).with_for_update()))
    return remove_records(db, jobs, [ticket], tasks, actor)


def remove_project(db, identifier, actor):
    project = lock_project(db, identifier)
    tickets = list(db.scalars(select(Ticket).where(Ticket.project_id == project.id)))
    ticket_ids = [t.id for t in tickets]
    jobs = list(db.scalars(select(PipelineJob).where(or_(PipelineJob.project_ref == project.id, PipelineJob.ticket_id.in_(ticket_ids))).with_for_update()))
    tasks = list(db.scalars(select(Task).where(Task.ticket_id.in_(ticket_ids)).with_for_update()))
    materials = list(db.scalars(select(Material).where(Material.project_id == project.id)))
    return remove_records(db, jobs, tickets, tasks, actor, project=project, materials=materials)


def remove_material(db, project_id, material_id, actor):
    lock_project(db, project_id)
    material = db.get(Material, str(material_id))
    if not material or material.project_id != str(project_id): raise HTTPException(404, '项目材料不存在')
    for job in db.scalars(select(PipelineJob).where(PipelineJob.project_ref == str(project_id))):
        try: state = PipelineStore(job_directory(job.id)).read()
        except (OSError, ValueError): raise HTTPException(409, '无法确认工作流材料引用，请先删除相关工作流')
        if material.id in json.dumps(state, ensure_ascii=False):
            raise HTTPException(409, '该材料已被工作流引用，请先删除相关工作流；仅停止后续使用可取消“默认用于评测”')
    for model, field in ((Result, Result.payload), (Task, Task.material_ids), (OutcomeSubmission, OutcomeSubmission.material_ids)):
        for value in db.scalars(select(field)):
            if material.id in json.dumps(value, ensure_ascii=False):
                raise HTTPException(409, '该材料仍被记录引用，请先删除相关工作流')
    db.delete(material)
    db.add(Audit(actor=actor, action='delete_material', target=material.id))
    commit_with_files(db, [material.storage_key])
    return {'deleted': True}
