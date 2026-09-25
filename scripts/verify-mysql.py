"""Run the workflow suite against an isolated MySQL database in this project's container."""
import os
import subprocess
import sys
from pathlib import Path
from dotenv import dotenv_values

root = Path(__file__).resolve().parents[1]
sql = "CREATE DATABASE IF NOT EXISTS impact_test CHARACTER SET utf8mb4; GRANT ALL PRIVILEGES ON impact_test.* TO 'impact'@'%';"
subprocess.run(['docker', 'compose', 'exec', '-T', 'mysql', 'sh', '-c', 'MYSQL_PWD="$MYSQL_ROOT_PASSWORD" exec mysql -uroot'], input=sql.encode(), cwd=root, check=True)
env = os.environ.copy()
env['IMPACT_TEST_DATABASE_URL'] = str(dotenv_values(root / '.env')['DATABASE_URL']).replace('/impact?', '/impact_test?')
env['DATABASE_URL'] = env['IMPACT_TEST_DATABASE_URL']
subprocess.run([sys.executable, '-m', 'alembic', 'upgrade', 'head'], cwd=root / 'backend', env=env, check=True)
subprocess.run([sys.executable, '-m', 'pytest', '-q'], cwd=root / 'backend', env=env, check=True)
