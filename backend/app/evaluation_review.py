"""Project-scoped, version-bound review; system reports never sign themselves."""
from datetime import date
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from .auth import current_user, admin
from .db import get_db
from .schema import StrictModel
from .models import (Result, ResultVersion, ReviewAssignment, ReviewDecision, EvaluationFollowup,
    User, Project, PipelineJob, Ticket, OutcomeSubmission, Audit, uid, now)
from .project_service import allowed_projects, require_project, stage_output, create_ticket_job, job_directory, ticket_data
from .pipeline_store import PipelineStore, atomic_json

router=APIRouter(prefix='/api')


def report_access(db,user,identifier,revision=None):
    row=db.scalar(select(Result).where(Result.id==str(identifier),Result.status=='published',
        Result.project_id.in_(allowed_projects(user))).with_for_update())
    if row is None:raise HTTPException(404,'报告不存在或无权访问')
    if revision is not None and row.revision!=revision:raise HTTPException(409,'报告版本已变化，请刷新后重新审阅')
    return row


def assigned(db,user,row):
    return bool(db.scalar(select(ReviewAssignment.id).where(ReviewAssignment.result_id==row.id,
        ReviewAssignment.user_id==user.id,ReviewAssignment.active==1)))


def decision_data(row):
    return {k:getattr(row,k) for k in ('id','result_revision','sequence','user_id','fact_id','verdict','reason','evidence_ids','created_at')}


def task_data(row):
    return {k:getattr(row,k) for k in ('id','result_revision','source_key','title','kind','body','status','revision','owner_id','deadline','resolution_refs','updated_at')}


def review_state(db,row):
    decisions=list(db.scalars(select(ReviewDecision).where(ReviewDecision.result_id==row.id,
        ReviewDecision.result_revision==row.revision).order_by(ReviewDecision.sequence)))
    overall=[d for d in decisions if d.fact_id=='__overall__']
    # Any later factual review invalidates an older overall sign-off.
    latest={(d.fact_id,d.user_id):d for d in decisions}
    confirmed=bool(overall and decisions[-1].id==overall[-1].id and overall[-1].verdict=='confirmed'
        and all(d.verdict=='confirmed' for d in latest.values()))
    return {'adjudication_status':'expert_confirmed' if confirmed else 'system_preliminary',
        'decisions':[decision_data(d) for d in decisions]}


@router.get('/reports/{id}/review')
def get_review(id:UUID,db:Session=Depends(get_db),user:User=Depends(current_user)):
    row=report_access(db,user,id)
    tasks=list(db.scalars(select(EvaluationFollowup).where(EvaluationFollowup.result_id==row.id,
        EvaluationFollowup.result_revision==row.revision).order_by(EvaluationFollowup.updated_at)))
    return {'revision':row.revision,**review_state(db,row),'can_review':assigned(db,user,row),
        'can_assign':user.role=='admin','tasks':[task_data(t) for t in tasks],
        'assignments':[{'user_id':a.user_id,'username':db.get(User,a.user_id).username,'active':bool(a.active)}
            for a in db.scalars(select(ReviewAssignment).where(ReviewAssignment.result_id==row.id))]}


class AssignmentInput(StrictModel):
    revision:int
    username:str=Field(min_length=1,max_length=80)
    active:bool=True


@router.post('/reports/{id}/reviewers')
def assign_reviewer(id:UUID,body:AssignmentInput,db:Session=Depends(get_db),user:User=Depends(admin)):
    row=report_access(db,user,id,body.revision)
    reviewer=db.scalar(select(User).where(User.username==body.username))
    if reviewer is None:raise HTTPException(404,'审阅账号不存在')
    require_project(db,reviewer,row.project_id)
    assignment=db.scalar(select(ReviewAssignment).where(ReviewAssignment.result_id==row.id,ReviewAssignment.user_id==reviewer.id))
    if assignment is None:
        assignment=ReviewAssignment(result_id=row.id,user_id=reviewer.id,assigned_by=user.id);db.add(assignment)
    assignment.active=int(body.active);assignment.assigned_by=user.id
    db.add(Audit(actor=user.id,action='reviewer_assigned' if body.active else 'reviewer_revoked',target=row.id));db.commit()
    return get_review(id,db,user)


