"""Structural and temporal checks. These do not prove research conclusions correct."""
from datetime import date
import json
from pathlib import Path
from typing import Literal
from pydantic import BaseModel,ConfigDict,Field,model_validator

Module=Literal['sota','prior_work','usage_media','github','indicator']
MODULES={'sota','prior_work','usage_media','github','indicator'}
TABLE_COLUMNS=json.loads((Path(__file__).resolve().parents[1]/'schemas/required-tables.json').read_text(encoding='utf-8'))
RESEARCH_TABLES=[name for name in TABLE_COLUMNS if name not in {'项目材料清单.csv','项目成果声明抽取表.csv','评审时间窗口表.csv','综合判断总表.csv','待线下核验材料清单.csv','证据总索引.csv','超出评审时间窗口排除清单.csv'}]
MANAGED_COLUMNS={'声明ID','证据ID','是否处于有效时间窗口'}
RESEARCH_COLUMNS=sorted({column for name in RESEARCH_TABLES for column in TABLE_COLUMNS[name]}-MANAGED_COLUMNS)

class Strict(BaseModel):
    model_config=ConfigDict(extra='forbid')

class Confidence(Strict):
    object_match: Literal['high','medium','low','unknown']
    independence: Literal['high','medium','low','unknown']
    protocol: Literal['high','medium','low','unknown']
    time: Literal['high','medium','low','unknown']

class Source(Strict):
    id: str
    module: Module
    title: str
    url: str
    publisher: str
    first_public_date: date | None
    event_date: date | None
    accessed_at: date
    access_status: Literal['full_text','metadata_only','blocked']
    quote: str
    claim_ids: list[str]
    relationship: Literal['internal','related','independent','unknown']
    supports: str
    does_not_prove: str
    confidence: Confidence

class Query(Strict):
    module: Module
    query: str
    channel: str
    executed_at: date
    outcome: Literal['results_found','no_verified_result','access_failed']
    source_ids: list[str]
    note: str

class Check(Strict):
    id: str
    module: Module
    claim_id: str
    conclusion: str
    status: Literal['supported','partial','conflicts','not_verified','not_applicable']
    evidence_ids: list[str]
    protocol_notes: str
    execution_percent: float | None = Field(ge=0,le=100)
    execution_basis: str
    confidence: Confidence

class ModuleStatus(Strict):
    id: Module
    status: Literal['completed','partial','blocked']
    summary: str
    limitations: list[str]


class TableCell(Strict):
    column: Literal[tuple(RESEARCH_COLUMNS)]
    value: str | None


class ResearchRecord(Strict):
    table: Literal[tuple(RESEARCH_TABLES)]
    cells: list[TableCell]
    source_ids: list[str]
    claim_ids: list[str]
    status: Literal['source_record','interpretation','unverified']
    limitation: str

    @model_validator(mode='after')
    def valid_columns(self):
        names=[c.column for c in self.cells]
        if len(set(names))!=len(names) or not set(names).issubset(TABLE_COLUMNS[self.table]):raise ValueError('专门表格列名未知或重复')
        if not self.source_ids and not self.claim_ids:raise ValueError('专门表格记录须关联真实来源或项目声明')
        return self

class SearchResult(Strict):
    schema_version: Literal['project-search.v1']
    project_id: str
    outcome_id: str
    project_start_date: date
    review_cutoff: date
    cutoff_basis: str
    search_date: date
    modules: list[ModuleStatus]
    sources: list[Source]
    queries: list[Query]
    checks: list[Check]
    limitations: list[str]
    research_records: list[ResearchRecord] = Field(default_factory=list)

    @model_validator(mode='after')
    def complete_structure(self):
        if {m.id for m in self.modules}!=MODULES or len(self.modules)!=5:raise ValueError('必须保留五个模块及实际执行状态')
        if self.project_start_date>self.review_cutoff:raise ValueError('项目开始时间晚于评审截止日')
        if self.search_date<self.review_cutoff:raise ValueError('不能声称检索审计未来的截止日期')
        ids={s.id for s in self.sources}
        if len(ids)!=len(self.sources):raise ValueError('证据ID重复')
        if len({c.id for c in self.checks})!=len(self.checks):raise ValueError('核验ID重复')
        for s in self.sources:
            if not s.url.startswith(('https://','http://')):raise ValueError('来源必须保留HTTP(S) URL')
            if s.access_status=='full_text' and not s.quote.strip():raise ValueError('全文核验必须保留原文片段')
        for q in self.queries:
            if not set(q.source_ids).issubset(ids):raise ValueError('检索日志引用不存在的来源')
            if q.executed_at!=self.search_date:raise ValueError('查询日期与本次执行日不一致')
        for c in self.checks:
            if not set(c.evidence_ids).issubset(ids):raise ValueError('结论引用不存在的来源')
            if c.status in ('supported','partial','conflicts') and not c.evidence_ids:raise ValueError('实质判断必须有证据')
            if c.execution_percent is not None and not c.execution_basis.strip():raise ValueError('执行度必须有明确计算依据')
        for m in self.modules:
            if m.status!='blocked' and not any(q.module==m.id for q in self.queries):raise ValueError('未记录实际查询的模块不能称为已检索')
        for row in self.research_records:
            if not set(row.source_ids).issubset(ids):raise ValueError('专门表格引用不存在的来源')
        return self

def time_status(source:Source,cutoff:date):
    if any(d and d>cutoff for d in [source.first_public_date,source.event_date]):return 'excluded_after_cutoff'
    if source.first_public_date is None or source.event_date is None:return 'unknown_date'
    if source.access_status!='full_text':return 'not_verified'
    return 'eligible'

def audit(result:SearchResult):
    sources={s.id:s for s in result.sources}
    statuses={s.id:time_status(s,result.review_cutoff) for s in result.sources}
    checks=[]
    for check in result.checks:
        item=check.model_dump(mode='json')
        eligible=[id for id in check.evidence_ids if statuses[id]=='eligible']
        item['eligible_evidence_ids']=eligible
        item['excluded_evidence_ids']=[id for id in check.evidence_ids if statuses[id]!='eligible']
        # Preserve model raw judgment but do not pass ineligible conclusions downstream.
        item['formal_status']=check.status if check.evidence_ids and len(eligible)==len(check.evidence_ids) else 'not_verified'
        item['formal_conclusion']=check.conclusion if item['formal_status']!='not_verified' else '现有引用未通过完整的时间/正文核验，原判断仅作为待核线索。'
        checks.append(item)
    return {'schema_version':'project-search-audit.v1','project_id':result.project_id,'outcome_id':result.outcome_id,
            'source_status':statuses,'checks':checks,'search_date':result.search_date.isoformat(),
            'review_cutoff':result.review_cutoff.isoformat(),'mode':'live_search','new_search_executed':bool(result.queries)}

if __name__=='__main__':
    import argparse,json
    from pathlib import Path
    p=argparse.ArgumentParser();p.add_argument('result',type=Path);a=p.parse_args()
    value=SearchResult.model_validate_json(a.result.read_text(encoding='utf-8'))
    print(json.dumps(audit(value),ensure_ascii=False,indent=2))
