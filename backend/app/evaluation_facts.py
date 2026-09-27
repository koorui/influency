"""Prepare a shared, citation-bound fact ledger before either grading path."""
import json
from datetime import datetime, timezone, date
from .skill_loader import contract
from .pipeline_store import atomic_json
from .pipeline_model import execute_json_stage


def prepare_fact_ledger(inputs, outputs, payload, folder, saved_response=None):
    intake=outputs['wu_intake']['intake']
    search=outputs['search_replay']
    boundary=payload.get('review_boundary') or {}
    cutoff=boundary.get('review_cutoff') or (search.get('raw_result') or {}).get('review_cutoff')
    cutoff=cutoff or datetime.now(timezone.utc).date().isoformat()
    date.fromisoformat(cutoff)
    known={e['id'] for e in intake['evidence']}
    external={e['id']:e for e in search['replay']['evidence']}
    if known & external.keys():raise ValueError('项目与外部证据编号重复')
    known |= external.keys()
    stage=folder/'fact-ledger';stage.mkdir()
    request={**payload,'evaluation_cutoff':cutoff,'expert_fact_decisions':inputs.get('expert_fact_decisions',[])}
    instruction=(
        'Build the shared fact ledger BEFORE grading. Never assign L or G here. '
        'Use exactly the supplied project_id, outcome_id, intake.primary_object_id and evaluation_cutoff. '
        'Cover F1 formed/validated, F2 actual task use, F3 independent adoption, F4 sustained multi-actor influence, '
        'F5 stable field dependency, F6 transformative change. These are factual predicates, not sequential mandatory gates. '
        'Separate the primary product from the method used to create it. Scientific downstream adoption is actual use. '
        'Every evidence_id must be an exact supplied intake or search ID. Do not invent evidence or reread unrelated files. '
        'verified means this exact fact has source support, not independent certification. Project assertions remain assertions. '
        'State not_found_as_of_cutoff means no record within search_coverage, NOT proven nonoccurrence. '
        'Use pending with state=null for an unexamined predicate, not_applicable with state=null if inapplicable. '
        'Retain counterevidence and conflicts. Unknown event dates remain null; explain time_basis, '
        'never infer that a retrospective report proves all events occurred before cutoff. '
        'Separate technical value, project additionality, AI contribution, potential and management action. '
        'Use the deterministic attribution boundaries: threshold is not baseline improvement, participation is not causal gain. '
        'Expert decisions refer to a previous snapshot; check their object, current evidence and cutoff before using them. '
        'Keep impact_facts exclusively for the primary object; associated-method effects belong in value_and_attribution, not the primary F predicates. '
        'Keep each original claim atomic, including numerical conditions and uncertainty. Read references/teacher-v3-integration.md.')
    if saved_response:
        from .pipeline_model import bind_fact_objects
        raw=json.loads(saved_response.read_text(encoding='utf-8'))
        ledger=contract.FactLedger.model_validate(bind_fact_objects(raw,request,stage))
        atomic_json(stage/'reuse-receipt.json',{'original_response':str(saved_response),'source_text_edited':False})
    else:ledger=execute_json_stage(stage,contract.FactLedger,request,instruction,inline_input=True)
    if (ledger.project_id,ledger.outcome_id,ledger.primary_object_id,ledger.evaluation_cutoff)!=(
        payload['project_id'],payload['outcome_id'],intake['primary_object_id'],cutoff):
        raise ValueError('事实账本改变了冻结对象或评价截止日')
    groups=[f.evidence_ids+f.counter_evidence_ids for f in ledger.impact_facts]
    groups += [c.evidence_ids for c in ledger.claims]
    groups += [v['evidence_ids'] for v in ledger.value_and_attribution.model_dump().values()]
    if any(set(ids)-known for ids in groups):raise ValueError('事实账本引用未知来源')
    statuses=(search.get('time_audit') or {}).get('source_status',{})
    for fact in ledger.impact_facts:
        if fact.state!='verified':continue
        if fact.event_date and date.fromisoformat(fact.event_date)>date.fromisoformat(cutoff):
            raise ValueError('达级事实发生在评价截止日之后')
        for key in fact.evidence_ids:
            if key not in external:continue
            if statuses.get(key) not in (None,'eligible'):raise ValueError('事实引用时间不合格来源')
            try: source=json.loads(external[key]['text'])
            except (TypeError,ValueError):source={}
            if not isinstance(source,dict) or not source.get('quote') or source.get('access_status') not in ('full_text','abstract'):
                raise ValueError('未取得原文的来源不能支持已核验事实')
    value=ledger.model_dump()
    atomic_json(folder/'fact-ledger.json',value)
    return value


def attach_fact_ledger(workspace, ledger, evidence=()):
    """No candidate grades or management conclusions cross this boundary."""
    if not ledger:return
    sources=[{'source_id':e['id'],**{k:e.get(k) for k in ('title','quote','locator','material_id','url','date','verification')}} for e in evidence]
    workspace['shared_fact_ledger']=ledger
    workspace['shared_fact_evidence']=sources
    for card in workspace.get('evaluation_framework',{}).get('outcome_cards',[]):
        card['shared_fact_ledger']=ledger
    for packet in workspace.get('evidence_adapter',{}).get('outcome_packets',{}).values():
        for unit in packet.get('dimensions',{}).values():
            unit['shared_fact_ledger']=ledger
            unit['shared_fact_evidence']=sources
