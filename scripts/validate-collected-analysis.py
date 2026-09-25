"""Revalidate real model analysis after moving collector-owned metadata out of model output.
Preserve the original response and record every metadata normalization; never edit judgments.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.pipeline_search import finalize_collected_search
from app.pipeline_search_collection import analysis_model,excerpt_bank
from app.pipeline_store import atomic_json,implementation_fingerprint

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--collection',type=Path,required=True);p.add_argument('--analysis',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    origin=a.collection.resolve();analysis_root=a.analysis.resolve();folder=a.output.resolve()
    payload=json.loads((origin/'input.json').read_text(encoding='utf-8'));collected=payload.pop('collected')
    for r in collected['primary_source_receipts']['sources']:
        if r.get('raw_file') and hashlib.sha256((origin/'primary-sources'/r['raw_file']).read_bytes()).hexdigest()!=r['sha256']:raise ValueError('原始响应发生变化')
        if r.get('text_file') and (origin/'primary-sources'/r['text_file']).read_text(encoding='utf-8')!=collected['primary_source_texts'][r['id']]:raise ValueError('文本与实际归档不一致')
    raw=(analysis_root/'response.json').read_bytes();value=json.loads(raw)
    model=analysis_model([c['id'] for c in payload['intake']['claims']],[c['id'] for c in collected['search']['candidates']],[e['id'] for e in excerpt_bank(collected)])
    changes=[]
    for source in value['sources']:
        changes.append({'source_id':source['id'],'model_url':source.pop('url',None),'model_accessed_at':source.pop('accessed_at',None),
                        'reason':'URL取实际检索候选；采集日期取实际receipt并统一本地时区。科学判断与日期未知状态不修改。'})
    analysis=model.model_validate(value)
    folder.mkdir(parents=True,exist_ok=False)
    for name in ('public-search','primary-sources'):shutil.copytree(origin/name,folder/name)
    (folder/'original-model-response.json').write_bytes(raw)
    atomic_json(folder/'normalization-audit.json',{'collection':str(origin),'analysis':str(analysis_root),'new_http_requests':False,'new_model_call':False,
        'model_response_sha256':hashlib.sha256(raw).hexdigest(),'implementation_fingerprint':implementation_fingerprint(),'metadata_changes':changes})
    scope={'project_id':payload['project_id'],'outcome_id':payload['outcome_id'],'intake':payload['intake']}
    boundary={k:payload[k] for k in ('project_start_date','review_cutoff','cutoff_basis')}
    result=finalize_collected_search(scope,boundary,payload,collected,folder,analysis)
    result.update(collection_reused=True,collection_origin=str(origin),analysis_origin=str(analysis_root),execution_mode='revalidated_model_output')
    atomic_json(folder/'output.json',result)
    print(json.dumps({'status':'validated','sources':len(result['raw_result']['sources']),'formal_evidence':len(result['replay']['evidence']),'findings':len(result['replay']['findings'])},ensure_ascii=False))
