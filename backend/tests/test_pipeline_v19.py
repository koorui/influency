import json
from pathlib import Path
import pytest
from app.pipeline_v19 import build_v19_workspace,export_stage,wrapper
from app.pipeline_store import WaitingForInput


def context():
    from app.v19_child_scope import child_workspace
    children=[{'outcome_id':f'OUT-{i}','title':f'成果{i}'} for i in range(5)]
    delivery={'project_profile':{'project_id':'P02','title':'测试项目'},
        'step3_frozen_outcomes':{'outcomes':[{'outcome_id':'PARENT','child_outcomes':children}]}}
    scope={'project_id':'P02','outcome_id':'OUT-0','attribution_preparation':{
        'evidence':[{'id':'E1','text':'已完成原始测试','locator':'第1页'}]}}
    workspace=child_workspace(delivery,scope,{'project_id':'P02','outcome_id':'OUT-0','evidence':[]},
        {'contribution_result':{},'unresolved_items':[]},child_id='OUT-0',routes={'D1':['E1']},review_note='测试原始事实映射')
    workspace['evaluation_framework']['outcome_cards'].extend(children[1:])
    oid=workspace['evaluation_framework']['outcome_cards'][0]['outcome_id']
    inputs={'v19_workspace':workspace,'v19_scope_mapping':{'outcome_id':oid,'canonical_name':'已确认具体成果','reviewed':True}}
    outputs={'wu_intake':{'project_id':'P02','outcome_id':oid,'intake':{'canonical_name':'已确认具体成果'},'attribution_preparation':{'evidence':[{'id':'PIPE-P1','text':'项目原文','locator':'第1页'}]}},
             'search_replay':{'replay':{'mode':'historical_replay','original_run_id':'fixture','original_completed_at':'2026-09-23','source_label':'历史回放','evidence':[]}},
             'attribution':{'engine':'dca-integration/1.1.0','contribution_result':{'analysis':'无法隔离AI增量'},'unresolved_items':[]},
             'wu_evaluation':{'rubric_id':'wu-v2-six-levels','assessment':{'current_level':6,'private_marker':'DO_NOT_PASS_WU_JUDGMENT'}}}
    return inputs,outputs


def test_bridge_keeps_frozen_id_and_excludes_wu_judgment(tmp_path):
    inputs,outputs=context()
    workspace=build_v19_workspace(inputs,outputs)
    assert len(workspace['evaluation_framework']['outcome_cards'])==1
    assert len(inputs['v19_workspace']['evaluation_framework']['outcome_cards'])==5
    assert 'DO_NOT_PASS_WU_JUDGMENT' not in json.dumps(workspace)
    oid=outputs['wu_intake']['outcome_id']
    dims=workspace['evidence_adapter']['outcome_packets'][oid]['dimensions']
    assert dims['D1']['pipeline_evidence_handoff']['attribution_analysis']['result']['analysis']=='无法隔离AI增量'
    assert 'attribution_analysis' not in dims['D6']['pipeline_evidence_handoff']
    p=tmp_path/'workspace.json';p.write_text(json.dumps(workspace,ensure_ascii=False),encoding='utf-8')
    check=wrapper().inspect_workspace(p)
    assert check['formal_input_ready']
    assert check['expected_logical_calls']==9


def test_bridge_requires_reviewed_mapping():
    inputs,outputs=context();inputs['v19_scope_mapping']['reviewed']=False
    with pytest.raises(WaitingForInput):build_v19_workspace(inputs,outputs)
    inputs,outputs=context();inputs['v19_workspace']['project_profile']['project_id']='P01'
    with pytest.raises(ValueError,match='项目'):build_v19_workspace(inputs,outputs)


def test_export_stores_two_independent_rubrics(tmp_path):
    wu={'project_id':'P02','outcome_id':'X','rubric_id':'wu-v2-six-levels','assessment':{'current_level':3,
        'dimensions':[{'id':f'D{i}','grade':'G1'} for i in range(1,8)]}}
    v19={'project_id':'P02','outcome_id':'X','rubric_id':'outcome-d1-d7-evaluation.v19','result':{
        'outcomes':[{'outcome_id':'X','dimensions':[{'dimension_id':f'D{i}','grade':{'level':'G1'}} for i in range(1,8)],
            'synthesis':{'impact_level':{'level':'L2'}}}]}}
    result=export_stage({}, {'wu_evaluation':wu,'v19_evaluation':v19},tmp_path)
    assert result['wu']['file']!=result['v19']['file']
    assert json.loads((tmp_path/result['wu']['file']).read_text(encoding='utf-8'))==wu
    assert json.loads((tmp_path/result['v19']['file']).read_text(encoding='utf-8'))==v19
    assert not result['published']


def test_export_rejects_unmapped_or_incomplete_grades(tmp_path):
    wu={'project_id':'P02','outcome_id':'X','rubric_id':'wu-v2-six-levels','assessment':{'current_level':3}}
    v19={'project_id':'P02','outcome_id':'X','rubric_id':'outcome-d1-d7-evaluation.v19','result':{'impact_level':'L2'}}
    with pytest.raises(ValueError,match='不完整'):export_stage({}, {'wu_evaluation':wu,'v19_evaluation':v19},tmp_path)
    assert not (tmp_path/'manifest.json').exists()
