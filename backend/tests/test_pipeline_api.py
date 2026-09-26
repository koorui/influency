"""Standalone pipelines are retired in favor of project-scoped requests."""
import pytest

@pytest.mark.parametrize('method,path', [
    ('post', '/api/admin/pipelines'),
    ('patch', '/api/admin/pipelines/legacy-workflow'),
    ('post', '/api/admin/pipelines/legacy-workflow/resume'),
])
def test_standalone_pipeline_mutations_are_retired(admin_client, method, path):
    assert getattr(admin_client, method)(path, json={}).status_code in (404, 405)
