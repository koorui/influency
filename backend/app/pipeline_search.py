import importlib.util
import json
import sys
from datetime import date
from .search_skill_loader import contract,SEARCH_SKILL_ROOT
from .pipeline_model import execute_json_stage
from .pipeline_store import WaitingForInput,atomic_json,fingerprint
from .pipeline_search_collection import collect_for_stage,validate_collected_result,analysis_model,with_actual_queries,excerpt_bank


def live_search_stage(inputs,outputs,folder):
    scope=outputs['wu_intake']
    boundary=inputs.get('search_boundary') or {}
    if not all(boundary.get(k) for k in ['project_start_date','review_cutoff','cutoff_basis']):
        raise WaitingForInput('联网Search前需提供项目启动日期、评审截止日及其来源，不能用今天替代')
    payload={'project_id':scope['project_id'],'outcome_id':scope['outcome_id'],**boundary,
             'search_date':date.today().isoformat(),'intake':scope['intake'],'project_evidence':scope['attribution_preparation']['evidence']}
    collected=collect_for_stage(payload,folder)
    return assess_collected_search(scope,boundary,payload,collected,folder)


def assess_collected_search(scope,boundary,payload,collected,folder):
    bank=excerpt_bank(collected)
    model_collected={k:v for k,v in collected.items() if k!='primary_source_texts'}
    model_collected['primary_source_excerpts']=bank
    result_model=analysis_model([c['id'] for c in scope['intake']['claims']],[c['id'] for c in collected['search']['candidates']],[e['id'] for e in bank])
    analysis=execute_json_stage(folder,result_model,{**payload,'collected':model_collected},
        'Assess the five Search modules using this run\'s program-collected public queries and archived source texts. '
        'Do not perform network or shell requests. Actual requests are in collected.search.queries; the program attaches the complete query log itself. '
        'Return research analysis only, without transcribing query logs. Every check evidence_id must appear in your sources list. '
        'Source IDs and URLs must match collected.search.candidates exactly. A source may inform a module different from its query module. '
        'Never use project material IDs as external source IDs: checks may cite only IDs in your sources list. '
        'Full_text requires actual primary_source_excerpts containing article or repository body, not a challenge, abstract or login page. '
        'Choose quote_ref from the provided excerpt IDs belonging to this source; the program copies that exact passage. Never compose quotations yourself. '
        'Use null quote_ref when no primary text is available, retaining metadata_only or blocked status. '
        'Populate research_records for the original workflow tables whenever archived sources or project claims supply relevant facts. '
        'Use the exact Chinese column names in skill/schemas/required-tables.json; unknown cells are null. '
        'Do not include 声明ID, 证据ID or 是否处于有效时间窗口 as table cells; the program derives them from record references and time audit. '
        'Do not infer project membership from paper authorship, independent deployment from citations, or numeric estimates without a method. '
        'Every record needs source_ids from your sources list or original claim_ids. Leave unavailable record types empty and explain module gaps. '
        'A received response or parsed candidate is not proof of matching subject, independent use or scientific validity. '
        'Wrong-subject results mean no_verified_result with an explanation; access/parse failures mean access_failed. '
        'Respect the supplied review cutoff, claim IDs, project and outcome. Do not reuse historical evaluation answers. '
        'Record blocked sources honestly and distinguish author/partner claims from independent evidence. '
        'Unknown dates must be null. Every module needs actual query logs or a blocked status. '
        'Do not execute repository code. Return all five modules; incomplete evidence means partial or blocked, not invented support.',
        skill_root=SEARCH_SKILL_ROOT,timeout=900,live_search=False,inline_input=True)
    return finalize_collected_search(scope,boundary,payload,collected,folder,analysis)


def finalize_collected_search(scope,boundary,payload,collected,folder,analysis):
    result=with_actual_queries(analysis,collected)
    if (result.project_id,result.outcome_id)!=(scope['project_id'],scope['outcome_id']):raise ValueError('Search改变项目或成果ID')
    if result.review_cutoff.isoformat()!=boundary['review_cutoff'] or result.project_start_date.isoformat()!=boundary['project_start_date']:
        raise ValueError('Search改变了上游评审时间边界')
    known_claims={c['id'] for c in scope['intake']['claims']}
    if any(c.claim_id not in known_claims for c in result.checks):raise ValueError('Search引用了不存在的上游声明')
    if any(not set(s.claim_ids).issubset(known_claims) for s in result.sources):raise ValueError('Search来源关联了不存在的上游声明')
    if any(not set(row.claim_ids).issubset(known_claims) for row in result.research_records):raise ValueError('专门表格关联了不存在的上游声明')
    if result.search_date.isoformat()!=payload['search_date']:raise ValueError('Search改变了本次实际检索日期')
    validate_collected_result(result,collected)
    audited=contract.audit(result)
    atomic_json(folder/'search-result.json',result.model_dump(mode='json'));atomic_json(folder/'time-audit.json',audited)
    sys.modules['search_contract']=contract
    spec=importlib.util.spec_from_file_location('pipeline_search_export',SEARCH_SKILL_ROOT/'scripts/export_search.py')
    exporter=importlib.util.module_from_spec(spec);spec.loader.exec_module(exporter);exporter.export(result,folder/'artifacts',collection_root=folder,context=payload)
    approved={k for k,v in audited['source_status'].items() if v=='eligible'}
    evidence=[{'id':s.id,'project_id':scope['project_id'],'outcome_id':scope['outcome_id'],'source_type':'search',
               'locator':s.url,'url':s.url,'text':json.dumps(s.model_dump(mode='json'),ensure_ascii=False)} for s in result.sources if s.id in approved]
    findings=[]
    for item in audited['checks']:
        status='conflicts' if item['formal_status']=='conflicts' else 'needs_expert' if item['formal_status'] in ('partial','not_verified') else None
        if status:findings.append({'id':item['id'],'status':status,'statement':item['formal_conclusion'],
            'reason':item['protocol_notes'] or '见Search底稿及时间审计','related_claim_ids':[item['claim_id']],
            'evidence_ids':item['eligible_evidence_ids']})
    handoff={'schema_version':'search-replay.v1','mode':'live_search','project_id':scope['project_id'],'outcome_id':scope['outcome_id'],
             'original_run_id':folder.name,'original_completed_at':result.search_date.isoformat(),
             'source_label':'单良Search规范：实际公开检索，经时间审计过滤','evidence':evidence,'findings':findings}
    return {'replay':handoff,'source_hash':fingerprint(handoff),'fresh_search_executed':True,'time_audit':audited,
            'raw_result':result.model_dump(mode='json')}
