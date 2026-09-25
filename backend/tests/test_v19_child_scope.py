import json
from pathlib import Path
import pytest
from app.v19_child_scope import child_workspace


def test_child_projection_does_not_inherit_parent_successes():
    delivery={'project_profile':{'project_id':'P02','title':'项目'},'step3_frozen_outcomes':{'outcomes':[{'outcome_id':'MAIN-003','child_outcomes':[{'outcome_id':'ACH-002','title':'新型拉曼探针'},{'outcome_id':'OTHER','title':'核磁系统'}]}]},'private_parent_claim':'核磁准确率99%'}
    intake={'project_id':'P02','outcome_id':'local','attribution_preparation':{'evidence':[{'id':'E1','text':'探针RIE记录','locator':'原报告页'}]}}
    replay={'project_id':'P02','outcome_id':'local','evidence':[]}
    attr={'contribution_result':{},'unresolved_items':[]}
    w=child_workspace(delivery,intake,replay,attr,child_id='ACH-002',routes={'D1':['E1']},review_note='仅评探针')
    assert len(w['evaluation_framework']['outcome_cards'])==1
    assert w['evaluation_framework']['outcome_cards'][0]['outcome_id']=='ACH-002'
    assert '99%' not in json.dumps(w)
    assert w['evidence_adapter']['outcome_packets']['ACH-002']['dimensions']['D6']['project_facts']==[]
    assert w['pipeline_provenance']['wu_evaluation_used'] is False
    with pytest.raises(ValueError):child_workspace(delivery,intake,replay,attr,child_id='ACH-002',routes={'D1':['missing']},review_note='只评探针')
