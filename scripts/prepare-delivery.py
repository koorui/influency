"""Prepare a historical ZIP for container import without executing its SQL."""
import argparse
from io import BytesIO
import json
from pathlib import Path, PurePosixPath
import tarfile
import zipfile
from read_delivery_dump import parse_dump

parser = argparse.ArgumentParser()
parser.add_argument('archive', type=Path)
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
destination = root / '.deploy-state/delivery.tar'
destination.parent.mkdir(parents=True, exist_ok=True)
pending = destination.with_suffix('.tar.partial')
with zipfile.ZipFile(args.archive) as original:
    tables = parse_dump(original.read('database-export.sql'))
    encoded = json.dumps(tables, ensure_ascii=False).encode('utf-8')
    names = set()
    with tarfile.open(pending, 'w') as output:
        info = tarfile.TarInfo('tables.json')
        info.size = len(encoded)
        info.mode = 0o600
        output.addfile(info, BytesIO(encoded))
        for entry in original.infolist():
            if entry.is_dir() or not entry.filename.startswith('backend/storage/'):
                continue
            name = entry.filename.removeprefix('backend/')
            path = PurePosixPath(name)
            if path.is_absolute() or '..' in path.parts or '\\' in name or name in names:
                raise ValueError('Invalid or repeated artifact path')
            names.add(name)
            info = tarfile.TarInfo(name)
            info.size = entry.file_size
            info.mode = 0o644
            with original.open(entry) as stream:
                output.addfile(info, stream)
pending.replace(destination)
print(json.dumps({'tables': {k: len(v) for k, v in tables.items()},
                  'artifact_files': len(names), 'output': str(destination)}, ensure_ascii=False))
