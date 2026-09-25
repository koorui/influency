import io
import zipfile


def make_zip(entries):
    out=io.BytesIO()
    with zipfile.ZipFile(out,'w') as z:
        for name,value in entries:z.writestr(name,value)
    return out.getvalue()


def test_batch_upload_multiple_and_zip_with_rejections(admin_client):
    archive=make_zip([('nested/项目说明.txt','这是压缩包内项目说明。'),('../escape.txt','不应被解压'),('image.png',b'fake')])
    response=admin_client.post('/api/admin/materials/batch',files=[
        ('files',('one.txt','第一个材料。'.encode(),'text/plain')),
        ('files',('two.md','第二个材料。'.encode(),'text/markdown')),
        ('files',('bundle.zip',archive,'application/zip')),
        ('files',('bad.exe',b'exe','application/octet-stream')),
    ])
    assert response.status_code==207,response.text
    data=response.json()
    assert data['accepted_count']==3,data
    assert any('bad.exe' in row['filename'] for row in data['rejected'])
    assert any('escape.txt' in row['filename'] for row in data['rejected'])
    assert any('image.png' in row['filename'] for row in data['rejected'])
    assert len(admin_client.get('/api/admin/materials').json())>=3


def test_batch_upload_limits_and_bad_zip(admin_client):
    many=[('files',(f'{i}.txt',b'x','text/plain')) for i in range(201)]
    assert admin_client.post('/api/admin/materials/batch',files=many).status_code==413
    response=admin_client.post('/api/admin/materials/batch',files=[('files',('bad.zip',b'not zip','application/zip'))])
    assert response.status_code==207
    assert response.json()['rejected_count']==1


def test_plain_file_after_full_archive_is_rejected_explicitly_not_dropped(admin_client,monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings(),'batch_max_files',2)
    archive=make_zip([('a.txt','a'),('b.txt','b')])
    result=admin_client.post('/api/admin/materials/batch',files=[('files',('two.zip',archive)),('files',('extra.txt',b'extra'))]).json()
    assert result['accepted_count']==2 and result['rejected_count']==1
    assert result['rejected'][0]['filename']=='extra.txt'


def test_archive_expansion_limit_is_shared_across_batch(admin_client,monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings(),'archive_max_expanded_mb',1)
    first=make_zip([('a.txt','a'*550000)]);second=make_zip([('b.txt','b'*550000)])
    result=admin_client.post('/api/admin/materials/batch',files=[('files',('a.zip',first)),('files',('b.zip',second))]).json()
    assert result['accepted_count']==1 and result['rejected_count']==1
    assert result['rejected'][0]['filename']=='b.zip'


def test_batch_reference_purpose_is_stored(admin_client):
    result=admin_client.post('/api/admin/materials/batch',data={'purpose':'reference'},files=[('files',('reference.txt',b'reference'))]).json()
    assert result['accepted'][0]['purpose']=='reference'
