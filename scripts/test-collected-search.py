"""Run the actual pipeline Search executor against Raman original-material intake."""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app.pipeline_search import live_search_stage
from app.pipeline_store import atomic_json,implementation_fingerprint

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    folder = args.output.resolve()
    folder.mkdir(parents=True, exist_ok=False)
    intake_path = ROOT / 'backend/storage/pipelines/3a90af73-833f-4ef2-ac03-2778dd4d25e7/wu_intake/attempt-1/output.json'
    intake = json.loads(intake_path.read_text(encoding='utf-8'))
    inputs = {'search_mode': 'live', 'search_boundary': {'project_start_date': '2025-06-01',
        'review_cutoff': '2026-04-30',
        'cutoff_basis': '本成果Search交付的阶段边界：2026-04-30；六月里程碑报告为内部回顾性材料，不冒充此前公开来源。'}}
    atomic_json(folder / 'test-origin.json', {'intake_path': str(intake_path), 'inputs': inputs,'implementation_fingerprint':implementation_fingerprint(),
        'boundary': '使用原始材料的成果定位输出，不输入历史Search、吴老师或v19评价结论。'})
    result = live_search_stage(inputs, {'wu_intake': intake}, folder)
    atomic_json(folder / 'output.json', result)
    print(json.dumps({'fresh_search_executed': result['fresh_search_executed'],
        'evidence': len(result['replay']['evidence']), 'findings': len(result['replay']['findings'])}, ensure_ascii=False))
