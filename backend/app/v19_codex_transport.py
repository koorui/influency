"""Keep original v19 evaluation orchestration; replace only model transport with Codex CLI.
Credentials remain in the local Codex store. Each call retains its own schema, prompt and logs.
"""
import json
import threading
from pathlib import Path
from types import SimpleNamespace
from pydantic import Field
from .schema import StrictModel
from .pipeline_model import execute_json_stage
from .pipeline_store import atomic_json
from .codex_adapter import configured_model
from .skill_loader import SKILL_ROOT
from .v19_response_contract import DimensionReply,OutcomeReply,ProjectReply


class ModelReply(StrictModel):
    result_json: str = Field(description='The complete JSON object requested by the supplied v19 system prompt, serialized as a JSON string.')


def source_references(value):
    found=set()
    if isinstance(value,dict):
        for key,item in value.items():
            if key=='source_id' and isinstance(item,str) and item:found.add(item)
            elif key in ('source_ids','decisive_source_ids') and isinstance(item,list):found.update(x for x in item if isinstance(x,str) and x)
            found.update(source_references(item))
    elif isinstance(value,list):
        for item in value:found.update(source_references(item))
    return found


def validate_source_references(data,payload):
    unknown=source_references(data)-source_references(payload['v19_input'])
    if unknown:raise ValueError('v19输出引用未提供的来源：'+','.join(sorted(unknown)))


class CodexV19Client:
    available=True

    def __init__(self,root,timeout=480,cache_roots=()):
        self.root=root
        self.root.mkdir(parents=True,exist_ok=True)
        self.settings=SimpleNamespace(glm_model=configured_model())
        self.timeout=timeout
        self._lock=threading.Lock()
        self._number=0
        self.cache_roots=[Path(p).resolve() for p in cache_roots]

    def chat_json(self,system,user,**kwargs):
        with self._lock:
            self._number+=1
            folder=self.root/f'call-{self._number:03d}'
            folder.mkdir(exist_ok=False)
        model=kwargs.get('model') or self.settings.glm_model
        payload={'v19_system_prompt':system,'v19_input':json.loads(user)}
        atomic_json(folder/'request-manifest.json',{'model':model,'transport':'codex-cli'})
        try:
            request=payload['v19_input']
            reply_model=DimensionReply if isinstance(request.get('dimension'),dict) else ProjectReply if isinstance(request.get('outcomes'),list) else OutcomeReply if isinstance(request.get('dimensions'),list) and request.get('outcome_id') else ModelReply
            direct=reply_model is not ModelReply
            reply=execute_json_stage(folder,reply_model,payload,
                'You are the model transport for ONE call of the v19 engine, which the host is already executing. '
                'Do not launch the v19 scripts or create another pipeline. Apply v19_system_prompt to v19_input. '+
                ('Return the requested v19 JSON object directly, not a serialized JSON string. Follow the supplied output schema for this call type. ' if direct else 'Return result_json containing the requested complete object. Preserve impact_level/scope_impact_level as applicable. ')+
                'The code-defined v19 rules are authoritative for this call; do not import Wu-v2 levels. '
                'No new Search, no invented source IDs. Missing facts remain pending. '
                'Every key_facts/evidence_chain entry must contain a nonempty fact, source_ids and outcome_ids. '
                'An absence of materials belongs in missing_inputs, not in a fact with empty references. Empty fact arrays are allowed. '
                'Do not omit any of the three branches when judging a D dimension.',
                skill_root=SKILL_ROOT.parent/'dual-layer-impact-v19',timeout=self.timeout,inline_input=True)
            data=reply.model_dump(mode='json') if direct else json.loads(reply.result_json)
            if not isinstance(data,dict):raise ValueError('v19 model output must be an object')
            validate_source_references(data,payload)
            atomic_json(folder/'parsed-result.json',data)
            return SimpleNamespace(ok=True,data=data,text=json.dumps(data,ensure_ascii=False),raw='',model=model,error='',error_type='')
        except Exception as exc:
            # The original pipeline owns bounded retries and incomplete-result handling.
            return SimpleNamespace(ok=False,data=None,text='',raw='',model=model,error=str(exc),error_type=type(exc).__name__)


def run_codex_v19(workspace,folder,engine,*,cache_roots=()):
    # wrapper() has installed the vendored package path, without changing its source.
    from metric_judgment.indicator_product import IndicatorEvaluationPipeline,build_indicator_product
    from .config import settings
    folder.mkdir(parents=True,exist_ok=False)
    client=CodexV19Client(folder/'calls',settings().codex_timeout_seconds,cache_roots=cache_roots)
    run=IndicatorEvaluationPipeline(client.settings,client).run(workspace,model=client.settings.glm_model,parallelism=1)
    from metric_judgment.grading_standard import VERSION
    run['grading_standard']=VERSION
    atomic_json(folder/'evaluation-run.json',run)
    checked=engine.validate_result(run)
    atomic_json(folder/'validation.json',checked)
    atomic_json(folder/'product.json',build_indicator_product(workspace,run))
    atomic_json(folder/'run-manifest.json',{'transport':'codex-cli','model':client.settings.glm_model,
        'reasoning_effort':settings().codex_reasoning_effort,'standard_version':run.get('run',{}).get('standard_version'),
        'valid':checked['valid'],
        'cached_responses':sum(json.loads(p.read_text(encoding='utf-8')).get('execution_mode')=='verified_cached_response' for p in (folder/'calls').glob('call-*/execution.json')),
        'cache_roots':[str(p) for p in cache_roots]})
    if not checked['valid']:raise ValueError('v19输出未通过完整性检查；原始响应已保留')
    return run
