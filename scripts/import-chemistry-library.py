"""Ingest the provided original chemistry directory, preserving bytes and recording roles."""
import hashlib
import json
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.db import Session
from app.models import Material,User,Audit
from app.main import _extract_text,_store_material
from app.config import settings
from app.pipeline_store import atomic_json,timestamp
from sqlalchemy import select

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    return h.hexdigest()

if __name__=='__main__':
    source=ROOT.parent/'9.23/有机化学';os.chdir(ROOT/'backend')
    destination=Path(settings().storage_dir).resolve()/'chemistry-library';destination.mkdir(exist_ok=True)
    records=[];classified=[]
    with Session() as db:
        user=db.scalar(select(User).where(User.username=='admin',User.role=='admin'))
        if not user:raise ValueError('管理员不存在')
        for path in sorted(source.iterdir()):
            if not path.is_file():continue
            digest=sha(path)
            row=db.scalar(select(Material).where(Material.sha256==digest).order_by(Material.created_at).limit(1))
            action='existing'
            if not row:
                content=path.read_bytes();text=_extract_text(path.name,content)
                row=_store_material(db,user,'有机化学/'+path.name,content,text);action='imported'
            purpose='instruction' if path.name=='AI4S项目-里程碑-测试大纲修改要求.docx' else 'project'
            if row.purpose!=purpose:
                row.purpose=purpose;db.add(Audit(actor=user.id,action='material_purpose_'+purpose,target=row.id))
            stored=Path(settings().storage_dir).resolve()/row.storage_key
            if not stored.is_file() or sha(stored)!=digest:raise ValueError('库中原件与交付文件不一致：'+path.name)
            records.append({'source':str(path),'material_id':row.id,'filename':row.filename,'sha256':digest,'bytes':path.stat().st_size,
                            'text_characters':len(row.text),'purpose':purpose,'action':action,'original_copy_verified':True})
            db.commit();print(json.dumps({'file':path.name,'action':action,'purpose':purpose},ensure_ascii=False),flush=True)
        # Exact byte matching to the explicitly designated reference directory;
        # do not classify arbitrary user files solely by a similar filename.
        references=ROOT.parent/'9.23/项目成果search'
        reference_hashes={sha(p):str(p) for p in references.rglob('*.docx') if p.name in ('综合评估.docx','凝练评估.docx','送检样例.docx')}
        for row in db.scalars(select(Material)):
            if row.sha256 in reference_hashes:
                if row.purpose!='reference':
                    row.purpose='reference';db.add(Audit(actor=user.id,action='material_purpose_reference',target=row.id))
                classified.append({'material_id':row.id,'filename':row.filename,'matched_reference':reference_hashes[row.sha256]})
        db.commit()
    atomic_json(destination/'manifest.json',{'imported_at':timestamp(),'source_directory':str(source),'records':records,'reference_materials':classified,
        'storage':'原件在后端storage目录；MySQL保存索引、用途、SHA256及提取正文。备份需同时保留数据库和原件目录。',
        'boundary':'原始资料与参考评价/流程说明分开登记；Excel公式仅保留文本，不执行或重算。'})
    print(json.dumps({'original_files':len(records),'reference_materials_classified':len(classified)},ensure_ascii=False))
