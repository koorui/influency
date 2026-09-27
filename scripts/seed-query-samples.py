"""Create idempotent, clearly-labelled query samples for local acceptance testing."""
from __future__ import annotations

import copy
import json
import shutil
from pathlib import Path

from app.config import settings
from app.db import Session
from app.evaluator import MockAdapter
from app.models import PipelineJob, Project, Result, ResultVersion, User, uid, now
from app.pipeline_store import atomic_json
from sqlalchemy import select


SAMPLES = [
    ("拉曼探针", ["拉曼探针", "拉曼", "光谱", "生物成像"]),
    ("NMR谱图智能解析", ["NMR", "核磁共振", "谱图解析", "结构识别"]),
    ("有机分子性质预测模型", ["分子性质", "机器学习", "有机化学", "性质预测"]),
    ("反应路线智能规划", ["逆合成", "反应路线", "合成规划", "化学反应"]),
    ("多模态光谱数据分析", ["光谱分析", "多模态", "数据处理", "谱学"]),
    ("自动化合成实验设计", ["自动化实验", "合成设计", "实验规划", "AI4S"]),
]


def main():
    with Session() as db:
        project = db.scalar(select(Project).order_by(Project.created_at).limit(1))
        user = db.scalar(select(User).where(User.role == 'admin').limit(1))
        source = db.scalar(select(PipelineJob).where(PipelineJob.status == 'succeeded').order_by(PipelineJob.created_at).limit(1))
        if not project or not user:
            raise SystemExit('需要已有项目和管理员账户')
        source_root = (Path(settings().storage_dir) / 'pipelines' / source.id).resolve() if source else None
        source_state = json.loads((source_root / 'pipeline.json').read_text(encoding='utf-8')) if source_root else {
            'schema_version':'impact-pipeline.v1','created_at':now().isoformat(),'status':'succeeded',
            'inputs':{},'stages':{name:{'status':'succeeded','attempts':1,'output':f'{name}/attempt-1/output.json','output_hash':''} for name in ('wu_intake','search_replay','attribution','wu_evaluation','v19_evaluation','export')}}
        created = []
        for title, keywords in SAMPLES:
            full_title = f'{title} · 查询演示样例'
            if db.scalar(select(Result.id).where(Result.title == full_title)):
                continue
            job_id = uid()
            root = (Path(settings().storage_dir) / 'pipelines' / job_id).resolve()
            if source_root: shutil.copytree(source_root, root)
            else: root.mkdir(parents=True)
            state = copy.deepcopy(source_state)
            state['inputs']['title'] = full_title
            state['inputs']['project_name'] = project.name
            state['inputs']['project_id'] = project.code
            state['status'] = 'succeeded'
            state['schema_version'] = 'impact-pipeline.v1'
            if not source_root:
                for stage in state['stages']:
                    output_dir=root/stage/'attempt-1'; output_dir.mkdir(parents=True,exist_ok=True)
                    value={'demo':True,'stage':stage,'title':full_title}
                    atomic_json(output_dir/'output.json',value)
                    state['stages'][stage]['output_hash']='demo'
            # Preserve the source evidence only as a rendering fixture; the report is explicitly demo-labelled.
            atomic_json(root / 'pipeline.json', state)
            row = PipelineJob(id=job_id, project_ref=project.id, title=full_title,
                              project_id=project.code, outcome_id=f'DEMO-{job_id[:8]}',
                              created_by=user.id, status='succeeded', started_at=now(), finished_at=now())
            payload = MockAdapter().evaluate(full_title, keywords, []).model_dump()
            payload['project_name'] = project.name
            payload['summary'] = '查询演示样例：仅用于验证成果检索、报告列表和页面展示，不代表真实科研评价。'
            payload['is_demo'] = True
            result = Result(id=uid(), project_id=project.id, pipeline_id=job_id, title=full_title,
                            search_text=' '.join([full_title, *keywords]), payload=payload,
                            status='published', published_at=now(), reviewed_by=user.id)
            db.add(row); db.add(result); db.flush()
            db.add(ResultVersion(result_id=result.id, revision=1, payload=payload, editor=user.id))
            created.append({'title': full_title, 'result_id': result.id, 'keywords': keywords})
        db.commit()
        print(json.dumps({'project': project.name, 'created': created, 'created_count': len(created)}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
