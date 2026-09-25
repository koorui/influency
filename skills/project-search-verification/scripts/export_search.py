"""Export structured Search artifacts; never invent evidence or pretend empty modules succeeded."""
import csv
import json
import shutil
import importlib.util
from pathlib import Path
from search_contract import SearchResult,audit

DIRECTORIES={'sota':'01_SOTA与对比指标验证','prior_work':'02_项目前既有成果追溯','usage_media':'03_成果使用评价与媒体报道','github':'05_GitHub价值与可复现性','indicator':'06_指标达成度核验'}

def csv_file(path,rows,columns):
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=columns,extrasaction='ignore');writer.writeheader()
        for row in rows:
            writer.writerow({k:json.dumps(v,ensure_ascii=False) if isinstance(v,(dict,list)) else v for k,v in row.items()})

def export(result:SearchResult,output:Path,collection_root:Path|None=None,context=None):
    output.mkdir(parents=True,exist_ok=False)
    checked=audit(result)
    for name,value in [('search-result',result.model_dump(mode='json')),('time-audit',checked)]:
        (output/f'{name}.json').write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    boundary=output/'00_项目输入与审计边界';boundary.mkdir()
    (boundary/'项目时间边界与团队范围.md').write_text(f'# 时间边界\n\n项目：{result.project_id}\n成果：{result.outcome_id}\n项目启动：{result.project_start_date}\n评审截止：{result.review_cutoff}\n日期依据：{result.cutoff_basis}\n检索执行：{result.search_date}\n',encoding='utf-8')
    report=['# 综合Search验证报告','本报告为截至项目对应阶段评审基准日的时点审计。网络检索执行日期可能晚于评审日期，但所有正式判断仅采用在评审基准日前已经形成并公开可获得的证据。评审日期之后出现的论文、指标、引用、代码更新、部署和媒体报道不用于反向评价项目在该阶段的状态。',f'评审截止：{result.review_cutoff}；实际检索：{result.search_date}。']
    for module in result.modules:
        folder=output/DIRECTORIES[module.id];folder.mkdir()
        (folder/'evidence').mkdir();(folder/'screenshots').mkdir()
        queries=[q.model_dump(mode='json') for q in result.queries if q.module==module.id]
        checks=[c for c in checked['checks'] if c['module']==module.id]
        csv_file(folder/'检索日志.csv',queries,['module','query','channel','executed_at','outcome','source_ids','note'])
        csv_file(folder/'核验结果.csv',checks,['id','claim_id','formal_status','formal_conclusion','status','conclusion','eligible_evidence_ids','excluded_evidence_ids','protocol_notes','execution_percent','execution_basis','confidence'])
        text=f'# {DIRECTORIES[module.id]}\n\n执行状态：{module.status}\n\n{module.summary}\n\n限制：\n'+ '\n'.join('- '+x for x in module.limitations)
        (folder/'核验报告.md').write_text(text,encoding='utf-8')
        report.append(text)
    summary=output/'04_综合结论';summary.mkdir()
    sources=[{**s.model_dump(mode='json'),'time_status':checked['source_status'][s.id]} for s in result.sources]
    primary={};queries={}
    if collection_root is not None:
        collection_root=collection_root.resolve()
        primary_path=collection_root/'primary-sources/receipts.json'
        query_path=collection_root/'public-search/receipts.json'
        if primary_path.exists():primary={r['id']:r for r in json.loads(primary_path.read_text(encoding='utf-8'))['sources']}
        if query_path.exists():queries={r['id']:r for r in json.loads(query_path.read_text(encoding='utf-8'))['queries']}
    for source in sources:
        paths=[]
        receipt=primary.get(source['id'],{})
        query=queries.get(source['id'].split('-S')[0],{})
        if collection_root is not None:
            entries=[('primary-sources',receipt.get('raw_file')),('primary-sources',receipt.get('text_file')),('public-search',query.get('file'))]
            for parent,name in entries:
                if not name:continue
                root=(collection_root/parent).resolve();original=(root/name).resolve()
                if not original.is_relative_to(root) or not original.is_file():raise ValueError('证据索引指向不存在或越界的归档')
                relative=Path(DIRECTORIES[source['module']])/'evidence'/original.name
                shutil.copyfile(original,output/relative);paths.append(relative.as_posix())
            for parent,record in [('primary-sources',receipt),('public-search',query)]:
                if record:
                    relative=Path(DIRECTORIES[source['module']])/'evidence'/(record['id']+'-receipt.json')
                    (output/relative).write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
                    paths.append(relative.as_posix())
        source['本地相对路径']=paths
        source['保存状态']='已归档（访问状态另列）' if paths else '未提供本地归档'
        source['保存格式']=receipt.get('content_type') or query.get('content_type','')
        source['访问限制']=receipt.get('error','')
    columns=['id','module','title','url','publisher','first_public_date','event_date','accessed_at','access_status','time_status','quote','claim_ids','relationship','supports','does_not_prove','confidence','本地相对路径','保存状态','保存格式','访问限制']
    csv_file(summary/'证据总索引.csv',sources,columns)
    csv_file(summary/'超出评审时间窗口排除清单.csv',[s for s in sources if s['time_status']=='excluded_after_cutoff'],columns)
    csv_file(summary/'待线下核验材料清单.csv',[s for s in sources if s['time_status'] in ('unknown_date','not_verified')],columns)
    spec=importlib.util.spec_from_file_location('required_search_tables',Path(__file__).with_name('export_required_tables.py'))
    tables=importlib.util.module_from_spec(spec);spec.loader.exec_module(tables)
    coverage=tables.export_required(result,checked,output,sources,context)
    report.append((summary/'规范分项说明.md').read_text(encoding='utf-8'))
    missing=[row['文件'] for row in coverage if row['行数']==0]
    report.append('## 专门表格的证据缺口\n\n以下表格已提供规范字段，但本轮未取得足以填报该类关系的结构化依据。空表不能解释为已排除该类成果或影响：\n\n'+'\n'.join('- '+name for name in missing))
    (summary/'综合Search验证报告.md').write_text('\n\n'.join(report),encoding='utf-8')
    (output/'README.md').write_text('# Search核验交付\n\n请先看04_综合结论/综合Search验证报告.md。JSON保留完整模型输出，CSV另列程序时间审计后的正式状态。截图目录为空时表示未生成截图，不代表已经截图核验。\n',encoding='utf-8')

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('result',type=Path);p.add_argument('--output',type=Path,required=True);p.add_argument('--collection-root',type=Path);p.add_argument('--context',type=Path);a=p.parse_args()
    export(SearchResult.model_validate_json(a.result.read_text(encoding='utf-8')),a.output,collection_root=a.collection_root,context=json.loads(a.context.read_text(encoding='utf-8')) if a.context else None)
