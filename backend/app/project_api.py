from datetime import timedelta
import json
import secrets
import shutil
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import Field, model_validator
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .auth import admin, current_user, check_password
from .db import get_db
from .models import Project, ProjectMember, AccessAttempt, User, Material, Ticket, OutcomeSubmission, PipelineJob, Result, Audit, now, uid
from .schema import StrictModel
from .pipeline_api import SearchBoundary
from .pipeline_store import PipelineStore
from .project_service import (allowed_projects, require_project, project_data, set_access_code,
    ticket_data, create_ticket_job, job_directory, stage_output, selected_materials)
from .project_deletion import lock_project, remove_project, remove_material, remove_request

router = APIRouter(prefix='/api')


class ProjectInput(StrictModel):
    name: str = Field(min_length=1,max_length=200)
    code: str = Field(min_length=1,max_length=100)
    search_boundary: SearchBoundary | None = None

    @model_validator(mode='after')
    def nonempty(self):
        self.name=self.name.strip();self.code=self.code.strip()
        if not self.name or not self.code: raise ValueError('项目名称和编号不能为空')
        return self


class AccessInput(StrictModel):
    code: str = Field(min_length=1,max_length=100)


class TicketInput(StrictModel):
    project_id: UUID
    request_key: UUID
    outcome_name: str = Field(min_length=1,max_length=200)
    description: str = Field(default='',max_length=5000)

    @model_validator(mode='after')
    def nonempty(self):
        self.outcome_name=self.outcome_name.strip()
        if not self.outcome_name: raise ValueError('请输入成果名称')
        return self


class MaterialInput(StrictModel):
    use_in_workflow: bool


@router.get('/projects')
def projects(db:Session=Depends(get_db),user:User=Depends(current_user)):
    return [project_data(p) for p in db.scalars(select(Project).where(Project.id.in_(allowed_projects(user))).order_by(Project.created_at))]


@router.post('/projects/unlock')
def unlock(body:AccessInput,db:Session=Depends(get_db),user:User=Depends(current_user)):
    # The account row serializes code attempts across API processes.
    db.scalar(select(User).where(User.id==user.id).with_for_update())
    attempt=db.get(AccessAttempt,user.id)
    if not attempt: attempt=AccessAttempt(id=user.id,failures=0);db.add(attempt)
    if attempt.locked_until and attempt.locked_until>now(): raise HTTPException(429,'安全码尝试过多，请五分钟后再试')
    if attempt.locked_until: attempt.failures=0;attempt.locked_until=None
    code=body.code.strip()
    parts=code.split('-',2)
    project=db.scalar(select(Project).where(Project.access_prefix==parts[1]).with_for_update()) if len(parts)==3 and parts[0]=='ZH' else None
    if not project or not check_password(code,project.access_secret):
        attempt.failures+=1
        if attempt.failures>=5: attempt.locked_until=now()+timedelta(minutes=5)
        db.commit();raise HTTPException(400,'安全码无效')
    member=db.scalar(select(ProjectMember).where(ProjectMember.project_id==project.id,ProjectMember.user_id==user.id))
    if not member: member=ProjectMember(project_id=project.id,user_id=user.id,access_version=project.access_version);db.add(member)
    else: member.access_version=project.access_version
    attempt.failures=0;attempt.locked_until=None
    db.commit();return project_data(project)


@router.get('/admin/projects')
def admin_projects(db:Session=Depends(get_db),user:User=Depends(admin)):
    return [project_data(p)|{'material_count':db.scalar(select(func.count()).select_from(Material).where(Material.project_id==p.id)),
        'ticket_count':db.scalar(select(func.count()).select_from(Ticket).where(Ticket.project_id==p.id)),
        'report_count':db.scalar(select(func.count()).select_from(Result).where(Result.project_id==p.id,Result.status=='published')),
        'search_boundary':p.evaluation_config.get('search_boundary')}
        for p in db.scalars(select(Project).order_by(Project.created_at))]