class DecisionInput(StrictModel):
    revision:int
    fact_id:str=Field(min_length=1,max_length=80)
    verdict:Literal['confirmed','partial','insufficient','conflict']
    reason:str=Field(min_length=1,max_length=10000)
    evidence_ids:list[str]=Field(default_factory=list,max_length=200)


@router.post('/reports/{id}/decisions',status_code=201)
def record_decision(id:UUID,body:DecisionInput,db:Session=Depends(get_db),user:User=Depends(current_user)):
    row=report_access(db,user,id,body.revision)
    if not assigned(db,user,row):raise HTTPException(403,'尚未被指定为本报告审阅人')
    facts=(row.payload.get('fact_ledger') or {}).get('impact_facts',[])
    if body.fact_id!='__overall__' and body.fact_id not in {f['id'] for f in facts}:raise HTTPException(422,'事实不属于本评价版本')
    evidence={e['id'] for e in row.payload.get('evidence',[])}
    if set(body.evidence_ids)-evidence:raise HTTPException(422,'复核引用了本报告之外的证据，请提交材料后重新核验')
    if not body.reason.strip():raise HTTPException(422,'请说明事实判断及依据')
    if body.verdict=='confirmed' and not body.evidence_ids:raise HTTPException(422,'确认须引用本轮证据')
    if body.fact_id=='__overall__' and body.verdict=='confirmed':
        from .project_api import report_comparison
        combined=report_comparison(db.get(PipelineJob,row.pipeline_id) if row.pipeline_id else None)
        if not row.payload.get('fact_ledger'):raise HTTPException(409,'历史报告须按新协议重新核验后确认')
        if not combined or combined.get('blocking_disagreement') or not combined.get('complete'):
            raise HTTPException(409,'关键分歧未处理，请确认事实并重新核验，再审阅新报告')
        latest={}
        for d in review_state(db,row)['decisions']:
            latest[(d['fact_id'],d['user_id'])]=d
        # A reviewer may supersede their own overall opinion, never another's objection.
        latest.pop(('__overall__',user.id),None)
        if any(d['verdict']!='confirmed' for d in latest.values()):raise HTTPException(409,'存在尚未解决的事实复核意见')
        if any(f.get('needs_expert_confirmation') and not any(key[0]==f['id'] and d['verdict']=='confirmed' for key,d in latest.items()) for f in facts):
            raise HTTPException(409,'请先逐项审阅需要专家确认的事实')
    sequence=(db.scalar(select(func.max(ReviewDecision.sequence)).where(ReviewDecision.result_id==row.id,ReviewDecision.result_revision==row.revision)) or 0)+1
    entry=ReviewDecision(result_id=row.id,result_revision=row.revision,sequence=sequence,user_id=user.id,
        fact_id=body.fact_id,verdict=body.verdict,reason=body.reason.strip(),evidence_ids=body.evidence_ids)
    db.add(entry);db.add(Audit(actor=user.id,action='expert_review_submitted',target=row.id));db.commit()
    return get_review(id,db,user)


class TaskCreate(StrictModel):
    revision:int
    source_index:int=Field(ge=0)


@router.post('/reports/{id}/followups',status_code=201)
def create_followup(id:UUID,body:TaskCreate,db:Session=Depends(get_db),user:User=Depends(current_user)):
    row=report_access(db,user,id,body.revision)
    suggestions=row.payload.get('follow_ups',[])
    if body.source_index>=len(suggestions):raise HTTPException(422,'任务不在本轮建议中')
    key=f'suggestion-{body.source_index}'
    task=db.scalar(select(EvaluationFollowup).where(EvaluationFollowup.result_id==row.id,
        EvaluationFollowup.result_revision==row.revision,EvaluationFollowup.source_key==key))
    if task is None:
        suggestion=suggestions[body.source_index]
        task=EvaluationFollowup(result_id=row.id,result_revision=row.revision,source_key=key,
            title=suggestion['title'],kind=suggestion['kind'],body=suggestion.get('body') or suggestion['detail'],edited_by=user.id)
        db.add(task);db.add(Audit(actor=user.id,action='followup_created',target=row.id));db.commit()
    return task_data(task)


