"""Docker/Linux liveness: a live evaluator child retains the OS worker lock."""
import json
import os
import threading
import time
from contextlib import contextmanager
from .pipeline_store import atomic_json

active_guard_fd=None


def acquire(root):
    if os.name=='nt':return None
    import fcntl
    fd=os.open(root/'worker.guard',os.O_CREAT|os.O_RDWR,0o600)
    try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd);raise FileExistsError('工作进程或其模型子进程仍在执行')
    return fd


def release(fd):
    # Do not LOCK_UN: an inherited child descriptor must keep the lock alive.
    if fd is not None:os.close(fd)


@contextmanager
def worker_guard(root):
    global active_guard_fd
    fd=acquire(root);stop=threading.Event()
    active_guard_fd=fd
    def beat():
        atomic_json(root/'heartbeat.json',{'worker_pid':os.getpid(),'updated_at':time.time(),
            'recovery_supported':fd is not None,'policy':'inherited-worker-lock-v1'})
    def heartbeat():
        while not stop.wait(15):beat()
    try:beat()
    except Exception:
        active_guard_fd=None;release(fd);raise
    thread=threading.Thread(target=heartbeat,daemon=True)
    thread.start()
    try:yield
    finally:
        stop.set();thread.join(timeout=2);active_guard_fd=None;release(fd)


def recover_interrupted():
    if os.name=='nt':return 0
    from sqlalchemy import select
    from .db import Session
    from .models import PipelineJob
    from .pipeline_api import directory
    from .pipeline_store import PipelineStore,timestamp
    from .evaluation_runtime import CURRENT
    from .config import settings
    if settings().v19_transport!='codex':return 0
    recovered=0
    with Session() as db:
        jobs=list(db.scalars(select(PipelineJob).where(PipelineJob.status=='running')))
        for job in jobs:
            root=directory(job.id);fd=None
            try:
                heart=json.loads((root/'heartbeat.json').read_text(encoding='utf-8'))
                if heart.get('policy')!='inherited-worker-lock-v1' or not heart.get('recovery_supported') or time.time()-heart['updated_at']<60:continue
                fd=acquire(root)
                # A concurrent normal completion may have committed before the lock opened.
                db.refresh(job,with_for_update=True)
                if job.status!='running':continue
                store=PipelineStore(root);state=store.read()
                if state['inputs'].get('runtime_version')!=CURRENT:continue
                for name,stage in state['stages'].items():
                    if stage['status']!='succeeded':
                        attempts=[int(p.name.removeprefix('attempt-')) for p in (root/name).glob('attempt-*') if p.is_dir() and p.name.removeprefix('attempt-').isdigit()]
                        stage['attempts']=max([stage['attempts'],*attempts])
                    if stage['status']=='running':
                        stage.update(status='failed',error='执行进程中断；已保留本次底稿，等待从此阶段续跑',finished_at=timestamp())
                state['status']='pending'
                state.setdefault('recoveries',[]).append({'at':timestamp(),'reason':'OS lock released by worker and evaluator children'})
                atomic_json(store.path,state)
                (root/'execution.lock').unlink(missing_ok=True)
                job.status='queued';job.error='进程中断后自动恢复，已完成阶段继续复用';job.revision+=1
                db.commit();recovered+=1
            except (FileNotFoundError,FileExistsError,ValueError,KeyError):continue
            finally:release(fd)
    return recovered
