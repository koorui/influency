import io
from openpyxl import Workbook


def test_xlsx_preserves_cell_locations_and_does_not_execute_formulas(admin_client):
    book=Workbook();sheet=book.active;sheet.title='指标记录';sheet['A1']='目标值';sheet['B2']=121;sheet['C3']='=B2*2'
    stream=io.BytesIO();book.save(stream)
    response=admin_client.post('/api/admin/materials',files={'file':('record.xlsx',stream.getvalue())})
    assert response.status_code==201,response.text
    material=admin_client.get('/api/admin/materials/'+response.json()['id']).json()
    assert '[指标记录!B2] 121' in material['text']
    assert '[公式，未执行或计算] =B2*2' in material['text']
    assert '242' not in material['text']


def test_reference_and_instruction_materials_cannot_enter_evaluation(admin_client,client):
    upload=admin_client.post('/api/admin/materials',files={'file':('reference.txt','这是参考评价，不能充当原始实验。'.encode())}).json()
    identifier=upload['id']
    assert client.patch(f'/api/admin/materials/{identifier}/purpose',json={'purpose':'reference'}).status_code==401
    classified=admin_client.patch(f'/api/admin/materials/{identifier}/purpose',json={'purpose':'reference'})
    assert classified.status_code==200 and classified.json()['purpose']=='reference'
    task=admin_client.post('/api/admin/tasks',json={'title':'示例','keywords':['示例'],'material_ids':[identifier],'adapter':'mock'})
    assert task.status_code==422,task.text
    pipeline=admin_client.post('/api/admin/pipelines',json={'title':'示例','project_name':'项目','project_id':'P','outcome_id':'A','material_ids':[identifier]})
    assert pipeline.status_code==422,pipeline.text
    assert admin_client.patch(f'/api/admin/materials/{identifier}/purpose',json={'purpose':'instruction'}).status_code==200
    assert admin_client.post('/api/admin/tasks',json={'title':'示例','keywords':['示例'],'material_ids':[identifier],'adapter':'mock'}).status_code==422


def test_queued_task_rechecks_material_purpose_before_invoking_model(admin_client,monkeypatch):
    from app.worker import run_once
    upload=admin_client.post('/api/admin/materials',files={'file':('source.txt','待确认用途的材料。'.encode())}).json()
    created=admin_client.post('/api/admin/tasks',json={'title':'队列用途复核','keywords':['复核'],'material_ids':[upload['id']],'adapter':'mock'})
    assert created.status_code==201,created.text
    admin_client.patch(f"/api/admin/materials/{upload['id']}/purpose",json={'purpose':'reference'})
    def forbidden(*args,**kwargs):raise AssertionError('No model should be called for reference material')
    monkeypatch.setattr('app.worker.get_adapter',forbidden)
    assert run_once()
    task=next(t for t in admin_client.get('/api/admin/tasks').json() if t['id']==created.json()['id'])
    assert task['status']=='failed' and '用途' in task['error']
