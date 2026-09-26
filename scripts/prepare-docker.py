"""Prepare private deployment files from an explicitly selected CLI home and local DB."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import secrets
import shutil
import sys
import tomllib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from sqlalchemy import DateTime, create_engine, select
from app.db import Base
from app import models


def toml_value(value):
    if isinstance(value, bool):
        return 'true' if value else 'false'
    if isinstance(value, (str, int, float, list)):
        return json.dumps(value, ensure_ascii=False)
    raise ValueError('Unsupported provider configuration value')


def write_table(lines, path, values):
    lines.append('[' + '.'.join(json.dumps(p) for p in path) + ']')
    for key, value in values.items():
        if not isinstance(value, dict):
            lines.append(f'{json.dumps(key)} = {toml_value(value)}')
    for key, value in values.items():
        if isinstance(value, dict):
            write_table(lines, [*path, key], value)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--codex-home', required=True, type=Path)
    parser.add_argument('--source-db', required=True, type=Path)
    parser.add_argument('--source-storage', required=True, type=Path)
    args = parser.parse_args()
    cli_home = args.codex_home.resolve(strict=True)
    if cli_home.name.casefold() in ('.codex-4', 'codex-4'):
        raise ValueError('The codex-4 workspace must not be used for this deployment')
    source_db = args.source_db.resolve(strict=True)
    source_storage = args.source_storage.resolve(strict=True)
    private = ROOT / '.deploy-secrets'
    state = ROOT / '.deploy-state'
    environment = ROOT / '.env.docker'
    if environment.exists() or private.exists() or state.exists():
        raise ValueError('Deployment files already exist; preserve existing credentials and review before preparing again')
    cfg = tomllib.loads((cli_home / 'config.toml').read_text(encoding='utf-8-sig'))
    auth = json.loads((cli_home / 'auth.json').read_text(encoding='utf-8-sig'))
    if not auth.get('OPENAI_API_KEY'):
        raise ValueError('The selected relay must have API-key authentication')
    provider = cfg.get('model_provider')
    if not provider or provider not in cfg.get('model_providers', {}):
        raise ValueError('An explicit relay provider configuration is required')
    lines = [f'{key} = {toml_value(cfg[key])}' for key in
             ('model', 'model_provider', 'model_reasoning_effort') if key in cfg]
    lines += ['cli_auth_credentials_store = "file"']
    write_table(lines, ['model_providers', provider], cfg['model_providers'][provider])
    cli_config = '\n'.join(lines) + '\n'
    tomllib.loads(cli_config)

    engine = create_engine('sqlite:///' + source_db.as_posix())
    tables = {}
    with engine.connect() as connection:
        for table in Base.metadata.sorted_tables:
            records = []
            for mapping in connection.execute(select(table)).mappings():
                records.append({key: value.isoformat() if isinstance(value, datetime) else value
                                for key, value in mapping.items()})
            tables[table.name] = records
    engine.dispose()
    if any(row['status'] in ('queued', 'running') for name in ('evaluation_tasks', 'pipeline_jobs') for row in tables[name]):
        raise ValueError('Finish or cancel pending evaluation tasks before migration')
    # The repository demo is not a real project result and is not deployed.
    demo_ids = {r['id'] for r in tables['evaluation_results'] if r['payload'].get('is_demo')}
    tables['evaluation_results'] = [r for r in tables['evaluation_results'] if r['id'] not in demo_ids]
    for name in ('result_versions', 'query_records'):
        tables[name] = [r for r in tables[name] if r['result_id'] not in demo_ids]
    for ticket in tables['tickets']:
        if ticket.get('result_id') in demo_ids:
            ticket['result_id'] = None
            ticket['status'] = 'pending'
    if tables['evaluation_tasks'] or tables['pipeline_jobs'] or tables['evaluation_results']:
        raise ValueError('This first-deployment importer only migrates accounts/materials; use the full backup workflow for evaluation archives')
    for record in tables['materials']:
        key = record['storage_key']
        if Path(key).name != key or not (source_storage / key).is_file():
            raise ValueError('Missing or invalid original material path')
        if (source_storage / key).stat().st_size != record['size']:
            raise ValueError('Original material size does not match its database record')

    private.mkdir(mode=0o700)
    (state / 'originals').mkdir(parents=True)
    (private / 'relay-config.toml').write_text(cli_config, encoding='utf-8')
    (private / 'relay-auth.json').write_text(json.dumps({'OPENAI_API_KEY': auth['OPENAI_API_KEY']}), encoding='utf-8')
    for record in tables['materials']:
        shutil.copyfile(source_storage / record['storage_key'], state / 'originals' / record['storage_key'])
    (state / 'migration.json').write_text(json.dumps({'format': 'zhiheng-initial-import-v1', 'tables': tables}, ensure_ascii=False, indent=2), encoding='utf-8')
    environment.write_text('\n'.join([
        'MYSQL_ROOT_PASSWORD=' + secrets.token_hex(24),
        'MYSQL_PASSWORD=' + secrets.token_hex(24),
        'SECRET_KEY=' + secrets.token_hex(32),
        'CODEX_VERSION=0.156.1',
        'CODEX_MODEL=' + cfg.get('model', 'gpt-6-astra'),
        'CODEX_REASONING_EFFORT=' + cfg.get('model_reasoning_effort', 'high'),
        'DEPLOY_ORIGIN=http://localhost:18080', 'BIND_ADDRESS=127.0.0.1',
        'WEB_PORT=18080', 'COOKIE_SECURE=false', ''
    ]), encoding='utf-8')
    for path in [environment, *private.iterdir(), state / 'migration.json']:
        path.chmod(0o600)
    print(json.dumps({'prepared': True, 'accounts': len(tables['users']), 'materials': len(tables['materials']),
                      'demo_results_excluded': len(demo_ids), 'cli_home': str(cli_home)}, ensure_ascii=False))


if __name__ == '__main__':
    main()
