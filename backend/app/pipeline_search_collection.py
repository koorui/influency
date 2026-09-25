"""Model-planned searches executed by an auditable public HTTP collector."""
import importlib.util
import json
import re
import sys
from datetime import datetime
from typing import Literal,Union
from pydantic import BaseModel, ConfigDict, Field, model_validator, create_model
from .pipeline_model import execute_json_stage
from .pipeline_store import atomic_json, WaitingForInput
from .search_skill_loader import SEARCH_SKILL_ROOT, contract


def load_script(name):
    spec = importlib.util.spec_from_file_location(name, SEARCH_SKILL_ROOT / 'scripts' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class QueryPlan(BaseModel):
    model_config = ConfigDict(extra='forbid')
    module: contract.Module
    channel: Literal['crossref', 'openalex', 'github', 'bing']
    query: str = Field(min_length=1, max_length=500)


class SearchPlan(BaseModel):
    model_config = ConfigDict(extra='forbid')
    queries: list[QueryPlan] = Field(min_length=5, max_length=15)

    @model_validator(mode='after')
    def modules_present(self):
        if {q.module for q in self.queries} != contract.MODULES:
            raise ValueError('检索计划须覆盖全部五模块')
        return self


class Selection(BaseModel):
    model_config = ConfigDict(extra='forbid')
    candidate_ids: list[str] = Field(max_length=15)
    rationale: str
    limitations: list[str]


def bound_result_model(claim_ids, candidate_ids):
    """Expose the actual identity vocabulary to structured generation, not only post-validation."""
    if not claim_ids:
        raise ValueError('成果定位未提供可核验声明')
    claim_type = Literal[tuple(claim_ids)]
    source_type = Literal[tuple(candidate_ids)] if candidate_ids else str
    bound_source = create_model('CollectedSource', __base__=contract.Source,
                                id=(source_type, ...), claim_ids=(list[claim_type], ...))
    bound_check = create_model('CollectedCheck', __base__=contract.Check,
                               claim_id=(claim_type, ...), evidence_ids=(list[source_type], ...))
    bound_query = create_model('CollectedQuery', __base__=contract.Query, source_ids=(list[source_type], ...))
    return create_model('CollectedSearchResult', __base__=contract.SearchResult,
                        sources=(list[bound_source], ...), checks=(list[bound_check], ...), queries=(list[bound_query], ...))


def excerpt_bank(collected):
    bank = []
    for identifier, text in collected['primary_source_texts'].items():
        normalized = ' '.join(text.split())
        # Complete sequential coverage; never select passages based on a desired conclusion.
        chunks = []
        while normalized:
            end = min(len(normalized), 700)
            if end < len(normalized):
                boundary = normalized.rfind(' ', 350, end)
                if boundary > 0: end = boundary
            chunks.append(normalized[:end])
            normalized = normalized[end:].lstrip()
        bank.extend({'id': f'{identifier}-T{n:04d}', 'source_id': identifier, 'text': text} for n, text in enumerate(chunks, 1))
    return bank


def research_record_type(claim_ids,source_ids):
    """Each table has its own typed cell object, preventing cross-table column drift."""
    variants=[]
    claim_type=Literal[tuple(claim_ids)] if claim_ids else str
    source_type=Literal[tuple(source_ids)] if source_ids else str
    for number,name in enumerate(contract.RESEARCH_TABLES,1):
        columns=create_model(f'ResearchColumns{number}',__base__=contract.Strict,
            **{column:(str|None,...) for column in contract.TABLE_COLUMNS[name] if column not in contract.MANAGED_COLUMNS})
        variants.append(create_model(f'ResearchTable{number}',__base__=contract.Strict,
            table=(Literal[name],...),cells=(columns,...),source_ids=(list[source_type],...),claim_ids=(list[claim_type],...),
            status=(Literal['source_record','interpretation','unverified'],...),limitation=(str,...)))
    return Union[tuple(variants)]


def normalize_records(records):
    return [{**row,'cells':[{'column':key,'value':value} for key,value in row['cells'].items()]} if isinstance(row['cells'],dict) else row for row in records]


def analysis_model(claim_ids, candidate_ids, excerpt_ids):
    bound = bound_result_model(claim_ids, candidate_ids)
    original_source = bound.model_fields['sources'].annotation.__args__[0]
    ref_type = Literal[tuple(excerpt_ids)] | None if excerpt_ids else type(None)
    referenced_source = create_model('ReferencedSource', __base__=contract.Strict,
        **{name: (field.annotation, field) for name, field in original_source.model_fields.items() if name not in ('quote','accessed_at','url')},
        quote_ref=(ref_type, ...))
    return create_model('CollectedSearchAnalysis', __base__=contract.Strict,
        **{name: (field.annotation, field) for name, field in bound.model_fields.items() if name not in ('queries', 'sources','research_records')},
        sources=(list[referenced_source], ...),research_records=(list[research_record_type(claim_ids,candidate_ids)],...))


def with_actual_queries(analysis, collected):
    """Query execution facts come from collector receipts, never model transcription."""
    values = analysis.model_dump(mode='json')
    values['research_records']=normalize_records(values.get('research_records',[]))
    bank = {e['id']: e for e in excerpt_bank(collected)}
    candidates={c['id']:c for c in collected['search']['candidates']}
    queries_by_id={q['id']:q for q in collected['search']['queries']}
    primary={r['id']:r for r in collected['primary_source_receipts']['sources']}
    for source in values['sources']:
        candidate=candidates[source['id']]
        source['url']=candidate['url']
        timestamp=primary.get(source['id'],{}).get('retrieved_at') or queries_by_id[candidate['query_id']]['executed_at']
        source['accessed_at']=datetime.fromisoformat(timestamp).astimezone().date().isoformat()
        ref = source.pop('quote_ref')
        if ref is not None and (ref not in bank or bank[ref]['source_id'] != source['id']):
            raise ValueError('引文片段不属于该来源')
        source['quote'] = bank[ref]['text'] if ref is not None else ''
    source_ids = {s['id'] for s in values['sources']}
    queries = []
    for receipt in collected['search']['queries']:
        linked = [i for i in receipt['candidate_ids'] if i in source_ids]
        failed = receipt['parse_status'] in ('access_failed', 'parse_failed', 'unparsed_or_no_organic_results')
        queries.append({'module': receipt['module'], 'query': receipt['query'], 'channel': receipt['channel'],
            'executed_at': datetime.fromisoformat(receipt['executed_at']).astimezone().date().isoformat(),
            'outcome': 'access_failed' if failed else 'results_found' if linked else 'no_verified_result',
            'source_ids': linked,
            'note': f"实际请求{receipt['id']}；解析状态{receipt['parse_status']}；候选{len(receipt['candidate_ids'])}条，报告引用{len(linked)}条。找到候选不代表证据核实；未引用不代表全网不存在。"})
    return contract.SearchResult.model_validate({**values, 'queries': queries})


def collect_for_stage(payload, folder):
    planner = folder / 'query-plan'
    planner.mkdir()
    plan = execute_json_stage(planner, SearchPlan, payload,
        'Plan 8-12 targeted public searches covering all five modules. No network or shell requests. '
        'Use exact paper titles and distinctive scientific terms from original claims. '
        'When input contains a DOI, include the COMPLETE DOI as a standalone Crossref query (e.g. 10.xxxx/suffix). '
        'Use short title-only queries for known papers; do not append every topic, author and metric to a single query. '
        'Generic OCNet finds unrelated computer vision projects; qualify with organic chemistry and authors. '
        'Use English terms for international scientific indexes, and Chinese terms where appropriate. '
        'Use Bing for independent use/media, Crossref/OpenAlex for papers, GitHub for repositories. '
        'This is a plan only, never claim searches executed.', skill_root=SEARCH_SKILL_ROOT,inline_input=True)
    collector = load_script('collect_public_search')
    parser = load_script('parse_public_search')
    archiver = load_script('archive_public_sources')
    collector.collect(plan.model_dump(), folder / 'public-search')
    parsed = parser.parse_archive(folder / 'public-search')
    atomic_json(folder / 'candidates.json', parsed)
    if not any(q['parse_status'] in ('parsed', 'organic_headings_only') for q in parsed['queries']):
        raise WaitingForInput('公共检索均未返回可解析结果；已保存失败记录，需要恢复检索能力后重试')
    selector = folder / 'source-selection'
    selector.mkdir()
    selected = execute_json_stage(selector, Selection, {'task': payload, 'search': parsed},
        'Select up to 15 relevant candidate IDs for primary-page opening. Do not request network access. '
        'Exclude unrelated same-name projects and off-topic results. Preserve IDs exactly. '
        'Include counterevidence and sources whose date may exclude them. Empty selection is honest if none match. '
        'Selection does not establish evidence strength or historical eligibility.', skill_root=SEARCH_SKILL_ROOT,inline_input=True)
    by_id = {c['id']: c for c in parsed['candidates']}
    if len(set(selected.candidate_ids)) != len(selected.candidate_ids) or any(i not in by_id for i in selected.candidate_ids):
        raise ValueError('原文选择引用未知或重复候选ID')
    receipts = archiver.archive_sources([{'id': i, 'url': by_id[i]['url']} for i in selected.candidate_ids], folder / 'primary-sources')
    texts = {}
    for record in receipts['sources']:
        if record.get('text_file'):
            texts[record['id']] = (folder / 'primary-sources' / record['text_file']).read_text(encoding='utf-8')
    return {'search': parsed, 'primary_source_receipts': receipts, 'primary_source_texts': texts,
            'selection': selected.model_dump()}


def validate_collected_result(result, collected):
    """Reject fabricated requests, URLs, source identity, or quotations before time audit."""
    candidates = {c['id']: c for c in collected['search']['candidates']}
    texts = collected['primary_source_texts']
    receipts = {r['id']: r for r in collected['primary_source_receipts']['sources']}
    normalize = lambda text: ' '.join(text.split())
    for source in result.sources:
        candidate = candidates.get(source.id)
        if not candidate or source.url != candidate['url']:
            raise ValueError(f'Search来源未对应真实检索候选：{source.id}')
        query_by_id={q['id']:q for q in collected['search']['queries']}
        stamp=receipts.get(source.id,{}).get('retrieved_at') or query_by_id[candidate['query_id']]['executed_at']
        if source.accessed_at != datetime.fromisoformat(stamp).astimezone().date():
            raise ValueError(f'来源采集日期与本次执行日不一致：{source.id}')
        if source.access_status == 'full_text':
            if receipts.get(source.id, {}).get('status') != 'text_extracted':
                raise ValueError(f'未取得来源正文：{source.id}')
            if normalize(source.quote) not in normalize(texts[source.id]):
                raise ValueError(f'来源引文与归档正文不符：{source.id}')
        elif source.quote:
            actual = texts.get(source.id, '') + '\n' + json.dumps(candidate, ensure_ascii=False)
            if normalize(source.quote) not in normalize(actual):
                raise ValueError(f'来源摘要引文与归档不符：{source.id}')
    actual_queries = {(q['module'], q['channel'], q['query']): q for q in collected['search']['queries']}
    seen = set()
    for query in result.queries:
        key = (query.module, query.channel, query.query)
        receipt = actual_queries.get(key)
        if not receipt or key in seen:
            raise ValueError('检索日志与实际请求不一致或重复')
        seen.add(key)
        executed = datetime.fromisoformat(receipt['executed_at']).astimezone().date()
        if query.executed_at != executed:
            raise ValueError('检索日期与实际请求日期不一致')
        if not set(query.source_ids).issubset(set(receipt['candidate_ids'])):
            raise ValueError('检索日志关联了另一次查询的来源')
        failed = receipt['parse_status'] in ('access_failed', 'parse_failed', 'unparsed_or_no_organic_results')
        if failed and query.outcome != 'access_failed':
            raise ValueError('访问/解析失败不能记成无结果或成功检索')
        if query.outcome == 'results_found' and not query.source_ids:
            raise ValueError('检索称找到结果但未保留关联来源')
    if seen != set(actual_queries):
        raise ValueError('模型遗漏实际检索请求，包括失败请求')