@router.post('/admin/projects',status_code=201)
def create_project(body:ProjectInput,db:Session=Depends(get_db),user:User=Depends(admin)):
    p=Project(id=uid(),name=body.name,code=body.code,access_prefix=secrets.token_hex(4),access_version=1,
        evaluation_config={'search_boundary':body.search_boundary.model_dump(mode='json') if body.search_boundary else None})
    code=set_access_code(p);db.add(p)
    try: db.commit()
    except IntegrityError: db.rollback();raise HTTPException(409,'项目名称或编号已存在')
    return project_data(p)|{'access_code':code}


@router.put('/admin/projects/{id}')
def update_project(id:UUID,body:ProjectInput,db:Session=Depends(get_db),user:User=Depends(admin)):
    p=lock_project(db,id)
    if p.code!=body.code and db.scalar(select(PipelineJob.id).where(PipelineJob.project_ref==p.id).limit(1)):
        raise HTTPException(409,'已有工作流的项目编号不可更改')
    p.name=body.name;p.code=body.code;p.evaluation_config={'search_boundary':body.search_boundary.model_dump(mode='json') if body.search_boundary else None}
    try: db.commit()
    except IntegrityError:db.rollback();raise HTTPException(409,'项目名称或编号已存在')
    return project_data(p)


@router.post('/admin/projects/{id}/access-code')
def rotate_code(id:UUID,db:Session=Depends(get_db),user:User=Depends(admin)):
    p=db.scalar(select(Project).where(Project.id==str(id)).with_for_update())
    if not p:raise HTTPException(404,'项目不存在')
    code=set_access_code(p);p.access_version+=1
    db.add(Audit(actor=user.id,action='rotate_project_code',target=p.id));db.commit()
    return {'access_code':code}


@router.get('/admin/projects/{id}/materials')
def project_materials(id:UUID,db:Session=Depends(get_db),user:User=Depends(admin)):
    require_project(db,user,id)
    return [{'id':m.id,'filename':m.filename,'size':m.size,'purpose':m.purpose,
        'use_in_workflow':bool(m.use_in_workflow),'created_at':m.created_at}
        for m in db.scalars(select(Material).where(Material.project_id==str(id)).order_by(Material.created_at.desc()))]


@router.post('/admin/projects/{id}/materials',status_code=207)
def upload_materials(id:UUID,files:list[UploadFile]=File(...),purpose:str=Form('project'),db:Session=Depends(get_db),user:User=Depends(admin)):
    lock_project(db,id)
    if purpose not in ('project','reference','instruction'): raise HTTPException(422,'材料用途无效')
    from .main import upload_batch
    return upload_batch(files,db,user,purpose,project_id=str(id))


@router.patch('/admin/projects/{id}/materials/{material_id}')
def select_material(id:UUID,material_id:UUID,body:MaterialInput,db:Session=Depends(get_db),user:User=Depends(admin)):
    lock_project(db,id)
    m=db.get(Material,str(material_id))
    if not m or m.project_id!=str(id):raise HTTPException(404,'项目材料不存在')
    if body.use_in_workflow and m.purpose!='project':raise HTTPException(422,'仅原始项目材料可用于工作流')
    m.use_in_workflow=int(body.use_in_workflow);db.commit();return {'ok':True}


@router.post('/requests',status_code=201)
def submit_ticket(body:TicketInput,db:Session=Depends(get_db),user:User=Depends(current_user)):
    lock_project(db,body.project_id)
    project=require_project(db,user,body.project_id)
    payload=body.model_dump(mode='json',exclude={'request_key'})
    existing=db.scalar(select(OutcomeSubmission).where(OutcomeSubmission.created_by==user.id,OutcomeSubmission.request_key==str(body.request_key)))
    if existing:
        if existing.payload!=payload:raise HTTPException(409,'该提交编号已使用，请刷新后重试')
        return ticket_data(db,db.get(Ticket,existing.ticket_id))
    ticket=Ticket(id=uid(),project_id=project.id,owner='user:'+user.id,query=body.outcome_name,normalized_query=body.outcome_name.casefold())
    job=None
    try:
        db.add(ticket);db.flush()
        job=create_ticket_job(db,project,ticket,user,body.description)
        db.add(OutcomeSubmission(ticket_id=ticket.id,created_by=user.id,request_key=str(body.request_key),payload=payload,material_ids=[]))
        db.add(Audit(actor=user.id,action='submit_workflow',target=ticket.id));db.commit()
    except Exception:
        db.rollback()
        if job:shutil.rmtree(job_directory(job.id),ignore_errors=True)
        existing=db.scalar(select(OutcomeSubmission).where(OutcomeSubmission.created_by==user.id,OutcomeSubmission.request_key==str(body.request_key)))
        if existing and existing.payload==payload:return ticket_data(db,db.get(Ticket,existing.ticket_id))
        raise
    return ticket_data(db,ticket)


