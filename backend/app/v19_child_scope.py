"""Project a frozen child without inheriting its parent's evidence or conclusions.
All evidence routes are explicit caller-reviewed IDs, never keyword matching.
"""
import copy


def child_workspace(delivery,intake,replay,attribution,*,child_id,routes,review_note):
    if not review_note.strip():raise ValueError('子成果适配必须保留范围审查说明')
    pid=intake['project_id'];local_id=intake['outcome_id']
    if delivery.get('project_profile',{}).get('project_id')!=pid:raise ValueError('冻结清单项目不一致')
    if (replay['project_id'],replay['outcome_id'])!=(pid,local_id):raise ValueError('Search成果范围不一致')
    matches=[(parent,child) for parent in delivery.get('step3_frozen_outcomes',{}).get('outcomes',[]) for child in parent.get('child_outcomes',[]) if child.get('outcome_id')==child_id]
    if len(matches)!=1:raise ValueError('冻结子成果ID不存在或重复')
    parent,child=matches[0]
    source=intake['attribution_preparation']['evidence']
    evidence={e['id']:{'source_id':e['id'],'quote':e['text'],'locator':e['locator'],'source_type':'项目内部原文','outcome_ids':[child_id]} for e in source}
    for e in replay['evidence']:
        if e['id'] in evidence:raise ValueError('项目与Search证据ID冲突')
        source_type='本轮公开检索与原文核验，通过评审时间审计' if replay.get('mode')=='live_search' else '历史Search记录，包含原文与索引判断，需区分'
        evidence[e['id']]={'source_id':e['id'],'quote':e['text'],'locator':e['locator'],'url':e.get('url'),'source_type':source_type,'outcome_ids':[child_id]}
    dimensions={};bindings=[]
    for number in range(1,8):
        dim=f'D{number}'
        requested=routes.get(dim,[])
        if not set(requested).issubset(evidence):raise ValueError('路由引用未知证据')
        facts=[copy.deepcopy(evidence[i]) for i in requested if i in {x['id'] for x in source}]
        external=[copy.deepcopy(evidence[i]) for i in requested if i not in {x['id'] for x in source}]
        unit={'dimension_id':dim,'outcome_id':child_id,'project_facts':facts,'external_search':external,'internal_search':[],
              'professional_metrics':[],'branches':[],'step3_problem_links':[],
              'problem_mapping_status':'missing_requires_upstream','scope_note':review_note,
              'missing_state':'已有依据，仍需核验' if requested else '待核验'}
        if dim in ('D1','D2','D5'):
            unit['ai_contribution']={'components':[],'attribution_records':attribution['contribution_result'],
                'unresolved_items':attribution['unresolved_items'],'source_ids':[e['id'] for e in source],
                'policy':'确定性归因工具分析，不是独立实验或专家判断。'}
        else:unit['ai_contribution']={'components':[],'policy':'非本维度主要判断对象'}
        # Raw scientific facts meet the original professional-facts intake contract,
        # without importing previous metric grades or creating a benchmark.
        if dim=='D1':
            for fact in facts:
                metric={'metric_id':'PIPELINE-FACT-'+fact['source_id'],'metric_name':'项目报告专业事实（原文待核验）',
                    'source_layer':'L4','criterion':'仅按原文记载及其测试条件判断，不预设达标或等级',
                    'evidence_preview':[{'evidence_id':fact['source_id'],'summary':fact['quote'],'source_ref':fact}],
                    'missing_evidence':['不等于独立复测；指标可比性由评价阶段核对']}
                unit['professional_metrics'].append(metric)
                bindings.append({'outcome_ids':[child_id],'branch_id':'D1.2','dimension_id':'D1','metric':metric})
        dimensions[dim]=unit
    card={'outcome_id':child_id,'canonical_outcome_id':child_id,'title':child['title'],'child_outcome_ids':[],
          'child_outcomes':[],'problem_ids':[],'parent_outcome_id':parent['outcome_id'],'scope':review_note,
          'source_card':copy.deepcopy(child),'source_provider':'原Step3冻结子成果；本轮只读投影','status':'frozen'}
    return {'schema_version':'indicator-workspace.v6',
        'project_profile':{'project_id':pid,'title':delivery['project_profile']['title'],
            'evaluation_scope':f"仅冻结子成果{child_id}（{child['title']}），不是整个{parent['outcome_id']}或全项目"},
        'evaluation_framework':{'outcome_cards':[card]},
        'step3_frozen_outcomes':copy.deepcopy(delivery['step3_frozen_outcomes']),
        'outcome_card_confirmation':{'status':'confirmed','basis':review_note},
        'milestone_context':copy.deepcopy(delivery.get('milestone_context',{})),
        'evidence_adapter':{'schema_version':'pipeline-child-evidence.v1','professional_metric_bindings':bindings,
            'outcome_packets':{child_id:{'source_card':card,'dimensions':dimensions}},
            'channel_status':{'internal_search':{'status':'not_delivered'}},
            'governance':{'parent_evidence_inherited':False,'review_note':review_note}},
        'available_search':{'external_group':{'status':'loaded','claim_count':len(replay['evidence'])}},
        'contribution_attribution':{},'evidence_repository':{},
        'pipeline_provenance':{'local_outcome_id':local_id,'frozen_child_id':child_id,'parent_id':parent['outcome_id'],

            'wu_evaluation_used':False,'historical_replay':replay.get('mode','historical_replay')=='historical_replay'}}
