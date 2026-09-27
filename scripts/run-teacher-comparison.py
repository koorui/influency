"""Run an authorized real evaluation against one frozen evidence packet.

Run inside the configured worker environment. Input is local private material;
outputs remain in storage, never in the repository or an external message.
"""
import argparse
import copy
import json
import sys
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('--runtime',type=Path,required=True)
parser.add_argument('--group',required=True)
parser.add_argument('--source',default='c6a13644-cdc1-4487-9d69-3eb92088d9d0')
parser.add_argument('--management-only',action='store_true')
args=parser.parse_args()
sys.path.insert(0,str(args.runtime/'backend'))
from app.config import settings
from app.pipeline_store import PipelineStore, atomic_json
from app.pipeline_stages import wu_evaluation_stage, attribution_stage
from app.pipeline_v19 import v19_evaluation_stage, export_stage
from app.skill_loader import contract

storage=Path(settings().storage_dir)
source=storage/'pipelines'/args.source
state=PipelineStore(source).read()
root=storage/'teacher-v4-comparison'/args.group
root.mkdir(parents=True,exist_ok=False)
sys.stdout=(root/'run.log').open('w',encoding='utf-8',buffering=1)
sys.stderr=sys.stdout
inputs=copy.deepcopy(state['inputs'])
outputs={name:json.loads((source/state['stages'][name]['output']).read_text(encoding='utf-8'))
         for name in ('wu_intake','search_replay','attribution')}
intake=outputs['wu_intake']['intake']
annotation=None
if not intake.get('primary_object_id'):
    annotation={'reason':'Historical schema lacks an object ID; explicitly evaluate the named probe product, not its design method.',
        'adds_new_evidence':False,'changes_card':False}
    intake['primary_object_id']='primary-product'
    intake['evaluation_objects']=[{'id':'primary-product','name':intake['canonical_name'],'kind':'探针产品',
        'version':'历史送检范围','relation_to_primary':'primary','evidence_ids':[e['id'] for e in intake['evidence'][:2]]}]
    intake['use_records']=[]
inputs['automatic_workspace']=True
atomic_json(root/'context.json',{'source_job_id':args.source,'grading_standard':contract.GRADING_VERSION,
    'model':settings().codex_model,'reasoning_effort':settings().codex_reasoning_effort,
    'fixed_source_evidence':True,'fresh_search_executed':False,'manual_scope_annotation':annotation,
    'attribution_recomputed':True,'not_an_accuracy_estimate':True})
atomic_json(root/'status.json',{'status':'running','stage':'attribution'})
try:
    folder=root/'attribution';folder.mkdir()
    outputs['attribution']=attribution_stage(inputs,outputs,folder)
    atomic_json(root/'frozen-input.json',{'inputs':inputs,'outputs':outputs})
    for name,executor in [('wu_evaluation',wu_evaluation_stage),('v19_evaluation',v19_evaluation_stage),('export',export_stage)]:
        if args.management_only and name!='wu_evaluation':break
        atomic_json(root/'status.json',{'status':'running','stage':name})
        folder=root/name;folder.mkdir()
        outputs[name]=executor(inputs,outputs,folder)
        atomic_json(folder/'output.json',outputs[name])
    atomic_json(root/'status.json',{'status':'succeeded','management_only':args.management_only})
except Exception as exc:
    atomic_json(root/'status.json',{'status':'failed','error':str(exc)})
    raise
