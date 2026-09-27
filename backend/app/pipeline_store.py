"""Durable stage journal: artifacts and Wu/v19 results never share output slots.
Executors are supplied by the pipeline service, not by browser requests.
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

STAGES=('wu_intake','search_replay','attribution','wu_evaluation','v19_evaluation','export')


def timestamp():return datetime.now(timezone.utc).isoformat()


def atomic_json(path,value):
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    for attempt in range(5):
        try:
            os.replace(temp,path)
            return
        except PermissionError:
            if os.name!='nt' or attempt==4:raise
            import time
            time.sleep(0.05*(attempt+1))


class WaitingForInput(Exception):
    def __init__(self,message,details=None):
        super().__init__(message);self.details=details or {}


class PipelineStore:
    def __init__(self,root):
        self.root=Path(root).resolve()
        self.path=self.root/'pipeline.json'

    def create(self,inputs):
        from .evaluation_runtime import CURRENT
        inputs={**inputs,'runtime_version':CURRENT}
        self.root.mkdir(parents=True,exist_ok=False)
        state={'schema_version':'impact-pipeline.v1','created_at':timestamp(),'status':'pending',
               'inputs':inputs,'stages':{s:{'status':'pending','attempts':0} for s in STAGES}}
        atomic_json(self.path,state)
        return state

    def read(self):return json.loads(self.path.read_text(encoding='utf-8'))

    def amend(self,patch,restart_stage):
        """Record an operator correction and invalidate dependent stages explicitly."""
        if restart_stage not in STAGES:raise ValueError('Unknown restart stage')
        lock=self.root/'execution.lock'
        fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
        os.write(fd,str(os.getpid()).encode());os.close(fd)
        try:
            state=self.read()
            if state['status']=='running':raise ValueError('Cannot amend a running pipeline')
            state['inputs']={**state['inputs'],**patch}
            revision=len(state.get('amendments',[]))+1
            atomic_json(self.root/f'input-revision-{revision}.json',state['inputs'])
            state.setdefault('amendments',[]).append({'revision':revision,'at':timestamp(),'restart_stage':restart_stage})
            for name in STAGES[STAGES.index(restart_stage):]:
                previous=state['stages'][name]
                state.setdefault('stage_history',[]).append({'stage':name,**previous})
                state['stages'][name]={'status':'pending','attempts':previous['attempts']}
            state['status']='pending';atomic_json(self.path,state)
            return state
        finally:lock.unlink(missing_ok=True)

    def execute(self,executors):
        # Atomic lock prevents two workers from running the same pipeline.
        lock=self.root/'execution.lock'
        fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
        os.write(fd,str(os.getpid()).encode());os.close(fd)
        try:
            state=self.read()
            state['status']='running';atomic_json(self.path,state)
            outputs={}
            for name in STAGES:
                stage=state['stages'][name]
                if stage['status']=='succeeded':
                    output_path=(self.root/stage['output']).resolve()
                    if not output_path.is_relative_to(self.root):raise ValueError('Stage output escapes pipeline directory')
                    value=json.loads(output_path.read_text(encoding='utf-8'))
                    outputs[name]=value;continue
                if name not in executors:raise ValueError(f'Missing stage executor: {name}')
                if stage['status'] in ('failed','waiting','running'):
                    state.setdefault('stage_history',[]).append({'stage':name,**stage})
                stage['attempts']+=1
                folder=self.root/name/f"attempt-{stage['attempts']}"
                folder.mkdir(parents=True,exist_ok=False)
                stage.update(status='running',started_at=timestamp(),error='')
                atomic_json(self.path,state)
                try:
                    value=executors[name](state['inputs'],outputs,folder)
                    atomic_json(folder/'output.json',value)
                    stage.update(status='succeeded',output=(folder/'output.json').relative_to(self.root).as_posix(),finished_at=timestamp())
                    outputs[name]=value
                except WaitingForInput as exc:
                    atomic_json(folder/'waiting.json',{'message':str(exc),'details':exc.details})
                    stage.update(status='waiting',error=str(exc),finished_at=timestamp())
                    state['status']='waiting';atomic_json(self.path,state);return state
                except Exception as exc:
                    stage.update(status='failed',error=str(exc),finished_at=timestamp())
                    state['status']='failed';atomic_json(self.path,state);raise
                atomic_json(self.path,state)
            state['status']='succeeded';atomic_json(self.path,state);return state
        except Exception:
            state=self.read()
            if state['status']=='running':state['status']='failed';atomic_json(self.path,state)
            raise
        finally:lock.unlink(missing_ok=True)
