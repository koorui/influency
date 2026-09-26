import json
from pathlib import Path
import pytest
from app.skill_loader import contract,SKILL_ROOT
from app.v19_response_contract import Grade,ImpactLevel
from app.pipeline_v19 import wrapper
from app.material_context import relevant_context
from app.pipeline_search_collection import load_script
from test_codex_adapter import fixture_assessment


def test_both_evaluators_use_document_ladder_and_require_actual_grades():
    wrapper()
    from metric_judgment.evaluation_policy import L_LEVEL_CRITERIA
    from metric_judgment.indicator_product import _normalize_level
    a=json.loads((SKILL_ROOT/'references/grading-standard-20260925.json').read_text(encoding='utf-8'))
    from metric_judgment.grading_standard import STANDARD, G_LEVEL_CRITERIA
    assert a==STANDARD==contract.STANDARD
    assert G_LEVEL_CRITERIA==a['g_level_criteria']
    assert L_LEVEL_CRITERIA=={k:v['name']+'：'+v['condition'] for k,v in a['levels'].items()}
    assert '独立外部' in a['levels']['L3']['meaning']
    for model in (Grade,ImpactLevel):
        with pytest.raises(ValueError):model(level='待确认',reason='证据少',source_ids=[],gap_to_next='补证')
    assert _normalize_level({'level':'G1','reason':'本轮材料未显示独立采用','source_ids':[]},'G',require_sources=True)['level']=='G1'


def test_final_report_keeps_grade_with_limited_evidence_but_blocks_false_upgrade():
    value=fixture_assessment()
    for d in value['dimensions']:d['grade']='G1';d['gaps']=['本轮材料没有建立更高成熟度']
    assessment=contract.FinalAssessment.model_validate(value)
    contract.validate_completed_assessment(assessment)
    value['dimensions'][2]['grade']='G3'
    with pytest.raises(ValueError):contract.FinalAssessment.model_validate(value)
    value['dimensions'][2]['grade']='G1';value['evaluation_status']='preliminary'
    with pytest.raises(ValueError):contract.FinalAssessment.model_validate(value)


def test_material_context_keeps_dated_original_lines_and_citation():
    text='无关资料\n'*1000+'累积五烯拉曼探针\n2026年2月26日完成第一轮验证。\n参考文献 s41524-025-01788-y\n'+'无关资料\n'*500
    result=relevant_context([{'id':'m','filename':'原件.txt','text':text}],['AI驱动高响应累积五烯拉曼探针'])
    assert any('2026年2月26日' in b['text'] and 's41524-025-01788-y' in b['text'] for b in result)
    assert sum(len(b['text']) for b in result)<46000


def test_publication_metadata_and_empty_navigation_are_not_full_text():
    load_script('parse_public_search');archive=load_script('archive_public_sources')
    metadata=archive.PublicationMetadata()
    metadata.feed('<meta name="citation_publication_date" content="2025/10/16"><meta name="citation_pdf_url" content="https://example.org/p.pdf">')
    assert metadata.dates==['2025-10-16'] and metadata.pdf_urls==['https://example.org/p.pdf']
    assert not archive.usable_body('Home Login Buy this chapter')
    assert not archive.usable_body('Verify you are human'+'.'*1000)
    assert archive.usable_body('Original research methodology. '*40)


def test_publication_dates_do_not_invent_adoption_event_dates():
    from app.search_skill_loader import contract as search_contract
    from test_search_time_audit import source
    from datetime import date
    cutoff=date(2026,4,30)
    assert search_contract.time_status(source(module='prior_work',event_date=None),cutoff)=='eligible'
    assert search_contract.time_status(source(module='usage_media',event_date=None),cutoff)=='unknown_date'
