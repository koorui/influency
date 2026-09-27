"""One bounded editorial reconciliation, grounded in the frozen source packet."""
from typing import Literal
import copy
import json
from pydantic import Field
from .schema import StrictModel
from .skill_loader import contract
from .pipeline_store import atomic_json


class ReviewItem(StrictModel):
    field: str
    action: Literal['revised', 'retained']
    reason: str = Field(min_length=10)
    evidence_ids: list[str]


class OutputQuality(StrictModel):
    fluent: bool
    understandable: bool
    actionable: bool
    evidence_faithful: bool
    revision_notes: str = Field(min_length=10)


class CoordinatedReport(StrictModel):
    assessment: contract.FinalAssessment
    review_items: list[ReviewItem]
    quality: OutputQuality


def validate_coordination(response, original, differences, source_ids):
    if response.assessment.fact_ledger.model_dump() != original['assessment']['fact_ledger']:
        raise ValueError('协调不得修改冻结事实；事实变化须重新核验')
    if response.assessment.model_dump()['outcome_card'] != original['assessment']['outcome_card']:
        raise ValueError('协调不得修改冻结成果卡')
    fields=[r.field for r in response.review_items]
    if len(set(fields)) != len(fields) or set(fields) != {d['field'] for d in differences}:
        raise ValueError('协调须逐项回应全部审查分歧，不能遗漏或编造事项')
    for item in response.review_items:
        if set(item.evidence_ids)-source_ids:
            raise ValueError('协调引用了原始来源以外的编号')
    if not all(getattr(response.quality,key) for key in ('fluent','understandable','actionable','evidence_faithful')):
        raise ValueError('最终输出的流畅度、易懂性、实用性或证据忠实度检查未通过')


def normalize_coordination(value,payload,folder):
    from .pipeline_model import expand_fact_citations
    value=copy.deepcopy(value)
    value['assessment'],corrections=contract.normalize_level_labels(value['assessment'])
    atomic_json(folder/'label-normalization.json',{'corrections':corrections,'raw_response_preserved':True})
    value['assessment']=expand_fact_citations(value['assessment'],payload,folder)
    present={e['id'] for e in value['assessment']['evidence_index']}
    restored=[e for e in payload['management_draft']['evidence_index'] if e['id'] not in present]
    value['assessment']['evidence_index'].extend(copy.deepcopy(restored))
    atomic_json(folder/'source-registry-binding.json',{'restored_ids':[e['id'] for e in restored],
        'source':'management_draft.evidence_index','raw_response_preserved':True,'grade_edited':False})
    return CoordinatedReport.model_validate(value)


def coordinate_report(inputs, outputs, folder, combined, *, saved_response=None):
    from .pipeline_model import execute_json_stage
    from .pipeline_stages import finish_wu_evaluation
    original=outputs['wu_evaluation']
    intake=outputs['wu_intake']['intake']
    payload={'project_id':original['project_id'],'outcome_id':original['outcome_id'],
        'intake':intake,'fact_ledger':original['assessment']['fact_ledger'],
        'search_replay':outputs['search_replay'],'attribution':outputs['attribution'],
        'management_draft':original['assessment'],
        'internal_review':outputs['v19_evaluation']['result'],
        'differences':combined['differences'],
        'review_boundary':inputs.get('search_boundary'),
        'confirmed_scope':inputs.get('confirmed_scope','')}
    folder.mkdir(parents=True,exist_ok=True)
    instruction=(
        'Read references/report-quality.md. Finalize the MANAGEMENT report, which is the sole authoritative system recommendation. '
        'The internal review is criticism, NEVER original evidence. Inspect every supplied difference against original intake/Search quotes, '
        'frozen object, dates and grade conditions. Revise the management draft when evidence warrants; otherwise retain its conclusion with a concrete reason. '
        'Do not average grades or force agreement. For each initial difference return exactly one review_item with its field, action, reason and original evidence IDs. '
        'Retain unresolved objections in the report boundary and concrete follow-up tasks. Decisive missing or contradictory facts may require a null L. '
        'Copy fact_ledger and outcome_card exactly. Retain the complete original evidence_index even when only a few sources are discussed in review_items. Keep canonical identity, original evidence IDs and source fields. '
        'Check the FINAL prose for fluent Chinese, understandable reasoning, actionable next steps and fidelity to evidence. '
        'Revise awkward or vague prose before responding. Record actual edits and remaining limitations in quality.revision_notes; do not invent expert review. '
        'Return assessment plus review_items and quality, within one bounded review call. No further searches.')
    if saved_response is None:
        response=execute_json_stage(folder,CoordinatedReport,payload,instruction,inline_input=True)
    else:
        if json.loads(saved_response.with_name('input.json').read_text(encoding='utf-8'))!=payload:
            raise ValueError('已存模型响应不属于相同冻结输入，不能复用')
        raw=saved_response.read_text(encoding='utf-8-sig')
        (folder/'response.json').write_text(raw,encoding='utf-8')
        atomic_json(folder/'input.json',payload)
        response=normalize_coordination(json.loads(raw),payload,folder)
    source_ids={e['id'] for e in intake['evidence']}|{e['id'] for e in outputs['search_replay']['replay']['evidence']}
    validate_coordination(response,original,combined['differences'],source_ids)
    final=finish_wu_evaluation(inputs,outputs,folder,response.assessment,payload)
    # Keep the editorial model response and source bindings, not merely a success flag.
    receipt={'status':'completed','authority':'management','saved_response':str(saved_response) if saved_response else None,
        'review_items':[r.model_dump() for r in response.review_items],
        'quality':response.quality.model_dump(),'initial_difference_count':len(combined['differences'])}
    atomic_json(folder/'coordination.json',receipt)
    return final,receipt
