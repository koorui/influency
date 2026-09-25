import importlib.util
import json
import sys
from types import SimpleNamespace
from datetime import datetime
import pytest
from app.search_skill_loader import SEARCH_SKILL_ROOT
from app.pipeline_search_collection import validate_collected_result, load_script, bound_result_model, excerpt_bank, analysis_model

spec = importlib.util.spec_from_file_location('parse_public_search', SEARCH_SKILL_ROOT / 'scripts/parse_public_search.py')
parser = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = parser
spec.loader.exec_module(parser)


def test_bing_challenge_is_not_negative_search(tmp_path):
    (tmp_path / 'Q1.html').write_text('<html><h2>Verify you are human</h2></html>', encoding='utf-8')
    (tmp_path / 'receipts.json').write_text(json.dumps({'queries': [{'id': 'Q1', 'module': 'usage_media', 'channel': 'bing', 'status': 'response_received', 'file': 'Q1.html'}]}))
    result = parser.parse_archive(tmp_path)
    assert result['candidates'] == []
    assert result['queries'][0]['parse_status'] == 'unparsed_or_no_organic_results'


def test_empty_index_is_distinct_from_failure_and_metadata_stays_metadata(tmp_path):
    (tmp_path / 'Q1.json').write_text(json.dumps({'message': {'items': [{'title': ['Paper'], 'URL': 'https://doi.org/10.example/test', 'published': {'date-parts': [[2025]]}}]}}))
    (tmp_path / 'Q2.json').write_text('{"items": []}')
    (tmp_path / 'receipts.json').write_text(json.dumps({'queries': [
        {'id': 'Q1', 'module': 'sota', 'channel': 'crossref', 'status': 'response_received', 'file': 'Q1.json'},
        {'id': 'Q2', 'module': 'github', 'channel': 'github', 'status': 'response_received', 'file': 'Q2.json'},
        {'id': 'Q3', 'module': 'sota', 'channel': 'openalex', 'status': 'access_failed'}]}))
    result = parser.parse_archive(tmp_path)
    assert result['candidates'][0]['access_status'] == 'metadata_only'
    assert result['candidates'][0]['date_metadata']['published']['date-parts'] == [[2025]]
    assert result['queries'][1]['parse_status'] == 'parsed'
    assert result['queries'][2]['parse_status'] == 'access_failed'


def test_visible_text_excludes_scripts_and_preserves_quote():
    assert parser.visible_text('<p>Measured <b>121</b></p><script>fake 999</script>') == 'Measured\n121'


def test_exact_doi_resolves_single_crossref_record():
    collector = load_script('collect_public_search')
    assert collector.crossref_url('10.1038/s41524-025-01788-y') == 'https://api.crossref.org/works/10.1038%2Fs41524-025-01788-y'
    items, status = parser.parse_items('crossref', json.dumps({'message': {'title': ['Known paper'], 'URL': 'https://doi.org/10.1038/s41524-025-01788-y'}}))
    assert status == 'parsed'
    assert items[0]['title'] == 'Known paper'


def test_explicit_repository_url_uses_exact_lookup_without_claiming_historical_verification():
    collector=load_script('collect_public_search')
    assert collector.github_url('https://github.com/example/research.git')=='https://api.github.com/repos/example/research'
    items,status=parser.parse_items('github',json.dumps({'full_name':'example/research','html_url':'https://github.com/example/research','created_at':'2025-01-01T00:00:00Z'}))
    assert status=='parsed' and len(items)==1
    assert items[0]['historical_state_verified'] is False


def test_generation_contract_rejects_invented_claim_identity():
    model = bound_result_model(['C1', 'C2'], ['Q001-S01'])
    check_model = model.model_fields['checks'].annotation.__args__[0]
    data = {'id': 'J1', 'module': 'sota', 'claim_id': 'C-SOTA', 'conclusion': 'unverified',
            'status': 'not_verified', 'evidence_ids': [], 'protocol_notes': '',
            'execution_percent': None, 'execution_basis': '',
            'confidence': dict.fromkeys(['object_match', 'independence', 'protocol', 'time'], 'unknown')}
    with pytest.raises(ValueError):
        check_model.model_validate(data)
    data['claim_id'] = 'C1'
    assert check_model.model_validate(data).claim_id == 'C1'


def test_excerpt_choices_preserve_complete_text_without_inventing_quotes():
    text=('Measured enhancement was 121.\n' * 100)+'Final observation.'
    bank=excerpt_bank({'primary_source_texts':{'Q1-S01':text}})
    assert ' '.join(e['text'] for e in bank)==' '.join(text.split())
    assert all(e['source_id']=='Q1-S01' and len(e['text'])<=700 for e in bank)
    model=analysis_model(['C1'],['Q1-S01'],[e['id'] for e in bank])
    source_model=model.model_fields['sources'].annotation.__args__[0]
    assert 'quote' not in source_model.model_fields
    assert 'quote_ref' in source_model.model_fields
    assert 'queries' not in model.model_fields


def test_receipt_cannot_read_outside_archive(tmp_path):
    (tmp_path / 'receipts.json').write_text(json.dumps({'queries': [{'id': 'Q1', 'channel': 'crossref', 'status': 'response_received', 'file': '../secret.json'}]}))
    assert parser.parse_archive(tmp_path)['queries'][0]['parse_status'] == 'parse_failed'


def test_model_cannot_invent_quotes_or_hide_failed_queries():
    day = datetime.fromisoformat('2026-09-25T01:00:00+00:00').astimezone().date()
    collected = {'search': {'candidates': [{'id': 'Q1-S01', 'url': 'https://example.org/paper', 'module': 'sota', 'query_id': 'Q1'}],
        'queries': [{'id': 'Q1', 'module': 'sota', 'channel': 'crossref', 'query': 'paper', 'executed_at': '2026-09-25T01:00:00+00:00', 'candidate_ids': ['Q1-S01'], 'parse_status': 'parsed'},
                    {'id': 'Q2', 'module': 'usage_media', 'channel': 'bing', 'query': 'deployment', 'executed_at': '2026-09-25T01:00:00+00:00', 'candidate_ids': [], 'parse_status': 'access_failed'}]},
        'primary_source_receipts': {'sources': [{'id': 'Q1-S01', 'status': 'text_extracted'}]},
        'primary_source_texts': {'Q1-S01': 'Observed enhancement was 121.'}}
    source = SimpleNamespace(id='Q1-S01', url='https://example.org/paper', module='sota', accessed_at=day, access_status='full_text', quote='Observed enhancement was 121.')
    queries = [SimpleNamespace(module='sota', channel='crossref', query='paper', executed_at=day, source_ids=['Q1-S01'], outcome='results_found'),
               SimpleNamespace(module='usage_media', channel='bing', query='deployment', executed_at=day, source_ids=[], outcome='access_failed')]
    result = SimpleNamespace(sources=[source], queries=queries, search_date=day)
    validate_collected_result(result, collected)
    source.quote = 'Observed enhancement was 999.'
    with pytest.raises(ValueError, match='引文'):
        validate_collected_result(result, collected)
    source.quote = 'Observed enhancement was 121.'
    result.queries = queries[:1]
    with pytest.raises(ValueError, match='遗漏'):
        validate_collected_result(result, collected)
    result.queries = queries
    queries[1].outcome = 'no_verified_result'
    with pytest.raises(ValueError, match='失败'):
        validate_collected_result(result, collected)
