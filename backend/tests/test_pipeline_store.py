import pytest
from app.pipeline_store import PipelineStore,STAGES,WaitingForInput


def test_resume_preserves_completed_stages_and_separate_rubrics(tmp_path):
    store=PipelineStore(tmp_path/'run');store.create({'project_id':'P02'})
    calls=[]
    def stage(name):
        def execute(inputs,outputs,folder):
            calls.append(name)
            if name=='attribution' and calls.count(name)==1:raise ValueError('bad comparison input')
            return {'stage':name,'rubric':'wu-v2' if name=='wu_evaluation' else 'v19' if name=='v19_evaluation' else None}
        return execute
    executors={s:stage(s) for s in STAGES}
    with pytest.raises(ValueError):store.execute(executors)
    assert store.read()['status']=='failed'
    assert store.execute(executors)['status']=='succeeded'
    assert calls.count('wu_intake')==1
    assert calls.count('attribution')==2
    records=store.read()['stages']
    assert records['wu_evaluation']['output']!=records['v19_evaluation']['output']


def test_scope_gate_stops_downstream_execution(tmp_path):
    store=PipelineStore(tmp_path/'run');store.create({'project_id':'P02'})
    def wait(*args):raise WaitingForInput('Confirm outcome',{'candidates':['A','B']})
    result=store.execute({'wu_intake':wait})
    assert result['status']=='waiting'
    assert result['stages']['search_replay']['attempts']==0




def test_amend_restarts_downstream_but_keeps_upstream_and_history(tmp_path):
    store=PipelineStore(tmp_path/'run');store.create({'project_id':'P02'})
    calls=[]
    def execute(name):
        def stage(inputs,outputs,folder):
            calls.append(name)
            if name=='search_replay' and not inputs.get('search_replay'):
                raise WaitingForInput('Search missing')
            return {'name':name}
        return stage
    executors={s:execute(s) for s in STAGES}
    assert store.execute(executors)['status']=='waiting'
    store.amend({'search_replay':{'source':'fixture'}},'search_replay')
    assert store.execute(executors)['status']=='succeeded'
    assert calls.count('wu_intake')==1
    assert calls.count('search_replay')==2
    assert (store.root/'search_replay/attempt-1/waiting.json').is_file()
    assert store.read()['amendments'][0]['restart_stage']=='search_replay'
