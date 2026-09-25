import csv
import importlib.util
import json
import sys
from app.search_skill_loader import SEARCH_SKILL_ROOT,contract


def test_required_report_retains_unknown_dates_and_does_not_invent_metrics(tmp_path):
    data={'schema_version':'project-search.v1','project_id':'P1','outcome_id':'A1','project_start_date':'2025-01-01',
        'review_cutoff':'2026-01-01','cutoff_basis':'原报告统计截止','search_date':'2026-09-25',
        'modules':[{'id':m,'status':'blocked','summary':'缺少核验依据','limitations':['未取得充分证据']} for m in sorted(contract.MODULES)],
        'sources':[{'id':'Q001-S01','module':'sota','title':'A paper','url':'https://example.org/paper','publisher':'Journal',
            'first_public_date':'2025-02-01','event_date':None,'accessed_at':'2026-09-25','access_status':'full_text',
            'quote':'A real passage.','claim_ids':['C1'],'relationship':'unknown','supports':'Background only','does_not_prove':'No same-protocol comparison',
            'confidence':dict.fromkeys(['object_match','independence','protocol','time'],'unknown')}],
        'queries':[],'checks':[],'limitations':['日期未确认']}
    result=contract.SearchResult.model_validate(data)
    sys.modules['search_contract']=contract
    spec=importlib.util.spec_from_file_location('test_search_exporter',SEARCH_SKILL_ROOT/'scripts/export_search.py')
    exporter=importlib.util.module_from_spec(spec);spec.loader.exec_module(exporter)
    context={'intake':{'canonical_name':'具体成果','claims':[{'id':'C1','text':'项目方声明','evidence_ids':['E1']}],
                      'evidence':[{'id':'E1','material_id':'M1','locator':'第3页','quote':'原始声明'}]}}
    folder=tmp_path/'report';exporter.export(result,folder,context=context)
    def rows(path):
        with (folder/path).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
    assert rows('01_SOTA与对比指标验证/其他方法实际指标估计表.csv')==[]
    missing=rows('04_综合结论/待线下核验材料清单.csv')
    assert missing[0]['填报状态']=='unknown_date'
    assert '日期' in missing[0]['建议索取材料']
    index=rows('04_综合结论/证据总索引.csv')[0]
    assert index['保存状态']=='未提供本地归档'
    assert json.loads(index['本地相对路径'])==[]
    assert rows('00_项目输入与审计边界/项目成果声明抽取表.csv')[0]['项目声明内容']=='项目方声明'
    report=(folder/'04_综合结论/综合Search验证报告.md').read_text(encoding='utf-8')
    assert '待线下核验材料清单.csv' in report
    assert '空表不能解释为已排除' in report
    data['research_records']=[{'table':'对比方法原始指标表.csv','cells':[{'column':'指标名称','value':'RIE'},{'column':'原始指标','value':None}],
        'source_ids':['Q001-S01'],'claim_ids':['C1'],'status':'unverified','limitation':'同口径原始数值未取得'}]
    populated=tmp_path/'populated';exporter.export(contract.SearchResult.model_validate(data),populated,context=context)
    with (populated/'01_SOTA与对比指标验证/对比方法原始指标表.csv').open(encoding='utf-8-sig',newline='') as stream:
        record=list(csv.DictReader(stream))[0]
    assert record['指标名称']=='RIE' and record['原始指标']==''
    assert record['填报状态'].startswith('待核验')
    assert json.loads(record['证据ID'])==['Q001-S01','E1']
    assert record['是否处于有效时间窗口'].startswith('待核验')
    with (populated/'04_综合结论/证据总索引.csv').open(encoding='utf-8-sig',newline='') as stream:
        index_rows=list(csv.DictReader(stream))
    assert {r['证据ID'] for r in index_rows}=={'Q001-S01','E1'}
    internal=next(r for r in index_rows if r['证据ID']=='E1')
    assert all((populated/p).is_file() for p in json.loads(internal['本地相对路径']))
