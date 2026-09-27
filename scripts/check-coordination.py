"""Real editorial check against saved evidence, without rewriting published reports."""
import argparse
import json
import sys
from pathlib import Path
parser=argparse.ArgumentParser()
parser.add_argument('--runtime',type=Path,required=True)
parser.add_argument('--pipeline',required=True)
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--saved-response',type=Path)
args=parser.parse_args()
sys.path.insert(0,str(args.runtime/'backend'))
from app.pipeline_store import PipelineStore,atomic_json
from app.project_service import job_directory
from app.unified_evaluation import combine_evaluations
from app.evaluation_coordination import coordinate_report
from app.codex_adapter import to_report
from app.skill_loader import contract
args.output.mkdir(parents=True,exist_ok=False)
state=PipelineStore(job_directory(args.pipeline)).read()
outputs={}
for name in ('wu_intake','search_replay','attribution','wu_evaluation','v19_evaluation'):
    record=state['stages'][name]
    if record['status']!='succeeded':raise ValueError('Source stage incomplete: '+name)
    outputs[name]=json.loads((job_directory(args.pipeline)/record['output']).read_text(encoding='utf-8'))
before=combine_evaluations(outputs['wu_evaluation'],outputs['v19_evaluation'])
atomic_json(args.output/'status.json',{'status':'running','source_pipeline':args.pipeline,'fresh_search':False,'published':False})
try:
    final,receipt=coordinate_report(state['inputs'],outputs,args.output/'coordination',before,saved_response=args.saved_response)
    atomic_json(args.output/'management-final.json',final)
    combined=combine_evaluations(final,outputs['v19_evaluation'])
    combined={k:v for k,v in combined.items() if k not in ('management_layer','dimension_layer')}
    combined['coordination']=receipt
    assessment=contract.FinalAssessment.model_validate(final['assessment'])
    report=to_report(assessment,[assessment.outcome_resolution.canonical_name]).model_dump(mode='json')
    report['rule_version']=final['grading_standard']
    atomic_json(args.output/'report.json',{'id':'coordination-preview','title':report['title'],
        'project_name':report['project_name'],'project_id':final['project_id'],'payload':report,
        'v19':outputs['v19_evaluation']['result'],'unified':combined,'published_at':None})
    atomic_json(args.output/'status.json',{'status':'succeeded','source_pipeline':args.pipeline,
        'fresh_search':False,'published':False,'management_before':before['levels']['management_level'],
        'management_after':combined['levels']['management_level'],'differences_before':len(before['differences']),
        'differences_after':len(combined['differences']),'quality':receipt['quality']})
except Exception as exc:
    atomic_json(args.output/'status.json',{'status':'failed','error':str(exc),'published':False})
    raise
