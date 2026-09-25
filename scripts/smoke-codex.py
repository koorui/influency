"""Explicit live CLI smoke check using clearly synthetic, insufficient-context data.
Run from the project root with the project venv. Never produces a publishable result.
"""
import sys
import uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.codex_adapter import CodexAdapter
from app.config import settings

if __name__=='__main__':
    settings().codex_search=False
    settings().storage_dir=str(Path(__file__).resolve().parents[1]/'backend/storage')
    task_id=str(uuid.uuid4())
    print('Live smoke task:',task_id,flush=True)
    result=CodexAdapter().evaluate('接口连通性样本',['接口验证'],[{
        'id':str(uuid.uuid4()),'filename':'connectivity-fixture.txt',
        'text':'这是一份虚构接口测试文件。未提供项目名称、项目编号、科研成果事实或实验结果。不得将此测试文件视为正式科研成果。'
    }],task_id=task_id,attempt=1)
    assert result.level is None
    assert result.evaluation_status == 'insufficient_project_context'
    print('PASS: real CLI returned a validated insufficient-context assessment; no level assigned.')
