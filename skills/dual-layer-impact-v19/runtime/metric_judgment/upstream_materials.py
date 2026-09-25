"""Bring delivered upstream tables into the workbench without inventing facts."""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from .citation_materials import citation_subject, citation_record_fields

REVIEW_PATH = Path(__file__).with_name('upstream_material_review.json')

# Table roles only select a review shelf, never a frozen outcome or a positive judgment.
ROLE_BRANCHES = {
    'use_and_deployment':['D5.2'], 'external_evaluation_and_citation':['D3.2','D7.1'],
    'media':['D7.2'], 'internal_reported_use':['D5.1'], 'prior_results_trace':['D2.1'],
    'sota_and_metric_validation':['D1.2','D1.3'], 'negative_search_and_exclusions':[],
}
TABLE_BRANCHES = {
    '申报成果复用判断表':['D2.1'], '项目成果时间归属与复用判断表':['D2.1'],
    '成果使用与评价总表':['D3.2','D4.3','D5.2','D7.1'],
    '指标可比性与参数差异表':['D1.2','D1.3'],
}


def _first(row, keys):
    return next((str(row[k]) for k in keys if row.get(k)), '')


def _sources(row, table, ordinal, package, source_id):
    quote = '\n'.join(f'{key}：{value}' for key,value in row.items() if value)
    urls = re.findall(r'https?://[^\s;；<>"，]+', ' '.join(str(row.get(key) or '') for key in
                     ['原始URL','URL','DOI或URL','doi','landing','openalex_id','pdf']))
    sources = [{'source_id':source_id,'title':f"上游核验表：{table['table_name']}",
                'locator':f"{table['relative_path']} · 第 {ordinal} 条数据记录",'quote':quote,
                'event_date':_first(row,['日期','证据日期','使用日期','评价或引用日期','首次公开日期','公开时间','publication_date']),
                'quality_note':'这是已交付核验表的原文，不是所引论文或网页的逐字原文。',
                'archive_file':str(package),'local_member':table['relative_path']}]
    raw_paths = _first(row,['本地证据','本地相对路径','本地原文','本地文件','本地相对路径','本地成果证据','相对路径'])
    for part in re.split('[;；]',raw_paths):
        member = part.strip().replace('\\','/')
        if not member:
            continue
        # All paths are relative to a delivered table/module, and must stay in the package.
        candidates=[]
        for base in [package / Path(table['relative_path']).parent, package]:
            target=(base/member).resolve()
            if target.is_relative_to(package) and target.is_file():
                candidates.append(target)
            elif target.is_relative_to(package) and '*' in member:
                candidates.extend(p.resolve() for p in base.glob(member) if p.is_file() and p.resolve().is_relative_to(package))
        for path in dict.fromkeys(candidates):
            sources.append({'source_id':source_id,'title':path.name,'archive_file':str(package),
                            'local_member':path.relative_to(package).as_posix(),
                            'quality_note':'上游表中所列附件；附件内容与核验表摘要应分别核对。'})
        if not candidates:
            sources.append({'source_id':source_id,'title':'上游所列附件（路径待核对）','locator':member,
                            'quality_note':'未按表格相对路径找到唯一文件，不能视为附件原文已接入。'})
    for url in dict.fromkeys(urls):
        sources.append({'source_id':source_id,'title':'上游列出的原始网页','url':url.rstrip('。)）'),
                        'quality_note':'保留上游链接；本轮没有重新联网核验。'})
    return sources


