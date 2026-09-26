import copy
import json
import pytest
from app.skill_loader import contract
from app.unified_evaluation import combine_evaluations
from app.pipeline_v19 import export_stage


def reports():
    common={'project_id':'P','outcome_id':'O','rubric_version':contract.RUBRIC_VERSION,
            'grading_standard':contract.GRADING_VERSION,'rubric_id':contract.RUBRIC_VERSION}
    management={**common,'assessment':{'current_level':2,'dimensions':[
        {'id':f'D{i}','grade':'G1'} for i in range(1,8)]}}
    dimensions={**common,'result':{'outcomes':[{'outcome_id':'O','dimensions':[
        {'dimension_id':f'D{i}','grade':{'level':'G1'}} for i in range(1,8)],
        'synthesis':{'impact_level':{'level':'L2'}}}],
        'project_synthesis':{'scope_impact_level':{'level':'L3'}}}}
    return management,dimensions


def test_compares_same_outcome_without_using_project_scope_or_overwriting_reports():
    a,b=reports();before=copy.deepcopy((a,b))
    value=combine_evaluations(a,b)
    assert value['comparison']=='consistent'
    assert value['levels']=={'management_level':'L2','dimension_level':'L2','scope_level':'L3'}
    b['result']['outcomes'][0]['synthesis']['impact_level']['level']='L4'
    b['result']['outcomes'][0]['dimensions'][2]['grade']['level']='G3'
    value=combine_evaluations(a,b)
    assert value['comparison']=='different'
    assert {x['field'] for x in value['differences']}=={'impact_level','D3'}
    assert a==before[0]
    assert value['levels']['management_level']=='L2'


def test_legacy_incomplete_and_mismatched_reports_are_not_certified():
    a,b=reports();a.pop('grading_standard')
    value=combine_evaluations(a,b)
    assert value['comparison']=='legacy_or_mixed' and value['rubric_version'] is None
    a,b=reports();b['result']['outcomes'][0]['outcome_id']='ANOTHER'
    assert combine_evaluations(a,b)['comparison']=='incomplete'
    assert combine_evaluations(a,b)['levels']['dimension_level'] is None
    b['project_id']='OTHER'
    with pytest.raises(ValueError,match='冻结'):combine_evaluations(a,b)


def test_export_preserves_both_sources_and_adds_shared_version_and_comparison(tmp_path):
    a,b=reports()
    manifest=export_stage({}, {'wu_evaluation':a,'v19_evaluation':b},tmp_path)
    assert manifest['rubric_version']==contract.RUBRIC_VERSION
    assert manifest['grading_standard']==contract.GRADING_VERSION
    assert json.loads((tmp_path/'wu-evaluation.json').read_text(encoding='utf-8'))==a
    assert json.loads((tmp_path/'v19-evaluation.json').read_text(encoding='utf-8'))==b
    assert json.loads((tmp_path/manifest['unified']['file']).read_text(encoding='utf-8'))['comparison']=='consistent'


def test_unified_endpoint_requires_admin_and_real_completed_pipeline(client,admin_client):
    identifier='11111111-1111-1111-1111-111111111111'
    assert client.get(f'/api/admin/pipeline-reports/{identifier}/double-layer').status_code==401
    assert admin_client.get(f'/api/admin/pipeline-reports/{identifier}/double-layer').status_code==404
    assert admin_client.get('/api/admin/pipeline-reports/invalid/double-layer').status_code==422
