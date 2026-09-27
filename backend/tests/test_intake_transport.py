import json
import pytest
from app.pipeline_model import check_tool_environment
from app.pipeline_stages import wu_intake_stage
from test_codex_adapter import fixture_assessment


def test_executor_permission_failure_is_not_missing_project_evidence(tmp_path):
    events=tmp_path/'events.jsonl'
    events.write_text(json.dumps({'item':{'type':'command_execution','exit_code':1,
        'aggregated_output':'bwrap: No permissions to create a new namespace'}}),encoding='utf-8')
    with pytest.raises(RuntimeError,match='无需重复填写成果名称'):check_tool_environment(events)
    events.write_text(json.dumps({'item':{'type':'command_execution','exit_code':1,
        'aggregated_output':'No exact title match; search with alternative keywords.'}}),encoding='utf-8')
    check_tool_environment(events)


def test_intake_receives_full_unicode_files_and_existing_outcome_name(tmp_path,monkeypatch):
    body='其他项目材料。\n'*30000+'示例探针完成光谱验证。\n示例探针属于测试项目。'
    def execute(folder,model,payload,instruction,**kwargs):
        assert payload['title']=='用户自定义的示例探针名称'
        assert payload['project_name']=='测试项目'
        assert len(json.dumps(payload,ensure_ascii=False))<30000
        source=payload['materials'][0]
        assert source['id']=='material-1'
        assert (folder/source['text_file']).read_text(encoding='utf-8')==body
        assert kwargs['inline_input'] is True
        fixture=fixture_assessment()
        return model(status='ready',project_name='测试项目',canonical_name='示例探针',confidence='high',
            candidates=[{'name':'示例探针','scope':'该项目的光谱探针','evidence_ids':['P1','P2']}],
            outcome_card=fixture['outcome_card'],
            evaluation_objects=[{'id':'primary','name':'示例探针','kind':'探针','version':'本期','relation_to_primary':'primary','evidence_ids':['P1']}],primary_object_id='primary',
            evidence=[{k:e[k] for k in ('id','material_id','locator','quote')} for e in fixture['evidence_index']],
            factors=[],comparisons=[],claims=[],gaps=[])
    monkeypatch.setattr('app.pipeline_stages.execute_json_stage',execute)
    result=wu_intake_stage({'title':'用户自定义的示例探针名称','project_name':'测试项目','project_id':'P',
        'outcome_id':'O','confirmed_scope':'','materials':[{'id':'material-1','filename':'中文材料.txt','text':body}]},{},tmp_path)
    assert result['intake']['canonical_name']=='示例探针'
    assert len(result['intake']['evidence'])==2
