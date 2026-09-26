"""Route current ticket evidence into v19 without reusing previous evaluations."""
from pydantic import Field
from .schema import StrictModel
from .pipeline_model import execute_json_stage
from .pipeline_store import WaitingForInput, atomic_json
from .v19_child_scope import child_workspace


class EvidenceRoutes(StrictModel):
    D1:list[str]=Field(description='核心问题解决与技术先进性的原始证据ID')
    D2:list[str]=Field(description='原创性与项目期新增的证据ID')
    D3:list[str]=Field(description='学术影响力的证据ID')
    D4:list[str]=Field(description='开放复用与生态影响力的证据ID')
    D5:list[str]=Field(description='真实应用影响力的证据ID')
    D6:list[str]=Field(description='流程、平台或组织主线集成的证据ID')
    D7:list[str]=Field(description='外部专业认可与领域影响的证据ID')
    explanation:str


def current_workspace(inputs,outputs,folder):
    scope=outputs['wu_intake'];intake=scope['intake'];replay=outputs['search_replay']['replay']
    evidence=scope['attribution_preparation']['evidence']
    routing_folder=folder/'evidence-routing';routing_folder.mkdir()
    routing=execute_json_stage(routing_folder,EvidenceRoutes,
        {'canonical_name':intake['canonical_name'],'outcome_card':intake['outcome_card'],
         'project_evidence':evidence,'external_evidence':replay['evidence']},
        'Only route evidence for this frozen outcome to D1-D7. Do not evaluate grades or invent facts. '
        'Use exact supplied evidence IDs. Irrelevant or missing support must yield an empty list. '
        'Project statements are not independent adoption or recognition. D6 accepts actual project, platform or organizational workflow integration; do not restrict it to Pujiang. '
        'D1 requires original project scientific or technical facts. Explain the routing briefly. '
        'This is automated evidence routing, not human approval.',inline_input=True)
    routes=routing.model_dump(exclude={'explanation'})
    known={e['id'] for e in evidence+replay['evidence']}
    if any(set(ids)-known for ids in routes.values()):raise ValueError('证据路由引用了本轮未提供的来源')
    if not set(routes['D1'])&{e['id'] for e in evidence}:raise WaitingForInput('当前成果缺少可用于双层评价的原始专业事实',routes)
    outcome_id=scope['outcome_id'];parent_id='SCOPE-'+outcome_id
    delivery={'schema_version':'indicator-workspace.v6',
        'project_profile':{'project_id':scope['project_id'],'title':inputs['project_name']},
        'step3_frozen_outcomes':{'status':'frozen','source_provider':'本工单成果卡阶段',
            'outcomes':[{'outcome_id':parent_id,'title':inputs['project_name'],'child_outcomes':[
                {'outcome_id':outcome_id,'title':intake['canonical_name'],'outcome_card':intake['outcome_card']}]}]},
        'milestone_context':{'review_boundary':inputs.get('search_boundary')}}
    note='本工单成果卡完成原文引用核对后，自动按当前证据ID分配维度；非人工审核。'+routing.explanation
    workspace=child_workspace(delivery,scope,replay,outputs['attribution'],child_id=outcome_id,routes=routes,review_note=note)
    workspace['evaluation_framework']['outcome_cards'][0]['source_provider']='本工单成果卡阶段'
    workspace['pipeline_provenance']['scope_origin']='current_ticket_intake'
    atomic_json(folder/'evidence-routes.json',routing.model_dump())
    return workspace
