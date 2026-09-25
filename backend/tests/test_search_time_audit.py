from datetime import date
from app.search_skill_loader import contract

def source(**extra):
    data={'id':'E1','module':'sota','title':'原始论文','url':'https://example.com/paper','publisher':'期刊',
          'first_public_date':'2026-04-01','event_date':'2026-03-20','accessed_at':'2026-09-25',
          'access_status':'full_text','quote':'原文','claim_ids':['C1'],'relationship':'independent',
          'supports':'指标','does_not_prove':'不可跨协议比较','confidence':dict.fromkeys(['object_match','independence','protocol','time'],'high')}
    data.update(extra)
    return contract.Source.model_validate(data)

def test_late_publication_and_event_never_count_formally():
    cutoff=date(2026,4,30)
    assert contract.time_status(source(),cutoff)=='eligible'
    assert contract.time_status(source(first_public_date='2026-05-01'),cutoff)=='excluded_after_cutoff'
    assert contract.time_status(source(event_date='2026-05-01'),cutoff)=='excluded_after_cutoff'
    assert contract.time_status(source(first_public_date=None),cutoff)=='unknown_date'
    assert contract.time_status(source(access_status='metadata_only'),cutoff)=='not_verified'

def test_late_source_cannot_support_claim_even_if_model_says_supported():
    data={'schema_version':'project-search.v1','project_id':'P02','outcome_id':'A','project_start_date':'2025-06-01','review_cutoff':'2026-04-30','cutoff_basis':'项目统计截止','search_date':'2026-09-25',
          'modules':[{'id':m,'status':'blocked','summary':'未执行','limitations':['测试']} for m in contract.MODULES],
          'sources':[source(first_public_date='2026-05-01').model_dump(mode='json')],'queries':[],
          'checks':[{'id':'J1','module':'sota','claim_id':'C1','conclusion':'模型声称支持','status':'supported','evidence_ids':['E1'],'protocol_notes':'待核','execution_percent':None,'execution_basis':'','confidence':dict.fromkeys(['object_match','independence','protocol','time'],'high')}],'limitations':[]}
    result=contract.SearchResult.model_validate(data)
    reviewed=contract.audit(result)
    assert reviewed['checks'][0]['formal_status']=='not_verified'
    assert reviewed['checks'][0]['eligible_evidence_ids']==[]
    assert reviewed['new_search_executed'] is False
