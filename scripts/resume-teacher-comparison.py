"""Resume a saved management response after an explicit formatting-only repair."""
import json
import sys
from pathlib import Path
runtime=Path(sys.argv[1]);root=Path(sys.argv[2])
sys.path.insert(0,str(runtime/'backend'))
from app.pipeline_store import atomic_json
from app.pipeline_stages import finish_wu_evaluation
from app.pipeline_v19 import v19_evaluation_stage,export_stage
from app.skill_loader import contract

sys.stdout=(root/'resume.log').open('w',encoding='utf-8',buffering=1);sys.stderr=sys.stdout
packet=json.loads((root/'frozen-input.json').read_text(encoding='utf-8'))
inputs,outputs=packet['inputs'],packet['outputs']
folder=root/'wu_evaluation';payload=json.loads((folder/'input.json').read_text(encoding='utf-8'))
try:
    raw=json.loads((folder/'response.json').read_text(encoding='utf-8'))
    value,corrections=contract.normalize_level_labels(raw)
    atomic_json(folder/'resume-normalization.json',{'corrections':corrections,'raw_response_preserved':True,'grade_edited':False})
    result=contract.FinalAssessment.model_validate(value)
    outputs['wu_evaluation']=finish_wu_evaluation(inputs,outputs,folder,result,payload)
    atomic_json(folder/'output.json',outputs['wu_evaluation'])
    for name,executor in [('v19_evaluation',v19_evaluation_stage),('export',export_stage)]:
        atomic_json(root/'status.json',{'status':'running','stage':name})
        folder=root/name;folder.mkdir()
        outputs[name]=executor(inputs,outputs,folder);atomic_json(folder/'output.json',outputs[name])
    atomic_json(root/'status.json',{'status':'succeeded','formatting_resume':True})
except Exception as exc:
    atomic_json(root/'status.json',{'status':'failed','error':str(exc)})
    raise
