import json
import os
from pathlib import Path
from uuid import UUID
from datetime import date
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Query
from fastapi.responses import FileResponse
from pydantic import Field,model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from .auth import admin
from .config import settings
from .db import get_db
from .models import PipelineJob,Material,Audit,User,Ticket,uid
from .pipeline_contracts import SearchReplay
from .pipeline_store import PipelineStore,STAGES
from .schema import StrictModel

router=APIRouter(prefix='/api/admin/pipelines',dependencies=[Depends(admin)])
ARTIFACT_SUFFIXES={'.json','.html','.md','.log','.jsonl','.csv','.txt','.pdf','.raw','.png'}


class SearchBoundary(StrictModel):
    project_start_date: date
    review_cutoff: date
    cutoff_basis: str = Field(min_length=1,max_length=1000)

    @model_validator(mode='after')
    def chronology(self):
        if self.project_start_date>self.review_cutoff:
            raise ValueError('证据截止日期不能早于项目启动日期')
        if self.review_cutoff>date.today():
            raise ValueError(f'本次评价的证据截止日期不能晚于今天（{date.today().isoformat()}），此处不是项目计划验收日期')
        return self


class ScopeMapping(StrictModel):
    outcome_id: str
    canonical_name: str = Field(min_length=1,max_length=200)
    reviewed: bool
    frozen_child_id: str | None = None
    evidence_routes: dict[str,list[str]] | None = None
    review_note: str = ''


class CreatePipeline(StrictModel):
    ticket_id: UUID | None = None
    title: str = Field(min_length=1,max_length=200)
    project_id: str = Field(min_length=1,max_length=100)
    project_name: str = Field(min_length=1,max_length=300)
    outcome_id: str = Field(min_length=1,max_length=160)
    material_ids: list[UUID] = Field(min_length=1,max_length=201)
    confirmed_scope: str = Field(default='',max_length=200)
    search_mode: Literal['replay','live'] = 'replay'
    search_boundary: SearchBoundary | None = None
    search_replay: SearchReplay | None = None
    v19_workspace: dict | None = None
    v19_scope_mapping: ScopeMapping | None = None

    @model_validator(mode='after')
    def consistent(self):
        if not all(x.strip() for x in [self.title,self.project_id,self.project_name,self.outcome_id]):raise ValueError('必填字段不能为空白')
        validate_handoffs(self.project_id,self.outcome_id,self.model_dump(mode='json'))
        return self


class AmendPipeline(StrictModel):
    revision: int
    search_mode: Literal['replay','live'] | None = None
    search_boundary: SearchBoundary | None = None
    confirmed_scope: str | None = Field(default=None,max_length=200)
    material_ids: list[UUID] | None = Field(default=None,min_length=1,max_length=201)
    search_replay: SearchReplay | None = None
    v19_workspace: dict | None = None
    v19_scope_mapping: ScopeMapping | None = None


class ResumePipeline(StrictModel):
    revision: int


def validate_handoffs(project_id,outcome_id,data):
    search=data.get('search_replay')
    if search and (search['project_id'],search['outcome_id'])!=(project_id,outcome_id):
        raise ValueError('Search回放必须对应当前项目和成果ID')
    workspace=data.get('v19_workspace')
    if workspace:
        profile=workspace.get('project_profile')
        if workspace.get('schema_version')!='indicator-workspace.v6' or not isinstance(profile,dict) or profile.get('project_id')!=project_id:
            raise ValueError('v19工作区版本或项目ID不匹配')
        if len(json.dumps(workspace,ensure_ascii=False))>6000000:raise ValueError('v19工作区超过6MB文本限制')
    mapping=data.get('v19_scope_mapping')
    if mapping and mapping['outcome_id']!=outcome_id:raise ValueError('成果范围映射ID不一致')


def directory(id):return (Path(settings().storage_dir)/'pipelines'/str(id)).resolve()


def materials(db,ids):
    rows=[]
    for id in dict.fromkeys(str(x) for x in ids):
        m=db.get(Material,id)
        if not m:raise HTTPException(404,'选定材料不存在')
        if m.purpose!='project':raise HTTPException(422,'参考结果或流程说明不能作为工作流的项目原始依据')
        rows.append({'id':m.id,'filename':m.filename,'text':m.text})
    if sum(len(m['text']) for m in rows)>settings().codex_max_input_chars:
        raise HTTPException(422,'材料超过单流程文本限制，请按成果拆分')
    return rows


