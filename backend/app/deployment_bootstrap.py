"""One-time transactional import of accounts and materials into an empty deployment."""
from datetime import datetime
import json
from pathlib import Path
import shutil
from sqlalchemy import DateTime, select, func
from .config import settings
from .db import Base, engine
from . import models


def main():
    storage = Path(settings().storage_dir).resolve()
    marker = storage / 'initial-import-completed.json'
    if marker.exists():
        print('Initial data already imported; preserving the database.')
        return
    source = Path('/migration')
    payload = json.loads((source / 'migration.json').read_text(encoding='utf-8'))
    if payload.get('format') != 'zhiheng-initial-import-v1':
        raise ValueError('Unsupported import format')
    tables = payload['tables']
    if not set(tables).issubset(Base.metadata.tables):
        raise ValueError('Import schema differs from application tables')
    for name in Base.metadata.tables: tables.setdefault(name, [])
    storage.mkdir(parents=True, exist_ok=True)
    for record in tables['materials']:
        key = record['storage_key']
        if Path(key).name != key or '/' in key or '\\' in key:
            raise ValueError('Invalid material storage path')
        original = source / 'originals' / key
        if not original.is_file() or original.stat().st_size != record['size']:
            raise ValueError('Original material is missing or has incorrect size')
        destination = storage / key
        if destination.exists():
            if destination.stat().st_size != record['size']:
                raise ValueError('Existing original conflicts with migration data')
        else:
            shutil.copyfile(original, destination)
    with engine.begin() as connection:
        occupied = any(connection.scalar(select(func.count()).select_from(t)) for t in Base.metadata.sorted_tables)
        if occupied:
            # Recover only from a completed DB commit followed by an interrupted marker write.
            for table in Base.metadata.sorted_tables:
                expected = {r['id'] for r in tables[table.name]}
                actual = set(connection.scalars(select(table.c.id)))
                if actual != expected:
                    raise ValueError('Database is not empty and does not match this initial import; no rows overwritten')
            print('Initial rows already committed; restoring completion marker.')
        else:
            for table in Base.metadata.sorted_tables:
                records = []
                for record in tables[table.name]:
                    converted = dict(record)
                    for column in table.columns:
                        if isinstance(column.type, DateTime) and converted.get(column.name):
                            converted[column.name] = datetime.fromisoformat(converted[column.name])
                    records.append(converted)
                if records:
                    connection.execute(table.insert(), records)
    marker.write_text(json.dumps({'accounts': len(tables['users']), 'materials': len(tables['materials'])}), encoding='utf-8')
    print(f"Imported {len(tables['users'])} accounts and {len(tables['materials'])} materials.")


if __name__ == '__main__':
    main()
    from .project_setup import initialize
    initialize()
