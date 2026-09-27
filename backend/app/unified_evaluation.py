"""Combine report views without turning one model's verdict into source evidence."""
from .skill_loader import contract


def combine_evaluations(management, dimensions):
    for key in ('project_id','outcome_id'):
        if not management.get(key) or management.get(key)!=dimensions.get(key):
            raise ValueError('两种评价的冻结项目或成果不一致，不能组合报告')
    assessment=management.get('assessment') or {}
    result=dimensions.get('result') or {}
    matches=[o for o in result.get('outcomes',[]) if o.get('outcome_id')==management['outcome_id']]
    # A project/scope synthesis is not an outcome verdict. Never substitute it.
    outcome=matches[0] if len(matches)==1 else {}
    management_level=assessment.get('current_level')
    management_level=f'L{management_level}' if type(management_level) is int and 1<=management_level<=6 else None
    dimension_level=(outcome.get('synthesis',{}).get('impact_level') or {}).get('level')
    scope_level=(result.get('project_synthesis',{}).get('scope_impact_level') or {}).get('level')
    if dimension_level not in {f'L{i}' for i in range(1,7)}:dimension_level=None
    if scope_level not in {f'L{i}' for i in range(1,7)}:scope_level=None
    current=all(v.get('rubric_version')==contract.RUBRIC_VERSION and v.get('grading_standard')==contract.GRADING_VERSION
                for v in (management,dimensions))
    modern=assessment.get('schema_version')=='outcome-evaluation.v3'
    differences=[]
    if management_level!=dimension_level and (modern or (management_level and dimension_level)):
        differences.append({'field':'impact_level','management':management_level,'dimensions':dimension_level})
    mg={d['id']:d.get('grade') for d in assessment.get('dimensions',[])}
    dg={d['dimension_id']:(d.get('grade') or {}).get('level') for d in outcome.get('dimensions',[])}
    for key in sorted(mg.keys() & dg.keys()):
        if mg[key]!=dg[key] and (modern or (mg[key] and dg[key])):
            differences.append({'field':key,'management':mg[key],'dimensions':dg[key]})
    md={d['id']:d for d in assessment.get('dimensions',[])}
    dd={d['dimension_id']:d for d in outcome.get('dimensions',[])}
    for row in differences:
        key=row['field']
        if key=='impact_level':
            row['management_reason']='；'.join(r.get('text','') for r in assessment.get('level_reasons',[]))
            row['dimension_reason']=(outcome.get('synthesis',{}).get('impact_level') or {}).get('reason','')
        else:
            row['management_reason']=md[key].get('conclusion','')
            row['dimension_reason']=(dd[key].get('grade') or {}).get('reason','')
        row['review_action']='核对对象、原始依据与事件时间；以管理者报告为主结论，未解决的异议保留为复核事项。'
    if modern:
        for key in sorted(md.keys() & dd.keys()):
            left=md[key].get('assessment_state');right=(dd[key].get('grade') or {}).get('assessment_state')
            if mg[key]==dg[key] and left!=right:
                differences.append({'field':key+'_state','management':left,'dimensions':right,
                    'management_reason':md[key].get('conclusion',''),
                    'dimension_reason':(dd[key].get('grade') or {}).get('reason',''),
                    'review_action':'核对证据不足、不适用和冲突的事实依据，不能因为均为空档而忽略状态差异。'})
    complete=bool(len(matches)==1 and len(assessment.get('dimensions',[]))==7 and len(outcome.get('dimensions',[]))==7 and management_level and dimension_level and
                  all(mg.get(f'D{i}') in {f'G{g}' for g in range(1,6)} and
                      dg.get(f'D{i}') in {f'G{g}' for g in range(1,6)} for i in range(1,8)))
    if modern:
        def reviewed(d, nested=False):
            row=(d.get('grade') or {}) if nested else d
            grade=row.get('level') if nested else row.get('grade')
            state=row.get('assessment_state')
            return bool(row.get('reason') if nested else row.get('conclusion')) and ((state=='assessed' and grade in {f'G{i}' for i in range(1,6)}) or (state in ('insufficient_evidence','not_applicable','conflict') and grade is None))
        complete=bool(len(matches)==1 and len(md)==7 and len(dd)==7 and all(
            reviewed(md.get(f'D{i}',{})) and reviewed(dd.get(f'D{i}',{}),True) for i in range(1,8)))
    # Method disagreement is advisory; missing or contradictory facts still need review.
    blocking=not bool(management_level)
    if modern and any(f.get('state')=='conflict' for f in (assessment.get('fact_ledger') or {}).get('impact_facts',[])):blocking=True
    comparison='legacy_or_mixed' if not current else 'incomplete' if not complete else 'different' if differences else 'consistent'
    return {
        'schema_version':'unified-impact-evaluation.v1',
        'evaluation_name':'管理者报告与内部审查',
        'project_id':management['project_id'],'outcome_id':management['outcome_id'],
        'rubric_version':contract.RUBRIC_VERSION if current else None,
        'grading_standard':contract.GRADING_VERSION if current else None,
        'comparison':comparison,'differences':differences,
        'complete':complete,
        'review_status':'needs_review' if differences or not complete or blocking else 'no_detected_difference',
        'expert_confirmation':'not_recorded',
        'blocking_disagreement':blocking,
        'current_level':management_level,
        'authority':'management',
        'adjudication_status':'system_preliminary',
        'levels':{'management_level':management_level,'dimension_level':dimension_level,'scope_level':scope_level},
        'management_layer':management,'dimension_layer':dimensions,
        'rule':'共用事实与标准，内部协调后以管理者报告为主；七维为审查依据。残留异议保留，不平均、不取高、不冒充专家认定。',
    }
