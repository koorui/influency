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
    differences=[]
    if management_level and dimension_level and management_level!=dimension_level:
        differences.append({'field':'impact_level','management':management_level,'dimensions':dimension_level})
    mg={d['id']:d.get('grade') for d in assessment.get('dimensions',[])}
    dg={d['dimension_id']:(d.get('grade') or {}).get('level') for d in outcome.get('dimensions',[])}
    for key in sorted(mg.keys() & dg.keys()):
        if mg[key] and dg[key] and mg[key]!=dg[key]:
            differences.append({'field':key,'management':mg[key],'dimensions':dg[key]})
    complete=bool(management_level and dimension_level and
                  all(mg.get(f'D{i}') in {f'G{g}' for g in range(1,6)} and
                      dg.get(f'D{i}') in {f'G{g}' for g in range(1,6)} for i in range(1,8)))
    comparison='legacy_or_mixed' if not current else 'incomplete' if not complete else 'different' if differences else 'consistent'
    return {
        'schema_version':'unified-impact-evaluation.v1',
        'evaluation_name':'双层影响力评价',
        'project_id':management['project_id'],'outcome_id':management['outcome_id'],
        'rubric_version':contract.RUBRIC_VERSION if current else None,
        'grading_standard':contract.GRADING_VERSION if current else None,
        'comparison':comparison,'differences':differences,
        'levels':{'management_level':management_level,'dimension_level':dimension_level,'scope_level':scope_level},
        'management_layer':management,'dimension_layer':dimensions,
        'rule':'共用六级与七维标准，分别保留原始证据；等级不相加、不平均、不自动取高。差异需核对证据覆盖、时间范围与成果粒度。',
    }
