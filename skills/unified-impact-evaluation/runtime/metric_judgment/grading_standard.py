"""Current user supplied grading standard, independent of transport and evidence."""
import json
from pathlib import Path

STANDARD=json.loads((Path(__file__).resolve().parents[2]/'references/grading-standard-20260925.json').read_text(encoding='utf-8'))
VERSION=STANDARD['version']
G_LEVEL_CRITERIA=STANDARD['grade_criteria']
RUBRIC_VERSION='unified-double-layer-impact.v1'
L_LEVEL_CRITERIA={key:value['name']+'：'+value['condition'] for key,value in STANDARD['levels'].items()}

FINAL_JUDGMENT_POLICY = (Path(__file__).resolve().parents[2]/'references/expert-method.md').read_text(encoding='utf-8')
FINAL_JUDGMENT_POLICY += '\n' + (Path(__file__).resolve().parents[2]/'references/teacher-v3-integration.md').read_text(encoding='utf-8')
FINAL_JUDGMENT_POLICY += '\n分档JSON必须包含assessment_state与level：assessed时给有事实支持的G1-G5；insufficient_evidence/not_applicable/conflict时level=null。L未定时level=null并写reason。L2以上use_evidence必须有对象、用户、任务、结果、关系与source_ids；L3以上另有独立性依据independence_source_ids。'


def apply_current_dimension_scope(payload):
    """Keep evidence and IDs; replace superseded scope/policy, not source facts."""
    payload['grading_standard']=STANDARD
    dim=payload.get('dimension',{})
    key=dim.get('dimension_id') or dim.get('question_id')
    if key in STANDARD['dimensions']:
        dim.update(name=STANDARD['dimensions'][key]['name'],question=STANDARD['dimensions'][key]['question'])
    return payload
