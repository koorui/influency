"""Re-run one failed v19 request through the current transport; preserve the failed call."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.v19_codex_transport import CodexV19Client
from app.pipeline_v19 import wrapper
from app.pipeline_store import atomic_json,fingerprint

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source-call',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    original=json.loads((a.source_call/'input.json').read_text(encoding='utf-8'))
    manifest=json.loads((a.source_call/'request-manifest.json').read_text(encoding='utf-8'))
    if fingerprint(original)!=manifest['input_hash']:raise ValueError('原始调用输入已变化')
    folder=a.output.resolve();folder.mkdir(parents=True,exist_ok=False)
    wrapper()
    client=CodexV19Client(folder/'calls')
    response=client.chat_json(original['v19_system_prompt'],json.dumps(original['v19_input'],ensure_ascii=False),model=manifest['model'])
    if not response.ok:raise ValueError(response.error)
    from metric_judgment.indicator_product import _dimension_output_error
    dimension=original['v19_input']['dimension']['question_id']
    error=_dimension_output_error(response.data,dimension)
    if error:raise ValueError(error)
    atomic_json(folder/'retry-validation.json',{'status':'validated','source_call':str(a.source_call.resolve()),'input_hash':fingerprint(original),
        'model':response.model,'dimension':dimension,'transport_change':'direct typed JSON object; original v19 prompt and inputs unchanged'})
    print(json.dumps({'status':'validated','dimension':dimension},ensure_ascii=False))