@router.get('/requests')
def my_requests(db:Session=Depends(get_db),user:User=Depends(current_user)):
    return [ticket_data(db,t) for t in db.scalars(select(Ticket).where(Ticket.owner=='user:'+user.id,
        Ticket.project_id.in_(allowed_projects(user))).order_by(Ticket.created_at.desc()).limit(200))]


@router.get('/admin/requests')
def admin_requests(db:Session=Depends(get_db),user:User=Depends(admin)):
    return [ticket_data(db,t,True) for t in db.scalars(select(Ticket).where(Ticket.project_id.is_not(None)).order_by(Ticket.created_at.desc()).limit(500))]


@router.get('/reports')
def reports(project_id:UUID|None=None,db:Session=Depends(get_db),user:User=Depends(current_user)):
    query=select(Result,PipelineJob).join(PipelineJob,PipelineJob.id==Result.pipeline_id).where(
        Result.status=='published',PipelineJob.status=='succeeded',Result.project_id.in_(allowed_projects(user)))
    if project_id:require_project(db,user,project_id);query=query.where(Result.project_id==str(project_id))
    return [{'id':r.id,'title':job.title,'project_id':r.project_id,'project_name':db.get(Project,r.project_id).name,
        'published_at':r.published_at,'pipeline_id':r.pipeline_id}
        for r,job in db.execute(query.order_by(Result.published_at.desc()).limit(500))]


@router.get('/reports/{id}')
def report(id:UUID,db:Session=Depends(get_db),user:User=Depends(current_user)):
    r=db.scalar(select(Result).where(Result.id==str(id),Result.status=='published',Result.project_id.in_(allowed_projects(user))))
    if not r:raise HTTPException(404,'报告不存在或当前账号无权查看')
    job=db.get(PipelineJob,r.pipeline_id) if r.pipeline_id else None
    if not job or job.status!='succeeded':raise HTTPException(409,'工作流尚未完成')
    return {'id':r.id,'title':job.title,'project_name':db.get(Project,r.project_id).name,
        'payload':r.payload,'v19':stage_output(job,'v19_evaluation')['result'],'published_at':r.published_at,
        **report_acceptance(db,job,user)}


def report_acceptance(db,job,user):
    ticket=db.get(Ticket,job.ticket_id) if job.ticket_id else None
    owner=ticket is not None and ticket.owner=='user:'+user.id
    return {'ticket_id':ticket.id if owner else None,
        'can_accept':bool(owner and not ticket.accepted_at),
        'accepted_at':ticket.accepted_at if owner else None}


@router.post('/requests/{id}/accept-report')
def accept_report(id:UUID,db:Session=Depends(get_db),user:User=Depends(current_user)):
    ticket=db.scalar(select(Ticket).where(Ticket.id==str(id),Ticket.owner=='user:'+user.id).with_for_update())
    if not ticket:raise HTTPException(404,'工单不存在')
    require_project(db,user,ticket.project_id)
    result=db.get(Result,ticket.result_id) if ticket.result_id else None
    job=db.get(PipelineJob,result.pipeline_id) if result and result.pipeline_id else None
    if not result or result.status!='published' or not job or job.status!='succeeded':raise HTTPException(409,'完整报告尚未生成')
    if not ticket.accepted_at:
        ticket.accepted_at=now();ticket.status='accepted';ticket.note='用户已验收报告'
        db.add(Audit(actor=user.id,action='accept_report',target=ticket.id));db.commit()
    return ticket_data(db,ticket)


