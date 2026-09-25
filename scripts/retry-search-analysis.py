"""Retry interpretation of one real collection without repeating or relabelling HTTP requests."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.pipeline_search import assess_collected_search
from app.pipeline_store import atomic_json,implementation_fingerprint

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--collection',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    origin=args.collection.resolve();folder=args.output.resolve()
    payload=json.loads((origin/'input.json').read_text(encoding='utf-8'))
    collected=payload.pop('collected')
    if 'primary_source_texts' not in collected:raise ValueError('This retry requires the original complete source-text collection')
    for receipt in collected['primary_source_receipts']['sources']:
        if receipt.get('raw_file'):
            if hashlib.sha256((origin/'primary-sources'/receipt['raw_file']).read_bytes()).hexdigest()!=receipt['sha256']:raise ValueError('原文归档已变化')
        if receipt.get('text_file'):
            actual=(origin/'primary-sources'/receipt['text_file']).read_text(encoding='utf-8')
            if actual!=collected['primary_source_texts'][receipt['id']]:raise ValueError('正文输入与归档不一致')
    folder.mkdir(parents=True,exist_ok=False)
    for name in ('public-search','primary-sources'):
        shutil.copytree(origin/name,folder/name)
    atomic_json(folder/'collection-origin.json',{'collection':str(origin),'new_http_requests':False,
        'search_date':payload['search_date'],'implementation_fingerprint':implementation_fingerprint(),
        'boundary':'本次仅重试同一真实采集的解释，不冒充再次联网或另一次独立搜索。'})
    scope={'project_id':payload['project_id'],'outcome_id':payload['outcome_id'],'intake':payload['intake']}
    boundary={k:payload[k] for k in ('project_start_date','review_cutoff','cutoff_basis')}
    result=assess_collected_search(scope,boundary,payload,collected,folder)
    result['collection_reused']=True;result['collection_origin']=str(origin)
    atomic_json(folder/'output.json',result)
    print(json.dumps({'status':'validated','new_http_requests':False,'evidence':len(result['replay']['evidence'])},ensure_ascii=False))