class TaskEdit(StrictModel):
    result_revision:int
    revision:int
    body:str=Field(min_length=1,max_length=30000)
    status:Literal['draft','open','submitted','resolved','cancelled']
    deadline:str|None=None
    resolution_refs:list[str]=Field(default_factory=list)


@router.post('/reports/{id}/followups/{task_id}')
def save_followup(id:UUID,task_id:UUID,body:TaskEdit,db:Session=Depends(get_db),user:User=Depends(current_user)):
    row=report_access(db,user,id,body.result_revision)
    task=db.scalar(select(EvaluationFollowup).where(EvaluationFollowup.id==str(task_id),EvaluationFollowup.result_id==row.id).with_for_update())
    if not task:raise HTTPException(404,'任务不存在')
    if task.revision!=body.revision or task.result_revision!=row.revision:raise HTTPException(409,'任务已被更新，请重新打开')
    if body.deadline:
        try:date.fromisoformat(body.deadline)
        except ValueError:raise HTTPException(422,'截止日期格式应为YYYY-MM-DD')
    evidence={e['id'] for e in row.payload.get('evidence',[])}
    decisions={d['id'] for d in review_state(db,row)['decisions']}
    if set(body.resolution_refs)-(evidence|decisions):raise HTTPException(422,'解决依据不属于本轮证据或专家记录')
    if body.status=='resolved' and not body.resolution_refs:raise HTTPException(422,'解决任务须关联证据或复核记录')
    task.body=body.body;task.status=body.status;task.deadline=body.deadline or None
    task.resolution_refs=body.resolution_refs;task.revision+=1;task.edited_by=user.id;task.updated_at=now()
    db.add(Audit(actor=user.id,action='followup_saved',target=task.id));db.commit()
    return task_data(task)


class ReevaluateInput(StrictModel):
    revision:int
    request_key:UUID
    change_reason:Literal['new_facts','additional_evidence','correction','rule_change','scope_change']
    description:str=Field(default='',max_length=5000)
    expected_inputs:dict | None=None


def reevaluation_snapshot(db,project):
    from .project_service import selected_materials
    materials=selected_materials(db,project)
    return {'material_ids':[m['id'] for m in materials],
        'search_boundary':project.evaluation_config.get('search_boundary')},materials


@router.get('/reports/{id}/reevaluation-preview')
def reevaluation_preview(id:UUID,db:Session=Depends(get_db),user:User=Depends(current_user)):
    row=report_access(db,user,id)
    project=require_project(db,user,row.project_id)
    snapshot,materials=reevaluation_snapshot(db,project)
    previous=db.get(PipelineJob,row.pipeline_id) if row.pipeline_id else None
    intake=stage_output(previous,'wu_intake').get('intake',{}) if previous else {}
    return {'expected_inputs':snapshot,'materials':[{'id':m['id'],'filename':m['filename']} for m in materials],
        'previous_cutoff':row.payload.get('evaluation_cutoff'),
        'primary_object':next((o for o in intake.get('evaluation_objects',[]) if o['id']==intake.get('primary_object_id')),None)}


