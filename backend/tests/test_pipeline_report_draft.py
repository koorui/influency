"""Manual draft/review endpoints are retired; delivery is covered by test_project_workflow."""

def test_manual_report_draft_is_retired(admin_client):
    response = admin_client.post('/api/admin/pipeline-reports/legacy-workflow/draft')
    assert response.status_code in (404, 405)
