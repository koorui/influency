import os
import json
import subprocess
import sys
import time
import pytest

pytestmark=pytest.mark.skipif(os.name=='nt',reason='Recovery is enabled only in the Linux worker')


def test_child_keeps_lock_after_parent_releases_descriptor(tmp_path):
    from app.pipeline_liveness import acquire,release
    fd=acquire(tmp_path)
    child=subprocess.Popen([sys.executable,'-c','import sys; sys.stdin.read()'],stdin=subprocess.PIPE,pass_fds=(fd,))
    release(fd)
    try:
        with pytest.raises(FileExistsError):acquire(tmp_path)
    finally:
        child.communicate(timeout=5)
    fd=acquire(tmp_path);release(fd)


def test_recovery_preserves_successful_stages_and_waits_for_live_process(tmp_path,monkeypatch):
    from app.pipeline_liveness import acquire,release,recover_interrupted
    from app.pipeline_store import PipelineStore,atomic_json
    from app.db import Session
    from app.models import PipelineJob,User
    from sqlalchemy import select
    store=PipelineStore(tmp_path/'job');state=store.create({})
    state['status']='running';state['stages']['wu_intake'].update(status='succeeded',output='intake.json',attempts=1)
    state['stages']['search_replay'].update(status='running',attempts=1)
    atomic_json(store.path,state);(store.root/'execution.lock').write_text('oldpid')
    atomic_json(store.root/'heartbeat.json',{'policy':'inherited-worker-lock-v1','recovery_supported':True,'updated_at':time.time()-120})
    with Session() as db:
        user=db.scalar(select(User))
        job=PipelineJob(title='Recovery',project_id='P',outcome_id='O',created_by=user.id,status='running');db.add(job);db.commit();identifier=job.id
    monkeypatch.setattr('app.pipeline_api.directory',lambda _:store.root)
    fd=acquire(store.root)
    try:assert recover_interrupted()==0
    finally:release(fd)
    assert recover_interrupted()==1
    recovered=store.read()
    assert recovered['stages']['wu_intake']['status']=='succeeded'
    assert recovered['stages']['search_replay']['status']=='failed'
    assert not (store.root/'execution.lock').exists()
    with Session() as db:assert db.get(PipelineJob,identifier).status=='queued'
