import importlib
import json
import sys
from pathlib import Path
from .pipeline_contracts import SearchReplay,AttributionPreparation,attribution_input
from .pipeline_store import WaitingForInput,atomic_json,fingerprint
from .pipeline_contracts import WuIntake
from .pipeline_model import execute_json_stage
from .skill_loader import contract,exporter

SKILLS=Path(__file__).resolve().parents[2]/'skills'


def wu_intake_stage(inputs,outputs,folder):
    import re
    request={k:inputs.get(k) for k in ['project_id','project_name','outcome_id','title','confirmed_scope','materials']}
    value=execute_json_stage(folder,WuIntake,request,
        'Execute only Wu Step 0 and Step 1: resolve the outcome, build the 12-field card, and extract factual attribution inputs. '
        'Do not evaluate G/L grades, do not perform attribution or Search. Missing facts stay missing. '
        'Extract factors, claims, comparisons only when supported by verbatim supplied material. Do not invent a comparison to fill the array; empty comparisons are allowed. '
        'Return needs_scope_confirmation if boundaries are ambiguous. Evidence material_id must match supplied IDs. '
        'A user-confirmed scope may disambiguate matching candidates but cannot invent project evidence. '
        'An evidence quote is an exact passage, not a summary. Confidence high requires at least two original locations. '
        'HARD OUTPUT RULE: every evidence_ids value anywhere in outcome_card, candidates, comparisons, and claims MUST be one of the IDs in evidence. '
        'Never create E12/E13/etc. If a field lacks evidence, set status=missing, value="未见明确表述/待补充", and evidence_ids=[]. Before finalizing, check every reference against the evidence ID set.')
    texts={m['id']:re.sub(r'\s+','',m['text']) for m in inputs['materials']}
    invalid=[e.id for e in value.evidence if not e.quote.strip() or e.material_id not in texts or re.sub(r'\s+','',e.quote) not in texts[e.material_id]]
    if invalid:
        raise ValueError(f'成果定位原文引用不一致：{invalid}；请核对原始响应，不能删除引用后继续计算')
    atomic_json(folder/'outcome-intake.json',value.model_dump())
    confirmed=inputs.get('confirmed_scope','')==value.canonical_name
    locations={(e.material_id,e.locator,e.quote) for e in value.evidence}
    if value.status!='ready' or not value.evidence or (not confirmed and (value.confidence!='high' or len(locations)<2)):
        raise WaitingForInput('请确认成果范围或补齐项目原始依据',value.model_dump())
    prep={'schema_version':'attribution-preparation.v1','project_id':inputs['project_id'],'project_name':value.project_name,
          'outcome_id':inputs['outcome_id'],'outcome_name':value.canonical_name,
          'evidence':[{'id':e.id,'project_id':inputs['project_id'],'outcome_id':inputs['outcome_id'],'source_type':'project','locator':e.locator,'text':e.quote,'url':None} for e in value.evidence],
          'factors':[f.model_dump() for f in value.factors],'comparisons':[c.model_dump() for c in value.comparisons],'claims':[c.model_dump() for c in value.claims]}
    return {'project_id':inputs['project_id'],'outcome_id':inputs['outcome_id'],'intake':value.model_dump(),'attribution_preparation':prep}


