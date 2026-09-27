"""Behavioral regressions found in the real probe evaluation; no model calls."""
import copy
import importlib
import json
import sys
from pathlib import Path

import pytest
from app.pipeline_stages import bind_search_evidence, attribution_stage
from app.pipeline_contracts import WuIntake
from app.skill_loader import contract
from app.unified_evaluation import combine_evaluations
from test_codex_adapter import fixture_assessment, material

runtime=Path(__file__).resolve().parents[2]/'skills/data-purification-ai-attribution/runtime'
sys.path.insert(0,str(runtime))
engine=importlib.import_module('dca_integration.attribution')


def comparison(**changes):
    value=dict(id='C1',name='测试对照',baseline={'label':'原流程','value':10,'unit':'秒'},
        observed={'label':'新流程','value':6,'unit':'秒'},direction='lower_is_better',
        comparability_status='established',comparison_kind='causal_increment',evidence_ids=['E1','E2','E3'],
        involved_factor_ids=['AI'],isolated_factor_ids=['AI'],baseline_evidence_ids=['E1'],
        observed_evidence_ids=['E2'],control_evidence_ids=['E3'],controlled_conditions='同样任务、硬件和数据，只替换模型')
    return value|changes


def data(comparisons=None):
    return dict(schema_version='dca-attribution-input/v1',project={'id':'P','name':'项目'},target={'id':'O','name':'方法'},
        evidence=[{'id':f'E{i}','source_type':'project','locator':f'第{i}段','text':'原始记录'} for i in range(1,4)],
        factors=[{'id':'AI','name':'模型','evaluate_independent_increment':True}],
        comparisons=comparisons if comparisons is not None else [comparison()],claims=[])


def run(tmp_path,value):
    p=tmp_path/'input.json';p.write_text(json.dumps(value),encoding='utf-8')
    engine.run_attribution(p,tmp_path/'out')
    return json.loads((tmp_path/'out/contribution_result.json').read_text(encoding='utf-8'))


def test_acceptance_threshold_cannot_generate_1110_percent_or_causal_credit(tmp_path):
    c=comparison(comparison_kind='threshold_check',direction='higher_is_better',
        observed={'value':121,'unit':'秒'})
    r=run(tmp_path,data([c]));v=r['comparison_results'][0]
    assert v['effect_outcome']=='threshold_met'
    assert v['percent_change_from_baseline'] is None and v['ratio_change'] is None
    assert not v['causal_eligible']
    assert r['factor_results'][0]['status']=='participation_supported_increment_not_isolated'


@pytest.mark.parametrize('changes',[
    {'comparison_kind':'unspecified'},{'comparability_status':'partial'},
    {'comparability_status':'unknown'},{'baseline':{'value':10}},
])
def test_unconfirmed_semantics_or_comparability_cannot_generate_gain(changes):
    r=engine._calculate_comparison(comparison(**changes))
    assert r['percent_change_from_baseline'] is None and not r['causal_eligible']


@pytest.mark.parametrize('value',[0,-10])
def test_nonpositive_baseline_does_not_create_percentage(value):
    r=engine._calculate_comparison(comparison(baseline={'value':value,'unit':'秒'}))
    assert r['percent_change_from_baseline'] is None and r['ratio_change'] is None


def test_controlled_positive_and_negative_results_are_not_cherry_picked(tmp_path):
    positive=comparison();negative=comparison(id='C2',observed={'value':12,'unit':'秒'})
    r=run(tmp_path,data([positive,negative]))
    f=r['factor_results'][0]
    assert f['status']=='conflicting_comparisons'
    assert f['established_by_comparison_ids']==['C1'] and f['nonpositive_by_comparison_ids']==['C2']
    assert f['evidence_ids']==['E1','E2','E3']


def test_real_single_factor_control_still_supports_bounded_increment(tmp_path):
    r=run(tmp_path,data())
    assert r['factor_results'][0]['status']=='direct_increment_supported'
    assert r['comparison_results'][0]['percent_change_from_baseline']==40


def test_missing_control_evidence_does_not_prove_causality(tmp_path):
    r=run(tmp_path,data([comparison(control_evidence_ids=[])]))
    assert r['factor_results'][0]['status']=='participation_supported_increment_not_isolated'


def test_empty_factors_complete_without_inventing_ai(tmp_path):
    v=data([]);v['factors']=[]
    r=run(tmp_path,v)
    assert r['attribution_applicability']=='not_established' and r['factor_results']==[]


def assessment():
    v=fixture_assessment()
    for d in v['dimensions']:d['grade']='G1'
    return v


def external():
    return dict(id='S1',title='页面',kind='external',material_id=None,source='页面',locator='改写位置',
        quote='改写的引文',url='https://example.org/paper',date='2020-01-01',supports='背景',
        does_not_prove='采用',verification='verified')


def test_external_quotes_and_dates_bind_to_replay_and_unknown_sources_fail(tmp_path):
    v=assessment();v['evidence_index'].append(external());a=contract.LegacyFinalAssessment.model_validate(v)
    source={'quote':'原文引文','first_public_date':'2025-01-01','access_status':'full_text'}
    replay={'replay':{'evidence':[{'id':'S1','text':json.dumps(source),'locator':'正文',
                                 'url':'https://example.org/paper'}]},'time_audit':{'source_status':{'S1':'eligible'}}}
    result=bind_search_evidence(a,replay,tmp_path)
    assert result.evidence_index[-1].quote=='原文引文' and result.evidence_index[-1].date=='2025-01-01'
    assert a.evidence_index[-1].quote=='改写的引文'
    replay['time_audit']['source_status']['S1']='unknown_date'
    with pytest.raises(ValueError):bind_search_evidence(a,replay,tmp_path)
    replay['replay']['evidence']=[]
    with pytest.raises(ValueError):bind_search_evidence(a,replay,tmp_path)


