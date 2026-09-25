"""Explicit live Search pilot on Raman claims extracted from original materials.
Teacher reference reports and historical Search verdicts are excluded from model input.
"""
import argparse
from datetime import date
import importlib.util
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.search_skill_loader import contract,SEARCH_SKILL_ROOT
from app.pipeline_model import execute_json_stage
from app.pipeline_store import atomic_json

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);a=parser.parse_args()
    a.output=a.output.resolve();a.output.mkdir(parents=True,exist_ok=False)
    source=ROOT/'backend/storage/pipelines/3a90af73-833f-4ef2-ac03-2778dd4d25e7/wu_intake/attempt-1/output.json'
    intake=json.loads(source.read_text(encoding='utf-8'))
    today=date.today().isoformat()
    payload={'project_id':'P02','outcome_id':'RAMAN-CASE-001','project_name':'人工智能赋能有机化学','project_start_date':'2025-06-01',
             'review_cutoff':'2026-04-30','cutoff_basis':'本成果Search交付的阶段边界：2026-04-30；六月里程碑报告为内部回顾性材料，不冒充此前公开来源。',
             'search_date':today,'intake':intake['intake'],'project_original_evidence':intake['attribution_preparation']['evidence']}
    result=execute_json_stage(a.output,contract.SearchResult,payload,
        'Complete all FIVE Search modules for this one Raman outcome using ACTUAL web queries and primary-source opening. '
        'The host supplied project dates and raw project quotations. Do not use reference evaluation answers. '
        'Return exact project_id/outcome_id and dates. Preserve claim IDs from intake.claims. '
        'For each module record at least one real query, or mark blocked with the actual reason. '
        'Use approximately 8-12 targeted queries total; keep sources focused on decisive support, counterevidence and temporal exclusions. '
        'Distinguish OCNet antecedent model use from actual adoption of these two Raman probes. '
        'Do not call stars/forks, author papers or partner-team use independent deployment. '
        'If publication/event dates or source body are unavailable use null/metadata_only/blocked, not guessed dates or fake quotes. '
        'Capture dated repository evidence at or before cutoff; current repo state is not historical proof. '
        'Do not download or execute project code. Do not spend the task re-reading unrelated files. '
        'Explicitly separate objective measurement and execution_percent from subjective confidence. '
        'Ensure the full five-module JSON is returned even if some searches are blocked.',
        skill_root=SEARCH_SKILL_ROOT,timeout=900,live_search=True)
    atomic_json(a.output/'search-result.json',result.model_dump(mode='json'))
    atomic_json(a.output/'time-audit.json',contract.audit(result))
    sys.modules['search_contract']=contract
    spec=importlib.util.spec_from_file_location('search_export',SEARCH_SKILL_ROOT/'scripts/export_search.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    module.export(result,a.output/'artifacts')
    print('Live Search returned and temporal audit exported.',flush=True)
