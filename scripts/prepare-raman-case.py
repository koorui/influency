"""Prepare reproducible source-only Raman input and substantive historical Search replay.
Reference answers and completed attribution outputs are deliberately never read here.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
from pypdf import PdfReader

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT.parent/'9.23'

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

def prepare(destination):
    destination.mkdir(parents=True,exist_ok=False)
    base=SOURCE/'项目成果search/拉曼探针'
    evidence_dir=base/'支撑证据/evidence'
    navigation=json.loads((evidence_dir/'MET-E002_本成果页码导航.json').read_text(encoding='utf-8'))
    original=next((SOURCE/'有机化学').glob('*里程碑报告*.pdf'))
    sha=digest(original)
    if sha!=navigation['原件SHA256']:raise ValueError('原始报告哈希与交付页码导航不一致')
    reader=PdfReader(original)
    pages=sorted(set([1,*navigation['建议阅读物理页序（从1计数）']]))
    passages=[]
    for page in pages:
        passages.append(f'\n[原报告物理第{page}页]\n'+(reader.pages[page-1].extract_text() or ''))
    name='project-original-pages.txt'
    (destination/name).write_text(f'原文件：{original.name}\nSHA256：{sha}\n以下仅为指定物理页原文，不含我方评价。\n'+''.join(passages),encoding='utf-8')
    index=base/'支撑证据/证据索引.csv'
    rows=list(csv.DictReader(index.open(encoding='utf-8-sig')))
    replay=[];provenance=[]
    excluded={'MET-E001','MET-E002','INPUT-RAM'}
    for row in rows:
        if row['证据ID'] in excluded:continue
        local=[];quotes=[]
        for relative in row['本地相对路径'].split(';'):
            if not relative:continue
            path=(base/relative).resolve()
            if not path.is_relative_to(base.resolve()) or not path.is_file():
                raise ValueError('Search交付原件缺失或路径无效：'+relative)
            local.append({'path':relative,'sha256':digest(path),'size':path.stat().st_size})
            # Use actual archived text for direct quotations; label catalogue interpretations separately.
            if path.suffix=='.txt':
                text=path.read_text(encoding='utf-8-sig')
                quotes.append({'path':relative,'excerpt':text[:18000],'excerpt_truncated':len(text)>18000})
            elif path.suffix=='.pdf' and row['证据ID']=='IMP-E036':
                pdf=PdfReader(path)
                quotes.append({'path':relative,'excerpt':'\n'.join(f'[物理第{i+1}页]\n'+(pdf.pages[i].extract_text() or '') for i in [0,6] if i<len(pdf.pages)),'excerpt_truncated':True})
        body={'record_type':'historical_search_delivery','title':row['来源标题'],'source_type':row['证据类型'],
              'source_date':row['首次公开/事件日期'],'retrieved_at':row['采集日期'],'evaluation_cutoff':row['评审基准日'],
              'historical_support_or_limit':row['核心支持/限制'],'scope':row['时间窗口判断'],
              'original_urls':row['原始URL'],'archive_manifest':local,'archived_original_excerpts':quotes,
              'note':'索引中的支持/限制属于历史核验结论；仅archived_original_excerpts是已归档原文。未执行新Search。'}
        urls=[v for v in row['原始URL'].split(';') if v.startswith(('http://','https://'))]
        replay.append({'id':row['证据ID'],'project_id':'P02','outcome_id':'RAMAN-CASE-001','source_type':'search',
                       'locator':f'证据索引.csv / {row["证据ID"]}','text':json.dumps(body,ensure_ascii=False),'url':urls[0] if urls else None})
        provenance.extend(local)
    search={'schema_version':'search-replay.v1','project_id':'P02','outcome_id':'RAMAN-CASE-001','mode':'historical_replay',
            'original_run_id':'raman-delivered-search-20260915','original_completed_at':'2026-09-15','source_label':'用户交付拉曼探针独立证据包；按证据索引逐项核对归档文件','evidence':replay,'findings':[]}
    (destination/'search-replay.json').write_text(json.dumps(search,ensure_ascii=False,indent=2),encoding='utf-8')
    manifest={'project_id':'P02','outcome_id':'RAMAN-CASE-001','project_number':'2025ZD0121900','original':str(original),'original_sha256':sha,
              'physical_pages':pages,'internal_materials':[name],'search_records':len(replay),'archived_files':len(provenance),
              'excluded_from_model':['既有AI贡献归因结果','吴老师参考输出报告','HTML中的示例评价结论','Search综合评估作为项目原始声明']}
    (destination/'source-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'directory':str(destination),'pages':len(pages),'search_records':len(replay),'archive_files':len(provenance)},ensure_ascii=False))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args();prepare(args.output.resolve())
