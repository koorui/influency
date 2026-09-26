"""Back up the running deployment, stop evaluators and merge the prepared delivery."""
from datetime import datetime
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
docker = shutil.which('docker') or str(Path(os.environ['LOCALAPPDATA']) / 'Programs/DockerDesktop/resources/bin/docker.exe')
os.environ['PATH'] = str(Path(docker).parent) + os.pathsep + os.environ['PATH']
compose = [docker, 'compose', '--env-file', '.env.docker']
subprocess.run(compose + ['stop', 'pipeline-worker'], check=True)
backup = ROOT / '.local-runtime/backups' / ('before-delivery-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '.sql')
backup.parent.mkdir(parents=True, exist_ok=True)
with backup.open('wb') as output:
    subprocess.run(compose + ['exec', '-T', 'mysql', 'sh', '-c',
        'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysqldump -u root --single-transaction --no-tablespaces impact'], stdout=output, check=True)
print('Database backup saved: ' + str(backup), flush=True)
subprocess.run(compose + ['run', '--rm', '--no-deps', 'bootstrap', 'python', '-m', 'app.import_delivery'], check=True)
subprocess.run(compose + ['start', 'pipeline-worker'], check=True)
subprocess.run(compose + ['exec', '-T', 'pipeline-worker', 'python', '-m', 'app.deployment_check'], check=True)
