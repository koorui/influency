import json
from pydantic import BaseModel
import pytest
from app.pipeline_search_repair import assess_with_repair
from app.pipeline_native_search import find_research_checkpoint
from app.pipeline_search_collection import with_actual_queries


class Reply(BaseModel):
    reference:str


def test_cli_receives_validation_error_and_keeps_original_response(tmp_path,monkeypatch):
    folder=tmp_path/'attempt-1';folder.mkdir()
    calls=[]
    def execute(run,model,payload,*args,**kwargs):
        calls.append(payload)
        reply=Reply(reference='missing' if len(calls)==1 else 'actual')
        (run/'response.json').write_text(reply.model_dump_json(),encoding='utf-8')
        return reply
    def finalize(reply):
        if reply.reference!='actual':raise ValueError('missing source: missing')
        return {'ok':True}
    monkeypatch.setattr('app.pipeline_search_repair.execute_json_stage',execute)
    assert assess_with_repair(folder,Reply,{'evidence':'actual'},'assess',finalize)=={'ok':True}
    assert calls[1]['correction']['previous_response']=={'reference':'missing'}
    assert 'missing source' in calls[1]['correction']['validation_error']
    assert json.loads((folder/'synthesis-1/response.json').read_text())['reference']=='missing'


def test_repair_is_bounded_and_never_publishes_invalid_output(tmp_path,monkeypatch):
    folder=tmp_path/'attempt-1';folder.mkdir()
    calls=[]
    def execute(run,*args,**kwargs):
        calls.append(run)
        reply=Reply(reference='missing')
        (run/'response.json').write_text(reply.model_dump_json(),encoding='utf-8')
        return reply
    def finalize(reply):raise ValueError('missing source')
    monkeypatch.setattr('app.pipeline_search_repair.execute_json_stage',execute)
    with pytest.raises(ValueError,match='missing source'):
        assess_with_repair(folder,Reply,{},'assess',finalize)
    assert len(calls)==3


def test_resumed_synthesis_uses_old_response_only_with_same_evidence(tmp_path,monkeypatch):
    first=tmp_path/'attempt-1';first.mkdir()
    (first/'input.json').write_text(json.dumps({'evidence':'old'}))
    (first/'response.json').write_text(Reply(reference='old').model_dump_json())
    current=tmp_path/'attempt-2';current.mkdir()
    calls=[]
    def execute(run,model,payload,*args,**kwargs):
        calls.append(payload);return Reply(reference='new')
    monkeypatch.setattr('app.pipeline_search_repair.execute_json_stage',execute)
    assert assess_with_repair(current,Reply,{'evidence':'new'},'assess',lambda r:r.reference)=='new'
    assert calls==[{'evidence':'new'}]


def test_research_checkpoint_rejects_changed_material_or_cutoff(tmp_path):
    old=tmp_path/'attempt-1/research-agent';(old/'research').mkdir(parents=True)
    (old/'materials').mkdir()
    payload={'review_cutoff':'2026-04-30'}
    materials=[{'id':'M1','filename':'report.txt','text':'original\r\nnext line'}]
    (old/'input.json').write_text(json.dumps({**payload,'materials':[{'id':'M1','filename':'report.txt','text_file':'materials/001.txt'}]}))
    (old/'materials/001.txt').write_bytes(materials[0]['text'].encode('utf-8'))
    (old/'response.json').write_text(json.dumps({'summary':'done','limitations':[],'completed_modules':[]}))
    (old/'research/journal.json').write_text('{}')
    (old/'events.jsonl').write_text('')
    current=tmp_path/'attempt-2';current.mkdir()
    assert find_research_checkpoint(payload,materials,current)==old.parent
    assert find_research_checkpoint({'review_cutoff':'2026-05-01'},materials,current) is None
    assert find_research_checkpoint(payload,[{**materials[0],'text':'changed'}],current) is None


def test_missing_source_feedback_names_the_check_and_source():
    class Analysis:
        def model_dump(self,**kwargs):
            return {'sources':[{'id':'Q004-S01'}],'checks':[{'id':'CHK-C9','evidence_ids':['Q004-S01','Q014-S02']}],'research_records':[]}
    with pytest.raises(ValueError,match='checks/CHK-C9: Q014-S02'):
        with_actual_queries(Analysis(),{})
