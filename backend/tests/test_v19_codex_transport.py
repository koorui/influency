import json
from pathlib import Path
from types import SimpleNamespace
from app.v19_codex_transport import CodexV19Client


def test_codex_transport_preserves_v19_request_and_json(tmp_path,monkeypatch):
    seen=[]
    def execute(folder,model,payload,instruction,**kwargs):
        seen.append((payload,instruction,kwargs))
        return model(result_json=json.dumps({'grade':{'level':'待确认'},'status':'待核验'}))
    monkeypatch.setattr('app.v19_codex_transport.execute_json_stage',execute)
    client=CodexV19Client(tmp_path/'calls')
    r=client.chat_json('v19 only',json.dumps({'dimension':'D1'}),model='gpt-6-astra')
    assert r.ok and r.data['grade']['level']=='待确认'
    assert seen[0][0]['v19_system_prompt']=='v19 only'
    assert seen[0][2]['skill_root'].name=='dual-layer-impact-v19'
    assert r.model=='gpt-6-astra'
    assert (tmp_path/'calls/call-001/parsed-result.json').exists()


def test_bad_json_is_failed_transport_not_fake_evaluation(tmp_path,monkeypatch):
    monkeypatch.setattr('app.v19_codex_transport.execute_json_stage',lambda *a,**k:SimpleNamespace(result_json='not json'))
    r=CodexV19Client(tmp_path/'calls').chat_json('v19','{}')
    assert not r.ok and r.data is None


def test_invented_source_is_rejected_before_original_engine(tmp_path,monkeypatch):
    monkeypatch.setattr('app.v19_codex_transport.execute_json_stage',lambda *a,**k:SimpleNamespace(result_json=json.dumps({'decisive_evidence':[{'source_ids':['invented-source']}]})))
    r=CodexV19Client(tmp_path/'calls').chat_json('v19',json.dumps({'evidence':[{'source_id':'E1','quote':'原文'}]}))
    assert not r.ok and r.data is None
    assert 'invented-source' in r.error


def test_dimension_uses_object_schema_instead_of_double_encoded_json(tmp_path,monkeypatch):
    from app.v19_response_contract import DimensionReply
    value={'status':'待核验','branch_judgments':[{'branch_id':f'D2.{n}','status':'待核验','conclusion':'缺少原始证据','decisive_source_ids':[]} for n in range(1,4)],
        'core_position':'待判断','conclusion':'缺少证据','expert_analysis':'不能默认定级','time_assessment':{'prior_baseline':'未知','current_window_increment':'未知','subsequent_effect':'未知'},
        'evidence_chain':[],'basis':[],'counterevidence':[],'professional_metric_use':[],'ai_attribution':'待核验','missing_inputs':['原始材料'],'expert_question':'',
        'evidence_confidence':'低','judgment_confidence':'低','key_facts':[],'confirmation_requests':[],'ai_analysis':{},
        'grade':{'level':'待确认','reason':'缺少依据','source_ids':[],'gap_to_next':'补充原始依据'}}
    def execute(folder,model,payload,instruction,**kwargs):
        assert model is DimensionReply
        assert kwargs['inline_input'] is True
        return model.model_validate(value)
    monkeypatch.setattr('app.v19_codex_transport.execute_json_stage',execute)
    result=CodexV19Client(tmp_path/'calls').chat_json('original v19 rules',json.dumps({'dimension':{'question_id':'D2'}}))
    assert result.ok and result.data==value


def test_cached_response_requires_same_input_model_and_matching_raw_response(tmp_path,monkeypatch):
    from app.pipeline_store import atomic_json,fingerprint
    from app.config import settings
    root=tmp_path/'prior';call=root/'call-001';call.mkdir(parents=True)
    payload={'v19_system_prompt':'original rules','v19_input':{'evidence':[{'source_id':'E1','quote':'original'}]}}
    data={'impact_level':{'level':'L1','source_ids':['E1']}}
    atomic_json(call/'request-manifest.json',{'input_hash':fingerprint(payload)})
    atomic_json(call/'input.json',payload)
    atomic_json(call/'execution.json',{'model':'gpt-6-astra','reasoning_effort':settings().codex_reasoning_effort})
    atomic_json(call/'response.json',{'result_json':json.dumps(data)})
    atomic_json(call/'parsed-result.json',data)
    calls=[]
    def execute(folder,model,payload,instruction,**kwargs):
        calls.append(payload)
        return model(result_json=json.dumps({'impact_level':{'level':'待确认','source_ids':[]}}))
    monkeypatch.setattr('app.v19_codex_transport.execute_json_stage',execute)
    client=CodexV19Client(tmp_path/'new',cache_roots=[root])
    result=client.chat_json(payload['v19_system_prompt'],json.dumps(payload['v19_input']),model='gpt-6-astra')
    assert result.ok and result.data==data and not calls
    assert json.loads((tmp_path/'new/call-001/execution.json').read_text())['new_model_call'] is False
    changed=client.chat_json('changed rules',json.dumps(payload['v19_input']),model='gpt-6-astra')
    assert changed.ok and len(calls)==1
    atomic_json(call/'parsed-result.json',{'impact_level':{'level':'L6','source_ids':['E1']}})
    unchanged=client.chat_json(payload['v19_system_prompt'],json.dumps(payload['v19_input']),model='gpt-6-astra')
    assert unchanged.ok and len(calls)==2 and unchanged.data['impact_level']['level']=='待确认'