def test_relabelled_same_quote_is_not_two_original_locations():
    v=assessment();v['evidence_index'][1]['quote']=v['evidence_index'][0]['quote']
    a=contract.LegacyFinalAssessment.model_validate(v)
    with pytest.raises(ValueError,match='两处'):contract.validate_materials(a,material())


def test_background_paper_alone_cannot_support_l3_but_private_adoption_can():
    v=assessment();v.update(current_level=3,level_name=contract.LEVELS[2])
    for offset,key in [(1,'upgrade_plus_1'),(2,'upgrade_plus_2')]:
        v[key].update(target_level=3+offset,level_name=contract.LEVELS[2+offset])
    v['evidence_index'].append(external())
    with pytest.raises(ValueError):contract.LegacyFinalAssessment.model_validate(v)
    v['evidence_index'].pop()
    v['impact_uses']=[{'object_id':'probe','user':'独立实验室','task':'实际研究任务','result':'任务产出',
        'relationship':'independent','relationship_basis':'原始第三方记录及关系说明',
        'evidence_ids':['P1'],'independence_evidence_ids':['P2']}]
    assert contract.LegacyFinalAssessment.model_validate(v).current_level==3


def test_intake_catches_unknown_factors_and_object_use_mismatch():
    v=fixture_assessment()
    intake=dict(status='ready',project_name='项目',canonical_name='示例探针',confidence='high',
        candidates=v['outcome_resolution']['candidate_outcomes'],outcome_card=v['outcome_card'],
        evidence=[{k:e[k] for k in ('id','material_id','quote','locator')} for e in v['evidence_index']],
        factors=[],comparisons=[],claims=[],gaps=[],evaluation_objects=[{
            'id':'probe','name':'探针','kind':'分子','version':'本期','relation_to_primary':'primary','evidence_ids':['P1']}],
        primary_object_id='probe',use_records=[])
    assert WuIntake.model_validate(intake).primary_object_id=='probe'
    intake['claims']=[{'id':'C','text':'参与','factor_id':'missing','evidence_ids':['P1']}]
    with pytest.raises(ValueError):WuIntake.model_validate(intake)
    intake['claims']=[];intake['use_records']=[{'object_id':'method','phase':'real_task','user':'团队',
        'task':'研制','result':'候选','relationship':'internal','relationship_basis':'项目记录',
        'event_date':None,'evidence_ids':['P1']}]
    with pytest.raises(ValueError):WuIntake.model_validate(intake)


def test_difference_keeps_both_reasons_without_overwriting_grades():
    m={'project_id':'P','outcome_id':'O','rubric_version':contract.RUBRIC_VERSION,'grading_standard':contract.GRADING_VERSION,
       'assessment':assessment()}
    d={k:v for k,v in m.items() if k!='assessment'}
    d['result']={'outcomes':[{'outcome_id':'O','dimensions':[
        {'dimension_id':f'D{i}','grade':{'level':'G2' if i==6 else 'G1','reason':'实际内部流程接入'}} for i in range(1,8)],
        'synthesis':{'impact_level':{'level':'L1'}}}]}
    original=copy.deepcopy((m,d));r=combine_evaluations(m,d)
    assert r['review_status']=='needs_review' and len(r['differences'])==1
    assert r['differences'][0]['dimension_reason']=='实际内部流程接入'
    assert (m,d)==original


def test_both_transports_reject_l2_without_actual_use_evidence():
    from app.v19_response_contract import ImpactLevel
    from app.pipeline_v19 import wrapper
    wrapper()
    from metric_judgment.indicator_product import _normalize_level
    raw=dict(level='L2',reason='内部研发流程运行',source_ids=['E1'],gap_to_next='补证')
    with pytest.raises(ValueError):ImpactLevel.model_validate(raw)
    assert _normalize_level(raw,'L',require_sources=True)['level']=='待确认'
    raw['use_evidence']=[{'object_id':'method','user':'实验团队','task':'真实候选选择','result':'选取并合成候选',
        'relationship':'internal','relationship_basis':'项目记录','source_ids':['E1'],'independence_source_ids':[]}]
    assert ImpactLevel.model_validate(raw).level=='L2'
    assert _normalize_level(raw,'L',require_sources=True)['level']=='L2'


def test_empty_factor_pipeline_stage_is_not_a_missing_input_block(tmp_path):
    prep=dict(schema_version='attribution-preparation.v1',project_id='P',project_name='项目',outcome_id='O',outcome_name='成果',
        evidence=[],factors=[],comparisons=[],claims=[])
    replay=dict(schema_version='search-replay.v1',project_id='P',outcome_id='O',mode='historical_replay',
        original_run_id='old',original_completed_at='2026-01-01',source_label='历史',evidence=[],findings=[])
    r=attribution_stage({}, {'wu_intake':{'project_id':'P','outcome_id':'O','attribution_preparation':prep},
        'search_replay':{'replay':replay}},tmp_path)
    assert r['contribution_result']['attribution_applicability']=='not_established'
