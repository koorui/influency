"""Durable stage journal: artifacts and Wu/v19 results never share output slots.
Executors are supplied by the pipeline service, not by browser requests.
"""
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

STAGES=('wu_intake','search_replay','attribution','wu_evaluation','v19_evaluation','export')


def fingerprint(value):
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()


def timestamp():return datetime.now(timezone.utc).isoformat()


def implementation_fingerprint():
    root=Path(__file__).resolve().parents[2]
    files=list(Path(__file__).parent.glob('pipeline_*.py'))
    files.append(Path(__file__).parent/'v19_codex_transport.py')
    files.append(Path(__file__).parent/'v19_response_contract.py')
    files.append(Path(__file__).parent/'v19_child_scope.py')
    for name in ('outcome-impact-evaluation','data-purification-ai-attribution','dual-layer-impact-v19','project-search-verification'):
        files.extend(p for p in (root/'skills'/name).rglob('*') if p.is_file() and p.suffix in ('.py','.json','.md','.yaml') and '__pycache__' not in p.parts)
    digest=hashlib.sha256()
    for path in sorted(files):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def atomic_json(path,value):
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    os.replace(temp,path)


class WaitingForInput(Exception):
    def __init__(self,message,details=None):
        super().__init__(message);self.details=details or {}


class PipelineStore:
    def __init__(self,root):
        self.root=Path(root).resolve()
        self.path=self.root/'pipeline.json'

    def create(self,inputs):
        self.root.mkdir(parents=True,exist_ok=False)
        state={'schema_version':'impact-pipeline.v1','created_at':timestamp(),'status':'pending',
               'implementation_hash':implementation_fingerprint(),
               'input_hash':fingerprint(inputs),'inputs':inputs,'stages':{s:{'status':'pending','attempts':0} for s in STAGES}}
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
            if fingerprint(state['inputs'])!=state['input_hash']:raise ValueError('Pipeline inputs changed outside amendment protocol')
            before=state['input_hash']
            old_implementation=state.get('implementation_hash')
            if old_implementation and old_implementation!=implementation_fingerprint():
                raise ValueError('工作流代码或Skill已更新，请新建任务，不能混用规则续跑')
            state['inputs']={**state['inputs'],**patch}
            state['input_hash']=fingerprint(state['inputs'])
            revision=len(state.get('amendments',[]))+1
            atomic_json(self.root/f'input-revision-{revision}.json',state['inputs'])
            state.setdefault('amendments',[]).append({'revision':revision,'at':timestamp(),'previous_hash':before,'new_hash':state['input_hash'],'restart_stage':restart_stage})
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
            if state.get('implementation_hash') and state['implementation_hash']!=implementation_fingerprint():
                raise ValueError('工作流代码或Skill已更新，请新建任务，不能混用两版规则续跑')
            if fingerprint(state['inputs'])!=state['input_hash']:raise ValueError('Pipeline inputs changed outside amendment protocol')
            state['status']='running';atomic_json(self.path,state)
            outputs={}
            for name in STAGES:
                stage=state['stages'][name]
                if stage['status']=='succeeded':
                    output_path=(self.root/stage['output']).resolve()
                    if not output_path.is_relative_to(self.root):raise ValueError('Stage output escapes pipeline directory')
                    value=json.loads(output_path.read_text(encoding='utf-8'))
                    if fingerprint(value)!=stage['output_hash']:raise ValueError(f'{name}: saved artifact changed')
                    outputs[name]=value;continue
                if name not in executors:raise ValueError(f'Missing stage executor: {name}')
                stage['attempts']+=1
                folder=self.root/name/f"attempt-{stage['attempts']}"
                folder.mkdir(parents=True,exist_ok=False)
                stage.update(status='running',started_at=timestamp(),error='')
                atomic_json(self.path,state)
                try:
                    value=executors[name](state['inputs'],outputs,folder)
                    atomic_json(folder/'output.json',value)
                    stage.update(status='succeeded',output=(folder/'output.json').relative_to(self.root).as_posix(),output_hash=fingerprint(value),finished_at=timestamp())
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
