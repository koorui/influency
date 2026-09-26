import json
import pytest
from app.pipeline_search_collection import load_script


def journal_module():
    load_script('parse_public_search');load_script('archive_public_sources')
    return load_script('research_session')


def test_journal_uses_real_native_events_without_duplicate_queries(tmp_path):
    module=journal_module()
    item={'id':'call1','type':'web_search','query':'probe Raman','action':{'type':'search','queries':['probe Raman']},
          'results':[{'title':'Actual paper','url':'https://example.org/paper','ref_id':'r1','snippet':'Actual snippet'}]}
    events=[{'type':'item.started','item':{'id':'call1','type':'web_search'}},{'type':'item.completed','item':item}]
    (tmp_path/'events.jsonl').write_text('\n'.join(json.dumps(e) for e in events),encoding='utf-8')
    data=module.sync_web(tmp_path,'sota')
    assert data['search']['queries'][0]['query']=='probe Raman'
    assert data['search']['candidates'][0]['url']=='https://example.org/paper'
    assert len(module.sync_web(tmp_path,'prior_work')['search']['queries'])==1
    with pytest.raises(ValueError):module.open_sources(tmp_path,['fabricated'])


def test_open_event_registers_real_alternative_url_without_faking_search(tmp_path):
    module=journal_module()
    items=[{'id':'search','type':'web_search','query':'DOI','action':{'type':'search','queries':['DOI']},'results':[]},
           {'id':'open','type':'web_search','query':'','action':{'type':'other'},'results':[{'url':'https://example.org/open.pdf','title':'Author manuscript'}]}]
    (tmp_path/'events.jsonl').write_text('\n'.join(json.dumps({'type':'item.completed','item':i}) for i in items),encoding='utf-8')
    data=module.sync_web(tmp_path,'prior_work')
    assert len(data['search']['queries'])==1
    assert data['search']['candidates'][0]['native_call_id']=='open'
    assert data['search']['queries'][0]['candidate_ids']==['Q001-S01']
