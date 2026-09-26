"""Merge a parsed historical delivery without replacing current accounts or executing SQL."""
from datetime import datetime
import json
from pathlib import Path
import shutil
import tarfile
from tempfile import TemporaryDirectory
from sqlalchemy import DateTime, JSON, select
from .config import settings
from .db import Base, engine
from .models import User


def import_from(source):
    storage = Path(settings().storage_dir).resolve()
    receipt = storage / 'delivery-import-20260925.json'
    if receipt.exists():
        print(receipt.read_text(encoding='utf-8'))
        return
    tables = json.loads((source / 'tables.json').read_text(encoding='utf-8'))
    counts = {}
    created_files = []
    try:
        with engine.begin() as connection:
            admin = connection.execute(select(User.id).where(User.username == 'admin', User.role == 'admin')).scalar_one()
            user_ids = {r['id']: admin for r in tables['users']}
            prepared = {}
            for table in Base.metadata.sorted_tables:
                if table.name == 'users': continue
                columns = {c.name: c for c in table.columns}
                records = []
                for original in tables.get(table.name, []):
                    row = {key: value for key, value in original.items() if key in columns}
                    for key, column in columns.items():
                        if row.get(key) is not None:
                            if isinstance(column.type, DateTime): row[key] = datetime.fromisoformat(row[key])
                            elif isinstance(column.type, JSON): row[key] = json.loads(row[key])
                    for key in ('uploaded_by', 'created_by', 'reviewed_by', 'editor', 'actor'):
                        if row.get(key) in user_ids: row[key] = user_ids[row[key]]
                    if row.get('owner', '').startswith('user:'):
                        owner = row['owner'][5:]
                        if owner in user_ids: row['owner'] = 'user:' + user_ids[owner]
                    if table.name == 'materials': row['filename'] = '历史交付/' + row['filename']
                    if table.name in ('evaluation_tasks', 'pipeline_jobs') and row['status'] in ('queued', 'running'):
                        row['status'] = 'failed'
                        row['error'] = '交付时尚未完成；本次只恢复历史数据，未自动执行。'
                    if table.name == 'tickets': row['active_key'] = None
                    if table.name == 'evaluation_results' and row['payload'].get('is_demo'):
                        row['status'] = 'draft'
                        row['published_at'] = None
                    if connection.execute(select(table.c.id).where(table.c.id == row['id'])).first():
                        raise ValueError('Incoming record conflicts with an existing ID; import aborted')
                    records.append(row)
                prepared[table.name] = records
            for row in prepared['materials']:
                key = row['storage_key']
                if Path(key).name != key or '/' in key or '\\' in key: raise ValueError('Invalid storage key')
                original = source / 'storage' / key
                if not original.is_file() or original.stat().st_size != row['size']:
                    raise ValueError('Original material missing or wrong size: ' + row['filename'])
            paths = [p for p in (source / 'storage').rglob('*') if p.is_file()]
            for path in paths:
                destination = storage / path.relative_to(source / 'storage')
                if destination.exists():
                    raise ValueError('Incoming artifact would overwrite an existing file: ' + str(destination))
            for path in paths:
                destination = storage / path.relative_to(source / 'storage')
                destination.parent.mkdir(parents=True, exist_ok=True)
                created_files.append(destination)
                shutil.copyfile(path, destination)
            for table in Base.metadata.sorted_tables:
                rows = prepared.get(table.name, [])
                if rows: connection.execute(table.insert(), rows)
                counts[table.name] = len(rows)
    except Exception:
        for path in reversed(created_files):
            path.unlink(missing_ok=True)
        raise
    report = {'imported': counts, 'artifact_files': len(paths), 'source_users_mapped_to': 'admin',
              'source_account_credentials_imported': False, 'model_request_sent': False,
              'demo_result_kept_as_draft': True}
    receipt.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


def main():
    if (Path(settings().storage_dir)/'legacy-cleanup-completed.json').exists():
        raise ValueError('Legacy delivery import is retired after project migration.')
    archive = Path('/migration/delivery.tar')
    if archive.is_file():
        with TemporaryDirectory(prefix='impact-delivery-') as temporary:
            with tarfile.open(archive, 'r:') as package:
                package.extractall(temporary, filter='data')
            import_from(Path(temporary))
    else:
        import_from(Path('/migration/delivery'))


if __name__ == '__main__':
    main()
