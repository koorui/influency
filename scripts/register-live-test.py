"""Register a verified multi-attempt real test as a reviewable, unpublished pipeline.
All original failures and model responses stay preserved at their source locations.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.pipeline_store import PipelineStore,atomic_json,fingerprint,timestamp
from app.pipeline_v19 import wrapper,export_stage
from app.pipeline_api import directory
from app.db import Session
from app.models import PipelineJob,Material,User,Audit,uid,now
from sqlalchemy import select

def read(path):return json.loads(path.read_text(encoding='utf-8'))
def copy(source,destination):
    shutil.copytree(source,destination,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--downstream',type=Path,required=True);p.add_argument('--search',type=Path,required=True);p.add_argument('--v19',type=Path,required=True);p.add_argument('--tables',type=Path,required=True);p.add_argument('--supersede-registration',action='store_true');a=p.parse_args()
    downstream,search,v19,tables=[x.resolve() for x in (a.downstream,a.search,a.v19,a.tables)]
    previous=read(downstream/'registered-pipeline.json') if (downstream/'registered-pipeline.json').exists() else None
    if previous and not a.supersede_registration:raise ValueError('本次测试已注册，避免重复创建')
    journal=read(downstream/'test-run.json');inputs=read(downstream/'inputs.json');upstream=read(downstream/'upstream.json')
    outputs={'wu_intake':upstream['wu_intake'],'search_replay':read(search/'output.json')}
    if fingerprint(outputs['search_replay'])!=fingerprint(upstream['search_replay']):raise ValueError('Search与实际下游输入不一致')
    for name in ('attribution','wu_evaluation'):
        value=read(downstream/name/'output.json');record=journal['stages'][name]
        if record['status']!='succeeded' or fingerprint(value)!=record['output_hash']:raise ValueError('下游阶段未成功或内容被修改')
        outputs[name]=value
    recovered=read(v19/'recovery.json');outputs['v19_evaluation']=read(v19/'output.json')
    if recovered['status']!='succeeded' or fingerprint(outputs['v19_evaluation'])!=recovered['output_hash']:raise ValueError('v19恢复结果不完整')
    workspace=read(v19/'workspace.json')
    if fingerprint(workspace)!=recovered['workspace_hash'] or not wrapper().validate_result(outputs['v19_evaluation']['result'])['valid']:raise ValueError('v19工作区或结果校验失败')
    provenance=workspace['pipeline_provenance']
    expected=[fingerprint(outputs['wu_intake']),fingerprint(outputs['search_replay']['replay']),fingerprint(outputs['attribution'])]
    if [provenance[k] for k in ('intake_hash','search_hash','attribution_hash')]!=expected:raise ValueError('v19与本次上游证据链不一致')
    if {o['outcome_id'] for o in outputs['v19_evaluation']['result']['outcomes']}!={provenance['frozen_child_id']}:raise ValueError('v19扩大了冻结成果范围')
    raw=outputs['search_replay']['raw_result'];enriched=read(tables/'enriched-search-result.json')
    if {k:v for k,v in enriched.items() if k!='research_records'}!={k:v for k,v in raw.items() if k!='research_records'}:
        raise ValueError('专门表格补充改变了原Search科学判断')
    texts={m['id']:re.sub(r'\s+','',m['text']) for m in inputs['materials']}
    for evidence in outputs['wu_intake']['intake']['evidence']:
        if evidence['material_id'] not in texts or re.sub(r'\s+','',evidence['quote']) not in texts[evidence['material_id']]:raise ValueError('成果定位引用未对应原材料')
    source_manifest=read(ROOT/'backend/storage/raman-case-source-v1/source-manifest.json')
    digest=hashlib.sha256()
    with Path(source_manifest['original']).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    if digest.hexdigest()!=source_manifest['original_sha256']:raise ValueError('原始项目PDF已经变化')
    # Registration restores the already used Search boundary for the management form.
    # It does not claim that all stages were freshly executed at registration time.
    inputs['search_boundary']={k:raw[k] for k in ('project_start_date','review_cutoff','cutoff_basis')}
    inputs['title']='拉曼探针 · 新Search完整实测（待审核）'
    os.chdir(ROOT/'backend')
    with Session() as db:
        user=db.scalar(select(User).where(User.username=='admin',User.role=='admin'))
        if not user:raise ValueError('管理员账号不存在')
        for m in inputs['materials']:
            stored=db.get(Material,m['id'])
            if not stored or stored.text!=m['text'] or stored.sha256!=m['sha256'] or stored.purpose!='project':raise ValueError('材料库与测试输入不一致或用途不是项目材料')
        identifier=uid();store=PipelineStore(directory(identifier));state=store.create(inputs)
        source_dirs={'wu_intake':Path(journal['intake_source']).parent,'search_replay':search,'attribution':downstream/'attribution','wu_evaluation':downstream/'wu_evaluation','v19_evaluation':v19}
        for name,source in source_dirs.items():
            destination=store.root/name/'attempt-1';destination.parent.mkdir(exist_ok=True)
            copy(source,destination)
            atomic_json(destination/'output.json',outputs[name])
            state['stages'][name]={'status':'succeeded','attempts':1,'output':f'{name}/attempt-1/output.json','output_hash':fingerprint(outputs[name]),
                'finished_at':timestamp(),'execution_mode':'verified_external_run','source_run':str(source)}
        copy(tables,store.root/'search_replay/attempt-1/required-tables')
        search_origin=Path(outputs['search_replay']['collection_origin']);analysis_origin=Path(outputs['search_replay']['analysis_origin'])
        copy(search_origin,store.root/'search_replay/attempt-1/collection-history')
        copy(analysis_origin,store.root/'search_replay/attempt-1/analysis-history')
        export_folder=store.root/'export/attempt-1';export_folder.mkdir(parents=True)
        exported=export_stage(inputs,outputs,export_folder);atomic_json(export_folder/'output.json',exported)
        state['stages']['export']={'status':'succeeded','attempts':1,'output':'export/attempt-1/output.json','output_hash':fingerprint(exported),'finished_at':timestamp()}
        state['status']='succeeded'
        state['verified_test_import']={'registered_at':timestamp(),'downstream_run':str(downstream),'v19_recovery':str(v19),'search_run':str(search),
            'table_supplement':str(tables),'original_downstream_implementation':journal['implementation_fingerprint'],'v19_recovery_implementation':recovered['implementation_fingerprint'],
            'boundary':'成果定位复用并核对原材料；Search为本次真实采集的已验证解释；下游实际执行；v19失败单元补跑，逐调用记录复用与新执行。并非一次无失败的自动运行。',
            'published':False}
        if previous:state['verified_test_import']['supersedes_registration']=previous['pipeline_id']
        atomic_json(store.path,state)
        shutil.copyfile(ROOT/'docs/raman-review-date-audit.md',store.root/'review-date-audit.md')
        row=PipelineJob(id=identifier,title=inputs['title'],project_id=inputs['project_id'],outcome_id=inputs['outcome_id'],created_by=user.id,status='succeeded',finished_at=now())
        db.add(row);db.add(Audit(actor=user.id,action='import_verified_live_test',target=identifier))
        if previous:
            old=db.get(PipelineJob,previous['pipeline_id'])
            if old:old.title='拉曼探针 · 旧版回挂记录（已保留历史）'
            db.add(Audit(actor=user.id,action='supersede_test_view',target=previous['pipeline_id']))
        db.commit()
        registration={'pipeline_id':identifier,'pipeline_dir':str(store.root),'status':'succeeded','published':False}
        if previous:atomic_json(downstream/f"registered-pipeline-history-{previous['pipeline_id']}.json",previous)
        atomic_json(downstream/'registered-pipeline.json',registration)
        print(json.dumps(registration,ensure_ascii=False))
