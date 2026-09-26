"""Frozen-evidence handoff to the unified skill's seven-dimension evaluator."""
import copy
import importlib.util
import json
from types import SimpleNamespace
from .pipeline_stages import SKILLS
from .pipeline_store import WaitingForInput,atomic_json
from .unified_evaluation import combine_evaluations


def wrapper():
    spec=importlib.util.spec_from_file_location('pipeline_v19_wrapper',SKILLS/'unified-impact-evaluation/scripts/v19.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def build_v19_workspace(inputs,outputs):
    delivered=inputs.get('v19_workspace')
    scope=outputs['wu_intake']
    if delivered is None:raise WaitingForInput('请提供已审查显式路由的v19工作区交付，不能用关键词自动绑定成果')
    workspace=copy.deepcopy(delivered)
    if workspace.get('schema_version')!='indicator-workspace.v6':raise ValueError('v19工作区格式错误')
    if workspace.get('project_profile',{}).get('project_id')!=scope['project_id']:
        raise ValueError('v19项目与Pipeline项目ID不一致')
    mapping=inputs.get('v19_scope_mapping') or {}
    if mapping.get('frozen_child_id'):
        if not mapping.get('reviewed') or mapping.get('outcome_id')!=scope['outcome_id'] or mapping.get('canonical_name')!=scope['intake']['canonical_name']:
            raise WaitingForInput('子成果范围映射尚未确认')
        from .v19_child_scope import child_workspace
        return child_workspace(workspace,scope,outputs['search_replay']['replay'],outputs['attribution'],
            child_id=mapping['frozen_child_id'],routes=mapping.get('evidence_routes') or {},review_note=mapping.get('review_note',''))
    outcome_id=scope['outcome_id']
    cards=workspace.get('evaluation_framework',{}).get('outcome_cards',[])
    selected=[c for c in cards if c.get('outcome_id')==outcome_id]
    if len(selected)!=1:raise WaitingForInput('当前成果ID未在v19冻结清单中唯一定位，不自动按标题强绑')
    mapping=inputs.get('v19_scope_mapping') or {}
    if mapping.get('outcome_id')!=outcome_id or mapping.get('canonical_name')!=scope['intake']['canonical_name'] or not mapping.get('reviewed'):
        raise WaitingForInput('请确认吴老师具体成果与v19冻结成果的显式范围对应关系',{'outcome_id':outcome_id,'v19_title':selected[0].get('title'),'wu_name':scope['intake']['canonical_name']})
    # The original outcome ID/title remain unchanged. Only declared evaluation coverage narrows.
    workspace['evaluation_framework']['outcome_cards']=selected
    workspace['project_profile']['evaluation_scope']=f"本轮仅评价冻结成果 {outcome_id}：{selected[0].get('title','')}"
    adapter=workspace.get('evidence_adapter',{})
    packet=adapter.get('outcome_packets',{}).get(outcome_id)
    if not packet or not packet.get('dimensions'):raise WaitingForInput('v19缺少当前冻结成果的维度证据包')
    adapter['outcome_packets']={outcome_id:packet}
    allowed={outcome_id,*selected[0].get('child_outcome_ids',[])}
    adapter['professional_metric_bindings']=[b for b in adapter.get('professional_metric_bindings',[]) if set(b.get('outcome_ids',[])) & allowed]
    replay=outputs['search_replay']
    attribution=outputs['attribution']
    # This supplemental packet retains original statements and tool analysis as distinct fields.
    # It never embeds the Wu assessment or any Wu G/L grade.
    project_sources=[{'source_id':e['id'],'quote':e['text'],'locator':e['locator'],'outcome_ids':[outcome_id],'source_type':'项目材料声明'} for e in scope['attribution_preparation']['evidence']]
    search_mode=replay['replay'].get('mode','historical_replay')
    source_type='本轮公开检索与原文核验，通过评审时间审计' if search_mode=='live_search' else '历史Search交付，未在本轮重新核验'
    search_sources=[{'source_id':e['id'],'quote':e['text'],'locator':e['locator'],'url':e.get('url'),'outcome_ids':[outcome_id],'source_type':source_type} for e in replay['replay']['evidence']]
    for dim,unit in packet['dimensions'].items():
        if unit.get('outcome_id') not in (None,outcome_id):raise ValueError('维度证据包成果ID错误')
        unit['pipeline_evidence_handoff']={'project_id':scope['project_id'],'outcome_id':outcome_id,
            'project_sources':project_sources,'search_sources':search_sources,'search_mode':search_mode,
            'search_provenance':{k:replay['replay'][k] for k in ['mode','original_run_id','original_completed_at','source_label']},
            'use_boundary':'这是补充原始材料及历史检索交付，不是吴老师评价结论；按当前维度适用性使用，D6/D7仍遵守原限制。'}
        if dim in ('D1','D2','D5'):
            unit['pipeline_evidence_handoff']['attribution_analysis']={
                'engine':attribution['engine'],'result':attribution['contribution_result'],'unresolved':attribution['unresolved_items'],
                'boundary':'确定性工具辅助分析，不是原始证据或专家裁决。'}
    adapter.setdefault('governance',{})['pipeline_handoff']='Wu conclusions excluded; project evidence, Search with explicit execution mode and DCA analysis retain distinct provenance.'
    return workspace


def v19_evaluation_stage(inputs,outputs,folder):
    import os
    from .config import settings
    if inputs.get('automatic_workspace'):
        from .pipeline_workspace import current_workspace
        workspace=current_workspace(inputs,outputs,folder)
    else:
        workspace=build_v19_workspace(inputs,outputs)
    path=folder/'workspace.json';atomic_json(path,workspace)
    engine=wrapper();preflight=engine.inspect_workspace(path);atomic_json(folder/'preflight.json',preflight)
    if not preflight['formal_input_ready']:raise WaitingForInput('v19输入契约未满足',preflight)
    cfg=settings()
    if cfg.v19_transport=='codex':
        from .v19_codex_transport import run_codex_v19
        result=run_codex_v19(workspace,folder/'artifacts',engine)
        return {'rubric_id':'outcome-d1-d7-evaluation.v19','project_id':outputs['wu_intake']['project_id'],
                'outcome_id':outputs['wu_intake']['outcome_id'],'result':result}
    if cfg.v19_transport!='provider':raise ValueError('V19_TRANSPORT仅支持codex或provider')
    allowed={'PATH','PATHEXT','SYSTEMROOT','WINDIR','USERPROFILE','APPDATA','LOCALAPPDATA','TEMP','TMP','HOME','COMSPEC','HTTP_PROXY','HTTPS_PROXY','NO_PROXY','SSL_CERT_FILE'}
    provider={k:v for k,v in os.environ.items() if k.upper() in allowed}
    provider.update({'V19_API_KEY':os.environ.get('V19_API_KEY') or cfg.v19_api_key.get_secret_value(),
        'V19_BASE_URL':os.environ.get('V19_BASE_URL') or cfg.v19_base_url,'V19_MODEL':os.environ.get('V19_MODEL') or cfg.v19_model,
        'PYTHONIOENCODING':'utf-8','PYTHON_DOTENV_DISABLED':'1'})
    missing=[k for k in ['V19_API_KEY','V19_BASE_URL','V19_MODEL'] if not provider.get(k)]
    if missing:raise WaitingForInput('v19模型服务未配置',{'missing_settings':missing})
    code=engine.run(SimpleNamespace(workspace=path,output_dir=folder/'artifacts',request_timeout=240,parallelism=2,total_timeout=1800,provider_environment=provider))
    if code:raise ValueError(f'v19阶段执行或校验失败（{code}），底稿已保留')
    result=json.loads((folder/'artifacts/evaluation-run.json').read_text(encoding='utf-8'))
    return {'rubric_id':'outcome-d1-d7-evaluation.v19','project_id':outputs['wu_intake']['project_id'],
            'outcome_id':outputs['wu_intake']['outcome_id'],'result':result}


def export_stage(inputs,outputs,folder):
    wu=outputs['wu_evaluation'];v19=outputs['v19_evaluation']
    atomic_json(folder/'wu-evaluation.json',wu)
    atomic_json(folder/'v19-evaluation.json',v19)
    combined=combine_evaluations(wu,v19)
    atomic_json(folder/'unified-evaluation.json',combined)
    manifest={'schema_version':'impact-pipeline-result.v1','project_id':wu['project_id'],'outcome_id':wu['outcome_id'],
              'wu':{'file':'wu-evaluation.json','rubric_id':wu['rubric_id']},
              'v19':{'file':'v19-evaluation.json','rubric_id':v19['rubric_id']},
              'search_mode':outputs.get('search_replay',{}).get('replay',{}).get('mode','historical_replay'),'published':False,'note':'两套L级口径独立，禁止按编号直接合并。'}
    atomic_json(folder/'manifest.json',manifest)
    return manifest