@router.post('/reports/{id}/reevaluate',status_code=201)
def reevaluate(id:UUID,body:ReevaluateInput,db:Session=Depends(get_db),user:User=Depends(current_user)):
    row=report_access(db,user,id,body.revision)
    if body.change_reason=='scope_change':raise HTTPException(422,'更换主对象请通过成果提交入口另评；此入口保持主对象')
    payload={'report_id':row.id,**body.model_dump(mode='json')}
    existing=db.scalar(select(OutcomeSubmission).where(OutcomeSubmission.created_by==user.id,OutcomeSubmission.request_key==str(body.request_key)))
    if existing:
        if existing.payload!=payload:raise HTTPException(409,'提交编号已用于不同请求')
        return ticket_data(db,db.get(Ticket,existing.ticket_id))
    project=require_project(db,user,row.project_id)
    expected,_=reevaluation_snapshot(db,project)
    if body.expected_inputs is not None and body.expected_inputs!=expected:
        raise HTTPException(409,'选用材料或评价截止日已变化，请重新预览后提交')
    previous=db.get(PipelineJob,row.pipeline_id)
    if previous is None:raise HTTPException(409,'历史报告没有可续接的成果对象，请通过成果提交入口重新核验')
    prior_intake=stage_output(previous,'wu_intake').get('intake',{})
    primary=next((o for o in prior_intake.get('evaluation_objects',[]) if o['id']==prior_intake.get('primary_object_id')),None)
    if primary is None:raise HTTPException(409,'历史报告未冻结主对象，请通过成果提交入口确认范围后重新核验')
    ticket=Ticket(id=uid(),project_id=row.project_id,owner='user:'+user.id,query=row.title,normalized_query=row.title.casefold())
    db.add(ticket);db.flush()
    job=create_ticket_job(db,project,ticket,user,body.description)
    store=PipelineStore(job_directory(job.id));state=store.read()
    if body.expected_inputs is not None and {'material_ids':[m['id'] for m in state['inputs']['materials']],
            'search_boundary':state['inputs'].get('search_boundary')}!=body.expected_inputs:
        raise HTTPException(409,'创建时材料发生变化，请刷新预览')
    state['inputs'].update(outcome_id=previous.outcome_id,supersedes_result_id=row.id,
        confirmed_scope=prior_intake['canonical_name'],
        frozen_primary_object={k:primary[k] for k in ('id','name','kind','relation_to_primary')},
        change_reason=body.change_reason,expert_fact_decisions=review_state(db,row)['decisions'])
    job.outcome_id=previous.outcome_id
    atomic_json(store.path,state)
    db.add(OutcomeSubmission(ticket_id=ticket.id,created_by=user.id,request_key=str(body.request_key),payload=payload,material_ids=[]))
    db.add(Audit(actor=user.id,action='report_reevaluation_requested',target=row.id));db.commit()
    return ticket_data(db,ticket)


@router.get('/reports/{id}/history')
def history(id:UUID,db:Session=Depends(get_db),user:User=Depends(current_user)):
    selected=report_access(db,user,id)
    job=db.get(PipelineJob,selected.pipeline_id) if selected.pipeline_id else None
    if job:
        reports=list(db.scalars(select(Result).join(PipelineJob,Result.pipeline_id==PipelineJob.id).where(
            Result.project_id==selected.project_id,Result.status=='published',
            PipelineJob.outcome_id==job.outcome_id).order_by(Result.published_at.desc(),Result.id)))
    else:reports=[selected]
    rows=[]
    for row in reports:
        current=selected.payload;prior=row.payload
        old_dims={d['id']:d.get('grade') for d in prior.get('dimension_audit',[])}
        current_dims={d['id']:d.get('grade') for d in current.get('dimension_audit',[])}
        old_facts={f['id']:f for f in (prior.get('fact_ledger') or {}).get('impact_facts',[])}
        current_facts={f['id']:f for f in (current.get('fact_ledger') or {}).get('impact_facts',[])}
        def fact_value(f):return {k:f.get(k) for k in ('fact_text','state','evidence_ids','counter_evidence_ids')}
        delta={'level_changed':prior.get('level')!=current.get('level'),
            'dimension_changes':[{'id':key,'from':old_dims.get(key),'to':current_dims.get(key)} for key in sorted(old_dims.keys()|current_dims.keys()) if old_dims.get(key)!=current_dims.get(key)],
            'changed_facts':sum(fact_value(old_facts.get(key,{}))!=fact_value(current_facts.get(key,{})) for key in old_facts.keys()|current_facts.keys()),
            'sources_before':len(prior.get('evidence',[])),'sources_current':len(current.get('evidence',[])),
            'comparison_target':selected.id,'is_current':row.id==selected.id}
        rows.append({'id':row.id,'revision':row.revision,'title':row.title,'published_at':row.published_at,
            'difference_to_current':delta,
            'level':row.payload.get('level'),'evaluation_cutoff':row.payload.get('evaluation_cutoff'),
            'change_reason':row.payload.get('history_context',{}).get('change_reason'),
            'rule_version':row.payload.get('rule_version')})
    return rows