def import_upstream_materials(external, project_id, cards, outcome_contracts):
    package=Path(external.get('repository_root') or '.') .resolve()
    review=json.loads(REVIEW_PATH.read_text(encoding='utf8')) if REVIEW_PATH.is_file() else {}
    records=[]
    seen=set()
    indexed={}
    for table in external.get('repository_tables') or []:
        if table.get('table_name') not in {'evidence_index','证据总索引','证据索引'}:
            continue
        for ordinal, raw in enumerate(table.get('rows') or [],1):
            eid=_first(raw,['证据ID','SourceID','ID'])
            if eid:
                indexed.setdefault(eid,[]).append((table,ordinal,raw))
    for table in external.get('repository_tables') or []:
        name=table.get('table_name') or ''
        role=table.get('role') or ''
        # Already represented by the primary external-claim importer.
        if name in {'claims_summary','claim_verification','项目成果声明抽取表'}:
            continue
        if role not in ROLE_BRANCHES and name not in TABLE_BRANCHES:
            continue
        is_citation_table = name.startswith('openalex_citing_summary_')
        subject = citation_subject(table, project_id, package) if is_citation_table else None
        for ordinal, raw in enumerate(table.get('rows') or [],1):
            exact=json.dumps(raw,ensure_ascii=False,sort_keys=True)
            # The same citing paper can cite multiple subjects. Preserve each edge.
            identity_key = (table['relative_path'], exact) if is_citation_table else exact
            if identity_key in seen:
                continue
            seen.add(identity_key)
            source_id=f"UP-{project_id}-{table['table_id']}-{ordinal:03}"
            identity=_first(raw,['ID','声明ID','成果ID','证据ID']) or str(ordinal)
            reviewed=review.get(project_id,{}).get(table['relative_path'],{}).get(identity) or {}
            unchanged=bool(reviewed and reviewed.get('row')==raw)
            branches=reviewed['branch_ids'] if unchanged else TABLE_BRANCHES.get(name,ROLE_BRANCHES.get(role,[]))
            targets=reviewed.get('outcome_ids',[]) if unchanged else []
            citation_fields = citation_record_fields(raw, subject) if subject else {}
            if is_citation_table:
                # A citation index cannot default to professional endorsement.
                branches = subject['branch_ids'] if subject else ['D3.1']
                targets = subject['outcome_ids'] if citation_fields.get('association_eligible') else []
            valid=[c['outcome_id'] for c in cards if c.get('outcome_id') in targets
                   and {k:c.get(k) for k in ('title','child_outcome_ids')}==outcome_contracts.get(c.get('outcome_id'))
                   and set(citation_fields.get('subject_child_outcome_ids') or []) <= set(c.get('child_outcome_ids') or [])]
            record={
                'record_id':source_id,'source_id':source_id,'upstream_id':identity,
                'title':_first(raw,['成果','成果名称','成果/技术线','项目申报成果','申报成果或组件','论文题目','专利名称','标题']) or name,
                'provider':'外部检索组原有交付','kind':role,'table_name':name,'raw_fields':copy.deepcopy(raw),
                'statement':_first(raw,['使用或评价内容','公开证据与评价','评价内容','项目期新增内容','主要方法或成果','判断','结论']) or '\n'.join(f'{k}：{v}' for k,v in raw.items() if v),
                'limitation':_first(raw,['防误用','误用风险','风险说明','限制说明','备注','防误用结论']),
                'branch_ids':branches,'outcome_ids':valid,
                'scope':'已对应成果与分支，待核验内容' if valid else '项目参考材料，成果对应待核对',
                'review_status':'已核对材料归属' if unchanged else '需核对具体成果与用途',
                'sources':_sources(raw,table,ordinal,package,source_id),
            }
            if citation_fields:
                record.update(citation_fields)
                record['review_status'] = '被引论文与成果范围已对应；引用内容待核验' if valid else '成果对应待核对'
                record['sources'].append({'source_id': source_id, 'title': '被引论文身份信息：'+subject['name'],
                    'archive_file': str(package), 'local_member': subject['metadata_path'],
                    'quality_note': '用于确认被引对象的题名和DOI；不能代替引用论文原文。'})
            if not valid:
                record['reference_reason'] = record.get('reference_reason') or (
                    '尚未接入已确认的成果清单。' if not cards else
                    '被引论文的身份或成果范围尚未确认。' if is_citation_table else
                    '此记录为缺口或时间范围说明，尚无明确的单项成果用途。' if not branches else
                    '材料已归集，尚未完成具体成果和用途的对应核对。')
            citations = re.split(r'[;,；、\s]+',_first(raw,['证据ID','核心证据ID']))
            for eid in citations:
                found=indexed.get(eid,[])
                scoped=[entry for entry in found if entry[0].get('module')==table.get('module')]
                choices=scoped or [entry for entry in found if entry[0].get('table_name')=='证据总索引']
                if len(choices)==1:
                    index_table,index_ordinal,index_row=choices[0]
                    for attachment in _sources(index_row,index_table,index_ordinal,package,source_id):
                        if attachment not in record['sources']:
                            record['sources'].append(attachment)
            if reviewed and not unchanged:
                record['branch_ids']=[]
                record['limitation']='上游记录发生变化，原有对应关系停止使用，需重新核对。'
            records.append(record)
    return {'records':records,'summary':{'record_count':len(records),
            'outcome_scoped_count':sum(bool(r['outcome_ids']) for r in records),
            'project_reference_count':sum(not r['outcome_ids'] for r in records),
            'citation_relation_count':sum(bool(r.get('citation')) for r in records),
            'reference_reasons':{reason:sum(r.get('reference_reason')==reason and not r['outcome_ids'] for r in records)
                                 for reason in sorted({r['reference_reason'] for r in records if not r['outcome_ids']})},
            'attached_local_files':len({(s.get('archive_file'),s.get('local_member')) for r in records for s in r['sources'] if s.get('local_member')}),
            'policy':'全部记录保留提供方原文与限制；项目参考不自动进入单项成果评价，未检出和安装失败不改写成不存在或成功使用。'}}
