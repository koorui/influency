"""One-time clean trial, requiring a full backup mounted read-only at /backup."""
import argparse
import json
import sys
from pathlib import Path
from sqlalchemy import select, delete, func
from .auth import hash_password
from .config import settings
from .db import Session
from .models import (User, Material, PipelineJob, Task, Result, ResultVersion, QueryRecord,
                     OutcomeSubmission, Ticket, Audit, ProjectMember, AccessAttempt)
from .project_deletion import commit_with_files, ensure_idle


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--apply',action='store_true')
    args=parser.parse_args()
    if not args.apply:raise SystemExit('Explicit --apply is required')
    backup=Path('/backup')
    receipt=json.loads((backup/'backup.json').read_text(encoding='utf-8'))
    for name,field in [('database.sql','database_bytes'),('materials.tar.gz','materials_bytes')]:
        if (backup/name).stat().st_size!=receipt[field] or receipt[field]<=0:raise ValueError('Incomplete backup')
    credentials=json.load(sys.stdin)
    root=Path(settings().storage_dir).resolve()
    marker=root/'fresh-trial-reset.json'
    if marker.exists():raise ValueError('Trial reset already completed; no changes made')
    with Session() as db:
        if db.scalar(select(User.id).where(User.username==credentials['username'])):raise ValueError('Username already exists')
        jobs=list(db.scalars(select(PipelineJob)));tasks=list(db.scalars(select(Task)))
        ensure_idle(jobs,tasks)
        if any(j.status=='queued' for j in jobs):raise ValueError('Queued workflow exists; reset refused')
        materials=list(db.scalars(select(Material)))
        kept=[m for m in materials if m.filename.startswith('有机化学/')]
        if len(kept)!=6:raise ValueError('Expected six original chemistry materials; review before clearing')
        keep_files={m.storage_key for m in kept}
        if any(Path(key).name!=key or not (root/key).is_file() for key in keep_files):raise ValueError('Original material missing')
        keep_files.update({'initial-import-completed.json','delivery-import-20260925.json',
                           'legacy-cleanup-completed.json','project-access-codes.json'})
        if (root/'.deletion-trash').exists() and any((root/'.deletion-trash').iterdir()):raise ValueError('Unresolved file deletion journal')
        paths=[p.name for p in root.iterdir() if p.name not in keep_files and p.name!='.deletion-trash']
        tables=(QueryRecord,ResultVersion,Result,OutcomeSubmission,Task,PipelineJob,Ticket,Audit,ProjectMember,AccessAttempt)
        counts={model.__tablename__:db.scalar(select(func.count()).select_from(model)) for model in tables}
        for model in tables:db.execute(delete(model))
        db.execute(delete(Material).where(~Material.id.in_([m.id for m in kept])))
        db.add(User(username=credentials['username'],password_hash=hash_password(credentials['password']),role='user'))
        commit_with_files(db,paths)
    outcome={'removed_rows':counts,'kept_materials':len(kept),'removed_materials':len(materials)-len(kept),
             'removed_storage_entries':len(paths),'new_user':credentials['username'],'backup':receipt['backup']}
    marker.write_text(json.dumps(outcome,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(outcome,ensure_ascii=False))


if __name__=='__main__':main()