@router.get('/reports/{id}/evidence/{evidence_id}/context')
def evidence_context(id:UUID,evidence_id:str,db:Session=Depends(get_db),user:User=Depends(current_user)):
    import re
    from .models import Material
    row=report_access(db,user,id)
    evidence=next((e for e in row.payload.get('evidence',[]) if e['id']==evidence_id),None)
    if not evidence or not evidence.get('material_id'):raise HTTPException(404,'此证据没有可预览的送检原文')
    material=db.get(Material,evidence['material_id'])
    if not material or material.project_id!=row.project_id:raise HTTPException(404,'材料不属于本报告项目')
    quote=evidence.get('excerpt') or '';text=material.text or ''
    at=text.find(quote) if quote else -1
    end=at+len(quote);mode='exact'
    if at<0 and quote.strip():
        compact=''.join(quote.split());position=''.join(text.split()).find(compact)
        if position>=0:
            for i,match in enumerate(re.finditer(r'\S',text)):
                if i==position:at=match.start()
                if i==position+len(compact)-1:
                    end=match.end();break
            mode='whitespace_only'
    if at<0:return {'matched':False,'before':'','quote':quote,'matched_text':'','after':'','filename':material.filename,
        'note':'未在当前提取文本中精确定位引文，请下载原文件按来源位置核对。'}
    return {'matched':True,'match_mode':mode,'before':text[max(0,at-600):at],'quote':quote,'matched_text':text[at:end],
        'after':text[end:end+600],'filename':material.filename,
        'note':('仅忽略空白差异定位。' if mode=='whitespace_only' else '原字符精确定位。')+'黄色部分是材料中首个匹配的原文片段；版式与页码以原文件为准。'}


@router.get('/reports/{id}/materials/{material_id}')
def report_material(id:UUID,material_id:UUID,db:Session=Depends(get_db),user:User=Depends(current_user)):
    from pathlib import Path
    from fastapi.responses import FileResponse
    from .config import settings
    from .models import Material
    row=report_access(db,user,id)
    if str(material_id) not in {e.get('material_id') for e in row.payload.get('evidence',[])}:
        raise HTTPException(404,'材料不属于本报告')
    material=db.get(Material,str(material_id))
    if not material or material.project_id!=row.project_id:raise HTTPException(404,'材料不存在')
    root=Path(settings().storage_dir).resolve();path=(root/material.storage_key).resolve()
    if not path.is_relative_to(root) or not path.is_file():raise HTTPException(404,'原文件不可访问，报告仍保留当时引文')
    return FileResponse(path,filename=material.filename,media_type='application/octet-stream')


