"""Convert an explicitly routed v19 outcome's historical Search packet, without searching.
Record text remains labelled as upstream ledger content, never a quote from a linked website.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app.pipeline_contracts import SearchReplay


def convert(workspace,outcome_id,run_id,completed_at,source_label):
    project_id=workspace.get('project_profile',{}).get('project_id')
    packet=workspace.get('evidence_adapter',{}).get('outcome_packets',{}).get(outcome_id)
    if not project_id or not packet or packet.get('outcome_id')!=outcome_id:raise ValueError('必须指定工作区中显式绑定的成果ID')
    claims=packet.get('external_search') or []
    evidence=[];findings=[];seen=set()
    for index,row in enumerate(claims):
        serialized=json.dumps(row,ensure_ascii=False,sort_keys=True)
        digest=hashlib.sha256(serialized.encode()).hexdigest()
        if digest in seen:continue
        seen.add(digest)
        id='REPLAY-'+digest[:24]
        evidence.append({'id':id,'project_id':project_id,'outcome_id':outcome_id,'source_type':'search',
            'locator':f'/evidence_adapter/outcome_packets/{outcome_id}/external_search/{index}',
            'text':'历史上游Search台账记录（不是所引网页逐字原文；本次未重新核验）：\n'+serialized,'url':None})
        if row.get('evidence_effect')=='反驳':
            findings.append({'id':'F-'+digest[:24],'status':'conflicts','statement':row.get('key_difference') or row.get('verdict') or '历史Search记录标记反驳',
                'reason':'原交付的 evidence_effect 明确为反驳；未将历史发现重新解释为当前事实',
                'related_claim_ids':[],'evidence_ids':[id]})
    return SearchReplay.model_validate({'schema_version':'search-replay.v1','project_id':project_id,'outcome_id':outcome_id,'mode':'historical_replay',
        'original_run_id':run_id,'original_completed_at':completed_at,'source_label':source_label,'evidence':evidence,'findings':findings})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True);p.add_argument('--outcome-id',required=True)
    p.add_argument('--original-run-id',required=True);p.add_argument('--completed-at',required=True,help='Original search completion date; use unknown when the source does not establish it')
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=convert(json.loads(a.workspace.read_text(encoding='utf-8-sig')),a.outcome_id,a.original_run_id,a.completed_at,
        a.workspace.name+'; SHA256='+hashlib.sha256(a.workspace.read_bytes()).hexdigest())
    with a.output.open('x',encoding='utf-8') as f:json.dump(result.model_dump(),f,ensure_ascii=False,indent=2)
    print(f'Exported {len(result.evidence)} historical records. No live Search executed.')
