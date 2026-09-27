"""Pin ordinary rule versions, and resume archived jobs with their original code."""
import os
import re
import subprocess
import sys
from pathlib import Path
from .pipeline_store import PipelineStore, WaitingForInput
from .config import settings

CURRENT='grading-20260927-coordinated-v5'
LEGACY='grading-20260927-audit-v3'


def dispatch_archived(root):
    store=PipelineStore(root);state=store.read()
    version=state['inputs'].get('runtime_version')
    if version is None:
        record=state['stages'].get('wu_evaluation',{})
        if record.get('status')=='succeeded':
            import json
            path=(store.root/record['output']).resolve()
            if not path.is_relative_to(store.root):raise ValueError('运行产物路径异常')
            version=json.loads(path.read_text(encoding='utf-8')).get('grading_standard')
        if not version:
            raise WaitingForInput('旧任务未记录运行版本，不能推测并用新规则续跑；请依据原运行记录指定归档版本，或另建评价',{'runtime_version':None})
    if version==CURRENT:return None
    if not re.fullmatch(r'[a-zA-Z0-9_.-]+',version):raise ValueError('无效的运行版本')
    base=Path(settings().storage_dir)/'evaluation-runtimes'/version
    if not (base/'backend/app/pipeline_service.py').is_file():
        raise WaitingForInput('该任务的原运行版本未安装，不能用新规则续跑；请恢复归档运行包或创建新评价',{'runtime_version':version})
    env={**os.environ,'PYTHONPATH':str(base/'backend'),'PYTHONIOENCODING':'utf-8'}
    code='from app.pipeline_service import run_pipeline; import sys; run_pipeline(sys.argv[1])'
    kw={'creationflags':subprocess.CREATE_NO_WINDOW} if os.name=='nt' else {}
    completed=subprocess.run([sys.executable,'-c',code,str(store.root)],cwd=base/'backend',env=env,**kw)
    if completed.returncode:raise ValueError('归档版本执行失败，原始阶段日志已保留')
    return store.read()