def job_or_404(db,id,lock=False):
    stmt=select(PipelineJob).where(PipelineJob.id==str(id))
    if lock:stmt=stmt.with_for_update()
    row=db.scalar(stmt)
    if not row:raise HTTPException(404,'工作流不存在')
    return row


def summary(row):
    return {key:getattr(row,key) for key in ['id','title','project_id','outcome_id','ticket_id','status','revision','error','created_at','started_at','finished_at']}


@router.get('')
def listing(db:Session=Depends(get_db)):
    return [summary(j) for j in db.scalars(select(PipelineJob).order_by(PipelineJob.created_at.desc()).limit(100))]


@router.post('',status_code=201)
def create(body:CreatePipeline,db:Session=Depends(get_db),user:User=Depends(admin)):
    ticket=None
    if body.ticket_id:
        ticket=db.scalar(select(Ticket).where(Ticket.id==str(body.ticket_id)).with_for_update())
        if not ticket:raise HTTPException(404,'关联工单不存在')
        if ticket.status!='pending':raise HTTPException(409,'该工单已受理，请查看已有任务')
    data=body.model_dump(mode='json',exclude={'material_ids'})
    data['materials']=materials(db,body.material_ids)
    id=uid()
    PipelineStore(directory(id)).create(data)
    row=PipelineJob(id=id,title=body.title,project_id=body.project_id,outcome_id=body.outcome_id,created_by=user.id,ticket_id=str(body.ticket_id) if body.ticket_id else None)
    if ticket:ticket.status='processing';ticket.note='管理员已受理，完整评价工作流排队中。'
    db.add(row);db.add(Audit(actor=user.id,action='pipeline_create',target=id));db.commit()
    return summary(row)


