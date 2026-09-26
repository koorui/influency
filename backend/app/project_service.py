"""Project access and the single ticket-to-report lifecycle."""
from pathlib import Path
import json
import secrets
from fastapi import HTTPException
from sqlalchemy import select
from .auth import hash_password
from .config import settings
from .models import Project, ProjectMember, Material, PipelineJob, Ticket, Result, ResultVersion, Audit, uid, now
from .pipeline_store import PipelineStore, STAGES

STEPS = [('成果卡', ('wu_intake',)), ('外部 Search', ('search_replay',)),
         ('贡献归因', ('attribution',)), ('双层影响力评价', ('wu_evaluation','v19_evaluation','export'))]


def set_access_code(project):
    code = 'ZH-' + project.access_prefix + '-' + secrets.token_urlsafe(12)
    project.access_secret = hash_password(code)
    return code


def allowed_projects(user):
    if user.role == 'admin': return select(Project.id)
    return select(Project.id).join(ProjectMember, ProjectMember.project_id == Project.id).where(
        ProjectMember.user_id == user.id, ProjectMember.access_version == Project.access_version)


def require_project(db, user, identifier):
    project = db.scalar(select(Project).where(Project.id == str(identifier), Project.id.in_(allowed_projects(user))))
    if not project: raise HTTPException(404, '项目不存在或尚未输入有效安全码')
    return project


def project_data(project):
    return {'id':project.id, 'name':project.name, 'code':project.code}


def job_directory(identifier):
    return (Path(settings().storage_dir) / 'pipelines' / str(identifier)).resolve()


def stage_output(job, name):
    store = PipelineStore(job_directory(job.id)); state = store.read()
    stage = state['stages'][name]
    if stage['status'] != 'succeeded': raise HTTPException(409, '该阶段尚未完成')
    path = (store.root / stage['output']).resolve()
    if not path.is_relative_to(store.root): raise HTTPException(409, '阶段文件路径异常')
    return json.loads(path.read_text(encoding='utf-8'))


def progress(job):
    if not job: return [{'name':name,'status':'pending'} for name,_ in STEPS]
    try: stages = PipelineStore(job_directory(job.id)).read()['stages']
    except (OSError, ValueError, KeyError): return [{'name':name,'status':'pending'} for name,_ in STEPS]
    output = []
    for name, keys in STEPS:
        statuses = [stages[k]['status'] for k in keys]
        status = next((x for x in ('failed','waiting','running') if x in statuses), None)
        if not status: status = 'succeeded' if all(x == 'succeeded' for x in statuses) else 'running' if 'succeeded' in statuses else 'pending'
        output.append({'name':name,'status':status})
    return output


def ticket_data(db, ticket, administrator=False):
    project = db.get(Project, ticket.project_id)
    job = db.scalar(select(PipelineJob).where(PipelineJob.ticket_id == ticket.id).order_by(PipelineJob.created_at.desc()).limit(1))
    result = db.get(Result, ticket.result_id) if ticket.result_id else None
    status = job.status if job else ticket.status
    if result and result.status == 'published': status = 'accepted' if ticket.accepted_at else 'awaiting_acceptance'
    value = {'id':ticket.id, 'project_id':ticket.project_id, 'project_name':project.name,
        'outcome_name':ticket.query, 'status':status, 'steps':progress(job),
        'result_id':result.id if result and result.status == 'published' else None,
        'created_at':ticket.created_at, 'note':ticket.note,
        'received_at':ticket.received_at, 'accepted_at':ticket.accepted_at,
        'pipeline_id':job.id if job else None}
    if administrator: value.update(revision=job.revision if job else 0, error=job.error if job else '')
    return value


def selected_materials(db, project):
    rows = list(db.scalars(select(Material).where(Material.project_id == project.id,
        Material.purpose == 'project', Material.use_in_workflow == 1).order_by(Material.created_at)))
    if sum(len(m.text) for m in rows) > settings().codex_max_input_chars - 20000:
        raise HTTPException(422, '项目选用材料正文过长，请管理员缩小默认评测材料范围')
    return [{'id':m.id,'filename':m.filename,'text':m.text} for m in rows]


def create_ticket_job(db, project, ticket, user, description=''):
    identifier = uid()
    inputs = {'title':ticket.query, 'project_id':project.code, 'project_name':project.name,
        'outcome_id':'OUT-'+ticket.id, 'materials':selected_materials(db, project),
        'confirmed_scope':'', 'request_description':description,
        'search_mode':'live', 'search_boundary':project.evaluation_config.get('search_boundary'),
        'automatic_workspace':True, 'v19_workspace':None, 'v19_scope_mapping':None}
    PipelineStore(job_directory(identifier)).create(inputs)
    job = PipelineJob(id=identifier, title=ticket.query, project_id=project.code, project_ref=project.id,
        outcome_id=inputs['outcome_id'], ticket_id=ticket.id, created_by=user.id, status='pending_acceptance')
    ticket.status='pending_acceptance'; ticket.note='等待管理员受理'
    db.add(job)
    return job


def deliver_report(db, job):
    """Publish only when the complete workflow and both report contracts passed."""
    if job.status != 'succeeded' or not job.project_ref: raise ValueError('完整工作流尚未成功')
    from .skill_loader import contract
    from .codex_adapter import to_report
    from .pipeline_v19 import wrapper
    assessment = contract.Assessment.model_validate(stage_output(job,'wu_evaluation')['assessment'])
    contract.validate_completed_assessment(assessment)
    if assessment.evaluation_status in ('needs_scope_confirmation','insufficient_project_context'):
        raise ValueError('成果范围或上下文尚待确认')
    v19 = stage_output(job,'v19_evaluation')['result']
    if not wrapper().validate_result(v19)['valid']: raise ValueError('双层评价结果不完整')
    stage_output(job, 'export')
    payload = to_report(assessment, [assessment.outcome_resolution.canonical_name or job.title]).model_dump(mode='json')
    for evidence in payload.get('evidence', []):
        if evidence.get('material_id'):
            material = db.get(Material, evidence['material_id'])
            if not material or material.project_id != job.project_ref: raise ValueError('报告引用了其他项目或缺失的材料')
    result = db.scalar(select(Result).where(Result.pipeline_id == job.id).with_for_update())
    if result and result.status == 'published': return result
    if result is None:
        result = Result(pipeline_id=job.id,project_id=job.project_ref,title=payload['title'],payload=payload,search_text=payload['title'])
        db.add(result); db.flush()
    else:
        result.project_id=job.project_ref; result.payload=payload; result.title=payload['title'];result.revision+=1
    result.status='published';result.published_at=now()
    db.add(ResultVersion(result_id=result.id,revision=result.revision,payload=payload,editor='workflow'))
    if job.ticket_id:
        ticket = db.get(Ticket, job.ticket_id)
        ticket.result_id=result.id;ticket.status='published';ticket.note='报告已生成'
    db.add(Audit(actor='workflow',action='report_delivered',target=result.id))
    return result
