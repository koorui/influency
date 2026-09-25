import json
from pathlib import Path

from app.models import PipelineJob, User
from app.pipeline_store import fingerprint
from app.db import Session


def test_unified_double_layer_endpoint_requires_both_layers(admin_client):
    with Session() as db:
        user = db.query(User).filter_by(username='admin').one()
        job = PipelineJob(title='统一双层测试', project_id='P', outcome_id='O', created_by=user.id, status='succeeded')
        db.add(job)
        db.commit()
        identifier = job.id
    root = Path(__import__('os').environ['STORAGE_DIR']) / 'pipelines' / identifier
    root.mkdir(parents=True)
    wu = {'rubric_id': 'wu', 'assessment': {'level_name': 'L2'}}
    v19 = {'rubric_id': 'unified-double-layer-impact.v1.v19-dimension-layer', 'result': {'project_synthesis': {'impact_level': {'level': 'L2'}, 'scope_impact_level': {'level': 'L1'}}}}
    wu_path = root / 'wu.json'; v19_path = root / 'v19.json'
    wu_path.write_text(json.dumps(wu), encoding='utf-8'); v19_path.write_text(json.dumps(v19), encoding='utf-8')
    stages = {name: {'status': 'succeeded', 'output': path, 'output_hash': fingerprint(value)} for name, path, value in [('wu_evaluation', 'wu.json', wu), ('v19_evaluation', 'v19.json', v19)]}
    for name in ('wu_intake', 'search_replay', 'attribution', 'export'):
        stages[name] = {'status': 'succeeded', 'output': 'unused.json', 'output_hash': fingerprint({})}
    (root / 'pipeline.json').write_text(json.dumps({'status': 'succeeded', 'stages': stages}), encoding='utf-8')
    response = admin_client.get(f'/api/admin/pipeline-reports/{identifier}/double-layer')
    assert response.status_code == 200
    body = response.json()
    assert body['evaluation_name'] == '双层影响力评价'
    assert body['levels'] == {'management_level': 'L2', 'dimension_level': 'L2', 'scope_level': 'L1'}
    assert '不相加' in body['rule']