@router.get('/{id}')
def detail(id:UUID,db:Session=Depends(get_db)):
    row=job_or_404(db,id)
    store=PipelineStore(directory(id));state=store.read()
    waiting={}
    if state.get('runtime_waiting'):waiting['runtime']=state['runtime_waiting']
    for stage,record in state['stages'].items():
        if record['status']=='waiting':
            path=store.root/stage/f"attempt-{record['attempts']}"/'waiting.json'
            if path.exists():waiting[stage]=json.loads(path.read_text(encoding='utf-8'))
    files=[]
    for p in store.root.rglob('*'):
        if p.is_file() and p.name!='execution.lock' and p.suffix in ARTIFACT_SUFFIXES and 'skill' not in p.relative_to(store.root).parts and '__pycache__' not in p.parts:
            files.append({'path':p.relative_to(store.root).as_posix(),'size':p.stat().st_size})
    def verified_output(name):
        record=state['stages'][name]
        if record['status']!='succeeded':return {}
        path=(store.root/record['output']).resolve()
        if not path.is_relative_to(store.root):raise HTTPException(409,'阶段底稿路径异常')
        value=json.loads(path.read_text(encoding='utf-8'))
        return value
    intake=verified_output('wu_intake').get('intake',{})
    search=verified_output('search_replay').get('replay',{})
    scope_evidence=[{'id':e['id'],'locator':e.get('locator',''),'quote':e.get('quote',''),'kind':'项目原文'} for e in intake.get('evidence',[])]
    for e in search.get('evidence',[]):
        quote=e.get('text','')
        try:
            parsed=json.loads(quote)
            if isinstance(parsed,dict):
                candidate=parsed.get('quote') or parsed.get('title')
                if isinstance(candidate,str):quote=candidate
        except (ValueError,TypeError):pass
        scope_evidence.append({'id':e['id'],'locator':e.get('locator',''),'quote':quote,
            'kind':'本轮检索（通过时点审计）' if search.get('mode')=='live_search' else '历史检索交付（非本次核验）'})
    workspace=state['inputs'].get('v19_workspace') or {}
    frozen=workspace.get('step3_frozen_outcomes') or {}
    scope_options=[]
    for parent in frozen.get('outcomes',[]) if isinstance(frozen,dict) else []:
        if not isinstance(parent,dict):continue
        children=parent.get('child_outcomes') or []
        for child in children if isinstance(children,list) else []:
            if isinstance(child,dict) and child.get('outcome_id'):
                scope_options.append({'id':child['outcome_id'],'title':child.get('title',''),'parent_id':parent.get('outcome_id',''),'parent_title':parent.get('title','')})
    heartbeat=None
    try:heartbeat=json.loads((store.root/'heartbeat.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):pass
    return {**summary(row),'heartbeat':heartbeat,'recoveries':state.get('recoveries',[]),'stages':state['stages'],'waiting':waiting,'files':files,'amendments':state.get('amendments',[]),
            'scope_options':scope_options,'scope_evidence':scope_evidence,'canonical_name':intake.get('canonical_name'),
            'scope_mapping':state['inputs'].get('v19_scope_mapping'),'search_mode':state['inputs'].get('search_mode','replay'),
            'search_boundary':state['inputs'].get('search_boundary'),
            'input_summary':{k:state['inputs'].get(k) for k in ['title','project_id','project_name','outcome_id','confirmed_scope']}}


@router.post('/{id}/resume')
def resume(id:UUID,body:ResumePipeline,db:Session=Depends(get_db),user:User=Depends(admin)):
    row=job_or_404(db,id,True)
    if row.revision!=body.revision or row.status not in ('waiting','failed'):
        raise HTTPException(409,'工作流状态已变化，请刷新；仅待补充或失败流程可续跑')
    if (directory(id)/'execution.lock').exists():raise HTTPException(409,'存在执行锁，请先核实后台进程状态')
    row.status='queued';row.error='';row.revision+=1
    db.add(Audit(actor=user.id,action='pipeline_resume',target=row.id));db.commit()
    return summary(row)


@router.post('/{id}/cancel')
def cancel(id:UUID,body:ResumePipeline,db:Session=Depends(get_db),user:User=Depends(admin)):
    row=job_or_404(db,id,True)
    if row.revision!=body.revision or row.status not in ('queued','waiting','failed'):
        raise HTTPException(409,'只能取消尚未执行或已暂停的流程，执行中任务请等待当前阶段结束')
    row.status='cancelled';row.revision+=1
    ticket=db.get(Ticket,row.ticket_id) if row.ticket_id else None
    if ticket and ticket.status=='processing':ticket.status='pending';ticket.note='关联工作流已取消，等待管理员重新受理。'
    db.add(Audit(actor=user.id,action='pipeline_cancel',target=row.id));db.commit()
    return summary(row)


@router.patch('/{id}')
def amend(id:UUID,body:AmendPipeline,db:Session=Depends(get_db),user:User=Depends(admin)):
    row=job_or_404(db,id,True)
    if row.revision!=body.revision or row.status in ('queued','running'):raise HTTPException(409,'流程执行中或版本已变化，请刷新')
    patch=body.model_dump(mode='json',exclude_unset=True,exclude={'revision','material_ids'})
    patch={k:v for k,v in patch.items() if v is not None}
    if body.material_ids is not None:patch['materials']=materials(db,body.material_ids)
    if not patch:raise HTTPException(422,'请至少提供一项补充信息')
    if row.status=='cancelled':raise HTTPException(409,'已取消的流程不再修改，请新建工作流')
    if set(patch)&{'confirmed_scope','materials','search_replay','search_mode','search_boundary'}:
        previous=PipelineStore(directory(id)).read()['inputs'].get('v19_scope_mapping')
        mapping=patch.get('v19_scope_mapping') or previous
        if mapping:patch['v19_scope_mapping']={**mapping,'reviewed':False}
    try:validate_handoffs(row.project_id,row.outcome_id,patch)
    except ValueError as exc:raise HTTPException(422,str(exc))
    restart='wu_intake' if set(patch)&{'confirmed_scope','materials'} else 'search_replay' if set(patch)&{'search_replay','search_mode','search_boundary'} else 'v19_evaluation'
    try:PipelineStore(directory(id)).amend(patch,restart)
    except (ValueError,FileExistsError) as exc:raise HTTPException(409,str(exc))
    row.status='queued';row.error='';row.revision+=1
    db.add(Audit(actor=user.id,action='pipeline_amend',target=row.id));db.commit()
    return summary(row)


@router.get('/{id}/artifact')
def artifact(id:UUID,path:str=Query(...,max_length=500),db:Session=Depends(get_db)):
    job_or_404(db,id)
    root=directory(id);file=(root/path).resolve()
    if not file.is_relative_to(root) or not file.is_file() or file.suffix not in ARTIFACT_SUFFIXES:
        raise HTTPException(404,'底稿文件不存在')
    return FileResponse(file,filename=file.name,media_type='application/octet-stream')