def wu_evaluation_stage(inputs,outputs,folder):
    intake=outputs['wu_intake']
    # Reuse exact quotes and locators from the intake instead of sending a
    # 679-page extracted report a second time to Codex.
    evidence_by_material={}
    for e in intake['intake'].get('evidence',[]):
        evidence_by_material.setdefault(e['material_id'],[]).append(f"[{e['locator']}]\n{e['quote']}")
    compact_materials=[]
    for material in inputs['materials']:
        compact_materials.append({'id':material['id'],'filename':material['filename'],'text':'\n\n'.join(evidence_by_material.get(material['id'],[]))})
    payload={'project_id':intake['project_id'],'outcome_id':intake['outcome_id'],'intake':intake['intake'],
             'materials':compact_materials,'search_replay':outputs['search_replay'], 'attribution':outputs['attribution'],
             'confirmed_scope':inputs.get('confirmed_scope','')}
    search_raw=outputs['search_replay'].get('raw_result',{})
    payload['review_boundary']=inputs.get('search_boundary') or {k:search_raw.get(k) for k in ('project_start_date','review_cutoff','cutoff_basis')}
    assessment=execute_json_stage(folder,contract.Assessment,payload,
        'Execute Wu evaluation after intake, Search replay and deterministic attribution. Do not repeat intake, Search or attribution calculation. '
        'Respect the frozen canonical name. Use supplied attribution results with their uncertainty and do not convert participation to net contribution. '
        'Check search_replay.fresh_search_executed and replay.mode: historical_replay is not fresh verification; live_search is actual queried evidence filtered by the supplied review cutoff. '
        'Never use time-audit excluded sources for formal support, and never turn a blocked or undated source into verified evidence. '
        'Respect review_boundary. An internal retrospective report is a project statement, not independent proof that every experiment occurred before the cutoff. '
        'If outcome-specific event dates are not established, state that limit in boundary_gap and request dated records. '
        'Do not retroactively certify an achievement date; if unresolved timing is essential to the level claim, return preliminary with current_level=null. '
        'A G grade requires affirmative evidence for that grade. No external recognition/adoption evidence does NOT establish G1: '
        'use grade=null and record the gap when a dimension lacks affirmative support; an empty evidence_ids list requires grade=null. '
        'Preserve material IDs and exact quotes; do not call the attribution output an original project document. '
        'Use only Wu v2 G/L criteria; output the full Wu assessment separately from v19. Missing evidence must remain gaps.',inline_input=True)
    contract.validate_materials(assessment,inputs['materials'],inputs.get('confirmed_scope',''))
    if assessment.outcome_resolution.canonical_name!=intake['intake']['canonical_name']:
        raise ValueError('吴老师评价阶段改变了已冻结成果范围')
    exporter.export_artifacts(assessment,folder/'artifacts')
    if assessment.evaluation_status in ('needs_scope_confirmation','insufficient_project_context'):
        raise WaitingForInput('吴老师评价要求补充上下文或确认成果范围',assessment.model_dump())
    return {'rubric_id':'wu-v2-six-levels','project_id':intake['project_id'],'outcome_id':intake['outcome_id'],'assessment':assessment.model_dump()}


def search_replay_stage(inputs,outputs,folder):
    if inputs.get('search_mode')=='live':
        from .pipeline_search import live_search_stage
        return live_search_stage(inputs,outputs,folder)
    scope=outputs['wu_intake']
    replay_input=inputs.get('search_replay')
    if replay_input is None:
        raise WaitingForInput('请提供同项目同成果的历史Search交付，或等待正式Search模块',{'project_id':scope['project_id'],'outcome_id':scope['outcome_id']})
    replay=SearchReplay.model_validate(replay_input)
    if (replay.project_id,replay.outcome_id)!=(scope['project_id'],scope['outcome_id']):
        raise ValueError('Search交付对象与已冻结成果不一致')
    value=replay.model_dump()
    return {'replay':value,'source_hash':fingerprint(value),'fresh_search_executed':False}


def attribution_stage(inputs,outputs,folder):
    scope=outputs['wu_intake']
    prepared=scope.get('attribution_preparation')
    if prepared is None:
        raise WaitingForInput('成果整理阶段尚未提供结构化贡献因素、声明及比较输入')
    if not prepared.get('factors'):
        raise WaitingForInput('未从材料中确认可归因因素，请补材料；不会默认创造一个AI因素')
    preparation=AttributionPreparation.model_validate(prepared)
    if (preparation.project_id,preparation.outcome_id)!=(scope['project_id'],scope['outcome_id']):
        raise ValueError('归因准备与冻结成果不一致')
    replay=SearchReplay.model_validate(outputs['search_replay']['replay'])
    payload=attribution_input(preparation,replay)
    path=folder/'attribution-input.json';atomic_json(path,payload)
    runtime=str(SKILLS/'data-purification-ai-attribution/runtime')
    if runtime not in sys.path:sys.path.insert(0,runtime)
    module=importlib.import_module('dca_integration')
    summary=module.run_attribution(input_path=str(path),output_dir=str(folder/'artifacts'))
    artifacts=folder/'artifacts'
    return {'project_id':scope['project_id'],'outcome_id':scope['outcome_id'],
        'engine':'dca-integration/1.1.0','input_hash':fingerprint(payload),
        'search_mode':replay.mode,'search_source_hash':outputs['search_replay']['source_hash'],
        'contribution_result':json.loads((artifacts/'contribution_result.json').read_text(encoding='utf-8')),
        'unresolved_items':json.loads((artifacts/'unresolved_items.json').read_text(encoding='utf-8')),
        'summary':summary}
