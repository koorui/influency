import importlib.util
import json
from pathlib import Path
import pytest
from app.pipeline_store import PipelineStore




def test_real_case_manifest_uses_original_pages_and_substantive_search():
    root=Path(__file__).resolve().parents[2]
    case=root/'backend/storage/raman-case-source-v1'
    if not case.exists():pytest.skip('Local real source package not installed in this environment')
    manifest=json.loads((case/'source-manifest.json').read_text(encoding='utf-8'))
    replay=json.loads((case/'search-replay.json').read_text(encoding='utf-8'))
    assert manifest['physical_pages'] and manifest['original_sha256']
    assert len(replay['evidence'])==6
    assert replay['original_completed_at']=='2026-09-15'
    assert {'IMP-E036','NEW-RAM-003'}.issubset({e['id'] for e in replay['evidence']})
    for e in replay['evidence']:
        data=json.loads(e['text'])
        assert data['archive_manifest']
        assert all(v['sha256'] for v in data['archive_manifest'])
    assert '综合评估' not in ''.join(manifest['internal_materials'])
