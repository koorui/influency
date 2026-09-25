import copy
import json
import sys
import uuid
from pathlib import Path
import pytest
from pydantic import ValidationError
from app.config import settings
from app.skill_loader import contract
from app.codex_adapter import CodexAdapter, to_report


def fixture_assessment():
    evidence=[{'id':f'P{i}','title':'测试材料','kind':'project','material_id':'material-1','source':'测试项目报告','locator':f'第{i}段','quote':quote,'url':None,'date':None,'supports':'仅支持项目材料中记载的验证事实','does_not_prove':'不证明独立外部使用','verification':'project_statement'} for i,quote in [(1,'示例探针完成光谱验证。'),(2,'示例探针属于测试项目。')]]
    fields=[{'name':name,'value':'未见明确表述','status':'missing','evidence_ids':[]} for name in sorted(contract.CARD_FIELDS)]
    for f in fields:
        if f['name']=='outcome_name':f.update(value='示例探针',status='confirmed',evidence_ids=['P1','P2'])
    upgrade=lambda n:{'target_level':n,'level_name':contract.LEVELS[n-1],'need':'提供真实使用证据','proof_materials':['使用记录']}
    return {'schema_version':'wu-outcome-v2.1','rubric_id':'wu-v2-six-levels','input_mode':'name_plus_materials',
        'project_context':{'status':'resolved','project_name':'测试项目','project_id':None,'source':'测试项目报告'},
        'outcome_resolution':{'user_query':'示例探针','canonical_name':'示例探针','aliases':[],'resolution_confidence':'high','candidate_outcomes':[{'name':'示例探针','scope':'测试项目所述示例探针','evidence_ids':['P1','P2']}],'scope_note':'两处项目原文对齐','source_refs':['P1','P2']},
        'outcome_card':fields,'evaluation_status':'formal','summary':'仅用于程序测试的成果。','current_level':1,'level_name':contract.LEVELS[0],
        'level_reasons':[{'text':'完成验证','kind':'support','evidence_ids':['P1']},{'text':'尚无真实使用证据','kind':'boundary','evidence_ids':[]}],
        'boundary_gap':'真实任务使用尚待证实','key_judgments':[{'topic':'完成情况','project_claim':'完成光谱验证','assessment':'材料有记载','project_evidence_ids':['P1'],'evaluation_evidence_ids':[]}],
        'upgrade_plus_1':upgrade(2),'upgrade_plus_2':upgrade(3),'next_tasks':{'project_material':{'title':'请项目组补证','summary':'补充使用证据','body':'项目组您好，请提供使用记录。'},'expert_review':None},
        'evidence_index':evidence,'claims':[{'text':'完成光谱验证','evidence_ids':['P1'],'status':'supported_by_project_material'}],
        'dimensions':[{'id':f'D{i}','grade':None,'conclusion':'证据有限','evidence_ids':[],'gaps':['待补证']} for i in range(1,8)],
        'ai_attribution':{'ai_role':'待确认','baseline':'待补充','confirmed_increment':'尚不能确认','confounders':[],'evidence_ids':[],'gaps':['缺少归因实验']},'external_search_status':'not_verified'}


def material():
    return [{'id':'material-1','filename':'test.txt','text':'示例探针完成光谱验证。\n示例探针属于测试项目。'}]


def test_contract_prevents_false_levels_and_broken_evidence():
    data=fixture_assessment()
    value=contract.Assessment.model_validate(data)
    contract.validate_materials(value,material())
    invalid=[]
    x=copy.deepcopy(data);x['evaluation_status']='needs_scope_confirmation';invalid.append(x)
    x=copy.deepcopy(data);x['current_level']=3;x['level_name']=contract.LEVELS[2];invalid.append(x)
    x=copy.deepcopy(data);x['level_reasons'][0]['evidence_ids']=['missing'];invalid.append(x)
    x=copy.deepcopy(data);x['project_context']['status']='missing';invalid.append(x)
    x=copy.deepcopy(data);x['outcome_resolution']['candidate_outcomes']*=2;invalid.append(x)
    x=copy.deepcopy(data);x['upgrade_plus_2']['target_level']=6;invalid.append(x)
    x=copy.deepcopy(data);x['dimensions'][0]['grade']='G1';invalid.append(x)
    for x in invalid:
        with pytest.raises(ValidationError): contract.Assessment.model_validate(x)
    value.evidence_index[0].quote='不存在的摘录'
    with pytest.raises(ValueError,match='原文'): contract.validate_materials(value,material())


def test_scope_confirmation_and_projection():
    value=contract.Assessment.model_validate(fixture_assessment())
    value.outcome_resolution.resolution_confidence='medium'
    with pytest.raises(ValueError,match='确认'):contract.validate_materials(value,material())
    contract.validate_materials(value,material(),'示例探针')
    result=to_report(value,['示例'])
    assert not result.is_demo
    assert result.reason_evidence_refs==[['P1'],[]]
    assert result.dimensions[0].project_evidence_ids==['P1']
    assert result.upgrades[1].target_level==3
    assert result.follow_ups[0].body.startswith('项目组')


def fake_command(monkeypatch,tmp_path,code):
    from app import codex_adapter
    program=tmp_path/'fake_cli.py';program.write_text(code,encoding='utf-8')
    monkeypatch.setattr(codex_adapter,'codex_command',lambda:[sys.executable,str(program)])
    monkeypatch.setattr(settings(),'storage_dir',str(tmp_path/'store'))
    monkeypatch.setattr(settings(),'codex_timeout_seconds',5)
    monkeypatch.setattr(settings(),'task_timeout_seconds',20)


def test_execution_exports_and_isolates_application_credentials(monkeypatch,tmp_path):
    fixture=tmp_path/'fixture.json';fixture.write_text(json.dumps(fixture_assessment(),ensure_ascii=False),encoding='utf-8')
    code="import sys,json,os\nfrom pathlib import Path\na=sys.argv; Path(a[a.index('-o')+1]).write_text(Path("+repr(str(fixture))+").read_text(encoding='utf-8'),encoding='utf-8')\nassert 'SECRET_KEY' not in os.environ\nassert 'DATABASE_URL' not in os.environ\nassert '--sandbox' in a and 'read-only' in a\n"
    fake_command(monkeypatch,tmp_path,code)
    adapter=CodexAdapter(); tid=str(uuid.uuid4())
    result=adapter.evaluate('示例探针',['示例'],material(),task_id=tid,attempt=1)
    assert result.level==1
    folder=tmp_path/'store/evaluations'/tid/'attempt-1/artifacts'
    assert (folder/'evidence-ledger.json').is_file()
    assert '项目组您好' in (folder/'project-material-request.md').read_text(encoding='utf-8')
    assert '① 影响力等级判断' in (folder/'report.html').read_text(encoding='utf-8')


def test_cli_failure_never_falls_back_to_mock(monkeypatch,tmp_path):
    fake_command(monkeypatch,tmp_path,'import sys\nsys.exit(7)\n')
    with pytest.raises(ValueError,match='退出码 7'):
        CodexAdapter().evaluate('示例',['示例'],material(),task_id=str(uuid.uuid4()),attempt=1)


def test_timeout_kills_execution(monkeypatch,tmp_path):
    fake_command(monkeypatch,tmp_path,'import time\ntime.sleep(60)\n')
    monkeypatch.setattr(settings(),'codex_timeout_seconds',1)
    with pytest.raises(ValueError,match='超时'):
        CodexAdapter().evaluate('示例',['示例'],material(),task_id=str(uuid.uuid4()),attempt=1)