@router.get('/admin/requests/{id}')
def request_detail(id:UUID,db:Session=Depends(get_db),user:User=Depends(admin)):
    ticket=db.get(Ticket,str(id))
    if not ticket or not ticket.project_id:raise HTTPException(404,'工单不存在')
    data=ticket_data(db,ticket,True)
    job=db.get(PipelineJob,data['pipeline_id']) if data['pipeline_id'] else None
    if job:
        from .pipeline_api import detail
        data['workflow']=detail(UUID(job.id),db)
        data['outputs']={}
        for name in ('wu_intake','search_replay','attribution','wu_evaluation','v19_evaluation'):
            if data['workflow']['stages'][name]['status']=='succeeded':data['outputs'][name]=stage_output(job,name)
    return data


class ContinueInput(StrictModel):
    revision:int
    confirmed_scope:str=Field(default='',max_length=200)
    refresh_materials:bool=False


class ReceiveInput(StrictModel):
    revision:int


@router.post('/admin/requests/{id}/receive')
def receive_request(id:UUID,body:ReceiveInput,db:Session=Depends(get_db),user:User=Depends(admin)):
    ticket=db.get(Ticket,str(id))
    if not ticket:raise HTTPException(404,'工单不存在')
    lock_project(db,ticket.project_id)
    job=db.scalar(select(PipelineJob).where(PipelineJob.ticket_id==ticket.id).with_for_update())
    if not job or job.status!='pending_acceptance' or job.revision!=body.revision:raise HTTPException(409,'工单状态已变化，请刷新')
    job.status='queued';job.revision+=1
    ticket.received_at=now();ticket.received_by=user.id;ticket.status='processing';ticket.note='已受理，等待执行完整工作流'
    db.add(Audit(actor=user.id,action='receive_request',target=ticket.id));db.commit()
    return ticket_data(db,ticket,True)


@router.delete('/admin/projects/{id}')
def delete_project(id:UUID,db:Session=Depends(get_db),user:User=Depends(admin)):
    return remove_project(db,id,user.id)


@router.delete('/admin/projects/{id}/materials/{material_id}')
def delete_material(id:UUID,material_id:UUID,db:Session=Depends(get_db),user:User=Depends(admin)):
    return remove_material(db,id,material_id,user.id)


@router.delete('/admin/requests/{id}')
def delete_request(id:UUID,db:Session=Depends(get_db),user:User=Depends(admin)):
    return remove_request(db,id,user.id)


@router.post('/admin/requests/{id}/continue')
def continue_request(id:UUID,body:ContinueInput,db:Session=Depends(get_db),user:User=Depends(admin)):
    ticket=db.get(Ticket,str(id))
    if not ticket or not ticket.project_id:raise HTTPException(404,'工单不存在')
    lock_project(db,ticket.project_id)
    job=db.scalar(select(PipelineJob).where(PipelineJob.ticket_id==ticket.id).with_for_update())
    if not job or job.revision!=body.revision or job.status not in ('failed','waiting'):raise HTTPException(409,'工单状态已变化，请刷新')
    project=require_project(db,user,ticket.project_id)
    store=PipelineStore(job_directory(job.id));state=store.read();patch={}
    if body.confirmed_scope.strip():patch['confirmed_scope']=body.confirmed_scope.strip()
    if body.refresh_materials:patch['materials']=selected_materials(db,project)
    boundary=project.evaluation_config.get('search_boundary')
    if state['inputs'].get('search_boundary')!=boundary:patch['search_boundary']=boundary
    try:
        if patch:store.amend(patch,'wu_intake' if {'materials','confirmed_scope'}&patch.keys() else 'search_replay')
        elif (store.root/'execution.lock').exists():raise ValueError('任务仍有执行锁，请检查后台状态')
    except (ValueError,FileExistsError) as exc:raise HTTPException(409,str(exc))
    job.status='queued';job.error='';job.revision+=1;ticket.status='processing';ticket.note='已继续处理'
    db.commit();return ticket_data(db,ticket,True)
