"""Extract original-format table records from the same archived Search evidence.
Does not change prior checks, grades, source dates or the downstream Search handoff.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
from typing import Literal
from pydantic import create_model
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.search_skill_loader import contract,SEARCH_SKILL_ROOT
from app.pipeline_model import execute_json_stage
from app.pipeline_search_collection import excerpt_bank,research_record_type,normalize_records
from app.pipeline_store import atomic_json,fingerprint

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--collection',type=Path,required=True);p.add_argument('--validated',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    origin=a.collection.resolve();validated=a.validated.resolve();folder=a.output.resolve();folder.mkdir(parents=True,exist_ok=False)
    payload=json.loads((origin/'input.json').read_text(encoding='utf-8'));collected=payload.pop('collected')
    result=contract.SearchResult.model_validate_json((validated/'search-result.json').read_text(encoding='utf-8'))
    claim_ids=[c['id'] for c in payload['intake']['claims']];source_ids=[s.id for s in result.sources]
    record=research_record_type(claim_ids,source_ids)
    output_model=create_model('RequiredResearchTables',__base__=contract.Strict,research_records=(list[record],...))
    stage=folder/'table-extraction';stage.mkdir()
    data={'project':payload,'validated_search':result.model_dump(mode='json'),'primary_source_excerpts':excerpt_bank(collected),
          'index_candidates':collected['search']['candidates'],'required_columns':contract.TABLE_COLUMNS}
    extracted=execute_json_stage(stage,output_model,data,
        'This pass ONLY extracts research_records for the original Chinese report tables from already archived evidence. '
        'No network requests, no changes to existing Search checks or dates, no G/L evaluation. '
        'Populate relevant factual and limitation records instead of leaving all tables empty. Use exact column names. '
        'For this generation pass cells is the table-specific object defined in the schema; fill every listed column with a string or null. '
        'The program fills 声明ID, 证据ID and 是否处于有效时间窗口 from claim_ids/source_ids and time audit; do not repeat those columns in cells. '
        'Known papers may be recorded as candidate bibliography with team identity explicitly unverified; do not assert they are team antecedents. '
        'A source published after project start is not a pre-project outcome. Unknown event dates remain unknown. '
        'Do not infer deployment or independent use from citation, affiliations or author statements. '
        'Do not invent patents, estimates, member identity or comparable metrics. Use null for unavailable cells. '
        'Record comparison protocol limitations and potential misattribution boundaries where evidence warrants. '
        'Each row cites permitted source_ids or claim_ids; these are provisional source records, not verified scientific conclusions. '
        'Limit to 30 substantive rows; unavailable categories may stay empty with their gaps already retained in the report.',
        skill_root=SEARCH_SKILL_ROOT,inline_input=True,timeout=600)
    updated=contract.SearchResult.model_validate({**result.model_dump(mode='json'),'research_records':normalize_records([r.model_dump(mode='json') for r in extracted.research_records])})
    atomic_json(folder/'enriched-search-result.json',updated.model_dump(mode='json'))
    sys.modules['search_contract']=contract
    spec=importlib.util.spec_from_file_location('search_table_export',SEARCH_SKILL_ROOT/'scripts/export_search.py');exporter=importlib.util.module_from_spec(spec);spec.loader.exec_module(exporter)
    exporter.export(updated,folder/'report',collection_root=origin,context=payload)
    atomic_json(folder/'provenance.json',{'collection':str(origin),'validated_analysis':str(validated),'original_result_hash':fingerprint(result.model_dump(mode='json')),
        'new_http_requests':False,'new_model_call':True,'scientific_checks_changed':False,'source_dates_changed':False,'downstream_handoff_changed':False,
        'record_count':len(updated.research_records)})
    print(json.dumps({'status':'exported','research_records':len(updated.research_records)},ensure_ascii=False))
