"""One real transport probe with an explicitly insufficient-evidence fixture.
It tests local authentication and JSON transport, not a project's impact grade.
"""
import argparse
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.v19_codex_transport import CodexV19Client
from app.pipeline_store import atomic_json

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True,type=Path);a=p.parse_args()
    if a.output.exists():raise SystemExit('Choose a new test directory; do not overwrite a previous run')
    client=CodexV19Client(a.output,timeout=180)
    result=client.chat_json('这只是v19接口连通测试，不是科研评价。没有任何证据。仅返回 {"status":"待核验","grade":{"level":"待确认","reason":"未提供科研证据","source_ids":[]}}，不得给出G1或L级。','{"test_only":true,"evidence":[]}',model='gpt-6-astra')
    if not result.ok:raise SystemExit(result.error)
    from app.pipeline_v19 import wrapper
    wrapper()
    from metric_judgment.indicator_product import _normalize_level
    normalized=_normalize_level(result.data.get('grade'),'G',require_sources=True)
    assert normalized['level']=='待确认'
    atomic_json(a.output/'verification.json',{'success':True,'model':result.model,'raw_result':result.data,'engine_normalized_grade':normalized,'test_only':True})
    print('Real Codex v19 transport succeeded; pending grade preserved.',flush=True)