@router.get('/reports/{id}/export')
def export_reviewed_report(id:UUID,db:Session=Depends(get_db),user:User=Depends(current_user)):
    import html
    from fastapi.responses import HTMLResponse
    from .project_api import report
    row=report_access(db,user,id);data=report(id,db,user);value=data['payload']
    esc=lambda v:html.escape(str(v or ''))
    status={'system_preliminary':'系统初步判断','expert_confirmed':'专家已确认','formal':'正式认定'}[value['adjudication_status']]
    evidence={e['id']:e for e in value.get('evidence',[])}
    def refs(ids):
        return ' '.join(f'<a href="#source-{esc(i)}">{esc(evidence[i]["title"])}</a>' for i in ids if i in evidence)
    sections=f'<h1>{esc(value["title"])}</h1><p>评价截止：{esc(value.get("evaluation_cutoff") or "历史记录未单列")} · {status} · 报告第{row.revision}版</p>'
    combined=data.get('unified') or {}
    sections+='<p>本报告以管理者判断为主结论，七维用于内部审查。系统建议不等于专家认定。</p>'
    coordination=combined.get('coordination') or {}
    sections+=f'<p>内部协调：{esc("已完成" if coordination.get("status")=="completed" else "本历史报告未运行新增协调步骤")}。</p>'
    if combined.get('differences'):
        sections+='<details><summary>内部审查保留意见</summary>'
        for item in combined['differences']:
            sections+=f'<p>{esc(item["field"])}：管理者依据：{esc(item.get("management_reason"))}；审查意见：{esc(item.get("dimension_reason"))}</p>'
        sections+='</details>'
    sections+=f'<h2>① 影响力判断</h2><h3>{esc("L"+str(value["level"]) if value.get("level") else "等级待核验")} {esc(value.get("level_name"))}</h3><p>{esc(value["summary"])}</p>'
    for i,reason in enumerate(value.get('reasons',[])):
        groups=value.get('reason_evidence_refs',[])
        sections+=f'<p>{esc(reason)} {refs(groups[i] if i<len(groups) else [])}</p>'
    sections+=f'<p>当前边界：{esc(value.get("boundary_gap"))}</p><h2>② 关键判断与证据</h2>'
    for judgment in value.get('dimensions',[]):
        sections+=f'<h3>{esc(judgment["topic"])}</h3><p>项目主张：{esc(judgment["claim"])} {refs(judgment.get("project_evidence_ids",[]))}</p><p>评价核验：{esc(judgment["assessment"])} {refs(judgment.get("evidence_ids",[]))}</p>'
    sections+='<h2>③ 下一步任务</h2>'
    tasks={t.source_key:t for t in db.scalars(select(EvaluationFollowup).where(EvaluationFollowup.result_id==row.id,EvaluationFollowup.result_revision==row.revision))}
    for i,suggestion in enumerate(value.get('follow_ups',[])):
        saved=tasks.get(f'suggestion-{i}')
        sections+=f'<h3>{esc(suggestion["title"])}</h3><pre>{esc(saved.body if saved else suggestion.get("body") or suggestion["detail"])}</pre>'
    sections+='<h2>证据原文与边界</h2>'
    for key,ev in evidence.items():
        sections+=f'<section id="source-{esc(key)}"><h3>{esc(ev["title"])}</h3><p>{esc(ev.get("source"))} · {esc(ev.get("locator"))}</p><blockquote>{esc(ev.get("excerpt"))}</blockquote><p>能证明：{esc(ev.get("supports"))}</p><p>不能证明：{esc(ev.get("does_not_prove"))}</p></section>'
        context=ev.get('source_context') or {}
        for field,label in (('event_date','事件日期'),('first_public_date','首次公开'),('accessed_at','取得日期')):
            if context.get(field):sections+=f'<p>{label}：{esc(context[field])}</p>'
    sections+='<h2>专家复核记录</h2>'
    for decision in review_state(db,row)['decisions']:
        name=db.get(User,decision['user_id']).username
        verdict={'confirmed':'有依据确认','partial':'部分支持','insufficient':'证据不足','conflict':'存在冲突'}[decision['verdict']]
        sections+=f'<p>{esc(name)} · {esc(decision["created_at"])} · {verdict}</p><p>{esc(decision["reason"])} {refs(decision["evidence_ids"])}</p>'
    sections+=f'<p>规则版本：{esc(value.get("rule_version") or "历史记录未单列")}</p>'
    document='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>成果评价报告</title><style>body{max-width:1000px;margin:32px auto;padding:20px;font:16px/1.8 system-ui;color:#284962}h2{margin-top:36px}pre,blockquote{white-space:pre-wrap;overflow-wrap:anywhere;background:#f4f8fc;padding:16px}p,a,h1,h3{overflow-wrap:anywhere}a{color:#316e9d}section{border-top:1px solid #dce5ee}</style>'+sections+'</html>'
    return HTMLResponse(document,headers={'Content-Disposition':'attachment; filename="outcome-report.html"'})
