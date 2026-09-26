"""Import chemistry originals into the administrator material library without running evaluation."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))

from sqlalchemy import select
from app.config import settings
from app.db import Session
from app.main import SUPPORTED_MATERIALS, _extract_text, _store_material
from app.models import Material, User


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--username', default='admin')
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    if not source.is_dir():
        raise ValueError('Source must be a directory')
    storage = Path(settings().storage_dir).resolve()
    receipt = storage / 'chemistry-library' / 'manifest.json'
    if receipt.exists():
        raise ValueError(f'An import receipt already exists; review it before importing again: {receipt}')
    # Import extracted originals only; a sibling ZIP is not imported a second time.
    files = sorted(p for p in source.rglob('*') if p.is_file() and p.suffix.lower() in SUPPORTED_MATERIALS)
    if not files:
        raise ValueError('No supported original files found')
    records, created_paths = [], []
    committed = False
    try:
        with Session() as db:
            user = db.scalar(select(User).where(User.username == args.username, User.role == 'admin'))
            if not user:
                raise ValueError('Administrator account not found')
            for path in files:
                filename = '有机化学/' + path.relative_to(source).as_posix()
                if len(filename) > 255:
                    raise ValueError(f'Material path too long: {filename}')
                if db.scalar(select(Material.id).where(Material.filename == filename)):
                    raise ValueError(f'Material already exists: {filename}')
                print(json.dumps({'file': path.name, 'status': 'extracting'}, ensure_ascii=False), flush=True)
                content = path.read_bytes()
                if len(content) > settings().max_upload_mb * 1024 * 1024:
                    raise ValueError(f'Material exceeds configured file size limit: {path.name}')
                extracted = _extract_text(path.name, content)
                row = _store_material(db, user, filename, content, extracted)
                stored = storage / row.storage_key
                created_paths.append(stored)
                row.purpose = 'instruction' if path.name == 'AI4S项目-里程碑-测试大纲修改要求.docx' else 'project'
                if stored.stat().st_size != len(content):
                    raise ValueError(f'Original copy has incorrect size: {path.name}')
                records.append({'source': str(path), 'material_id': row.id, 'filename': filename,
                                'bytes': len(content), 'text_characters': len(extracted), 'purpose': row.purpose})
                print(json.dumps(records[-1], ensure_ascii=False), flush=True)
            manifest = {'imported_at': datetime.now(timezone.utc).isoformat(), 'source_directory': str(source),
                        'uploaded_by': args.username, 'records': records,
                        'storage': '数据库保存材料索引、用途和提取正文；原件保存在 storage 目录。',
                        'boundary': '仅导入材料，未创建成果申报或启动评测；Excel 公式保留为文本。'}
            receipt.parent.mkdir(parents=True, exist_ok=True)
            pending = receipt.with_suffix('.pending.json')
            pending.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
            db.commit()
            committed = True
            pending.replace(receipt)
    except Exception:
        if not committed:
            for path in created_paths:
                path.unlink(missing_ok=True)
            receipt.with_suffix('.pending.json').unlink(missing_ok=True)
        raise
    print(json.dumps({'imported_files': len(records), 'receipt': str(receipt)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
