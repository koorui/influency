"""Package explicit source/static files for a reproducible mounted release."""
import argparse
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument('output',type=Path)
args=parser.parse_args()
repo=Path(__file__).resolve().parents[1]
out=args.output.resolve()
out.mkdir(parents=True,exist_ok=False)
for name in ('backend','skills'):
    shutil.copytree(repo/name,out/name,ignore=shutil.ignore_patterns('__pycache__','*.pyc','.pytest_cache','storage','.env*','tests'))
shutil.copytree(repo/'.local-runtime/teacher-v4/web',out/'web')
shutil.copy2(repo/'frontend/nginx.conf',out/'nginx.conf')
(out/'release.json').write_text(json.dumps({'created_at':datetime.now(timezone.utc).isoformat(),'runtime_version':'grading-20260927-coordinated-v5',
    'result_protocol':'outcome-evaluation.v3','database_revision':'0015',
    'source_roots':['backend','skills'],'static_root':'web','deployment':'read-only source and static mounts on existing dependency images'},indent=2),encoding='utf-8')
services={}
for name in ('api','pipeline-worker','migrate','bootstrap'):
    services[name]={'volumes':[{'type':'bind','source':(out/'backend').as_posix(),'target':'/app/backend','read_only':True},
        {'type':'bind','source':(out/'skills').as_posix(),'target':'/app/skills','read_only':True}]}
services['web']={'volumes':[{'type':'bind','source':(out/'web').as_posix(),'target':'/usr/share/nginx/html','read_only':True},
    {'type':'bind','source':(out/'nginx.conf').as_posix(),'target':'/etc/nginx/conf.d/default.conf','read_only':True}]}
(out/'compose.release.json').write_text(json.dumps({'services':services},indent=2),encoding='utf-8')
print(out)
