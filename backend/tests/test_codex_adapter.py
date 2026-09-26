"""Shared assessment fixtures for current workflow tests.

The former single-task Codex API tests were retired with the old product
routes; these two fixtures remain shared by the project workflow tests.
"""
from app.skill_loader import contract


def fixture_assessment():
    evidence=[{'id':f'P{i}','title':'测试材料','kind':'project','material_id':'material-1','source':'测试项目报告','locator':f'第{i}段','quote':quote,'url':None,'date':None,'supports':'仅支持项目材料中记载的验证事实','does_not_prove':'不证明独立外部使用','verification':'project_statement'} for i,quote in [(1,'示例探针完成光谱验证。'),(2,'示例探针属于测试项目。')]]
    fields=[{'name':name,'value':'未见明确表述','status':'missing','evidence_ids':[]} for name in sorted(contract.CARD_FIELDS)]
    for f in fields:
        if f['name']=='outcome_name':f.update(value='示例探针',status='confirmed',evidence_ids=['P1','P2'])
    upgrade=lambda n:{'target_level':n,'level_name':contract.LEVELS[n-1],'need':'提供真实使用证据','proof_materials':['使用记录']}
    return {'schema_version':'wu-outcome-v2.1','rubric_id':'wu-v2-six-levels','input_mode':'name_plus_materials','project_context':{'status':'resolved','project_name':'测试项目','project_id':None,'source':'测试项目报告'},'outcome_resolution':{'user_query':'示例探针','canonical_name':'示例探针','aliases':[],'resolution_confidence':'high','candidate_outcomes':[{'name':'示例探针','scope':'测试项目所述示例探针','evidence_ids':['P1','P2']}],'scope_note':'两处项目原文对齐','source_refs':['P1','P2']},'outcome_card':fields,'evaluation_status':'formal','summary':'仅用于程序测试的成果。','current_level':1,'level_name':contract.LEVELS[0],'level_reasons':[{'text':'完成验证','kind':'support','evidence_ids':['P1']},{'text':'尚无真实使用证据','kind':'boundary','evidence_ids':[]}],'boundary_gap':'真实任务使用尚待证实','key_judgments':[{'topic':'完成情况','project_claim':'完成光谱验证','assessment':'材料有记载','project_evidence_ids':['P1'],'evaluation_evidence_ids':[]}],'upgrade_plus_1':upgrade(2),'upgrade_plus_2':upgrade(3),'next_tasks':{'project_material':{'title':'请项目组补证','summary':'补充使用证据','body':'项目组您好，请提供使用记录。'},'expert_review':None},'evidence_index':evidence,'claims':[{'text':'完成光谱验证','evidence_ids':['P1'],'status':'supported_by_project_material'}],'dimensions':[{'id':f'D{i}','grade':None,'conclusion':'证据有限','evidence_ids':[],'gaps':['待补证']} for i in range(1,8)],'ai_attribution':{'ai_role':'待确认','baseline':'待补充','confirmed_increment':'尚不能确认','confounders':[],'evidence_ids':[],'gaps':['缺少归因实验']},'external_search_status':'not_verified'}


def material():
    return [{'id':'material-1','filename':'test.txt','text':'示例探针完成光谱验证。\n示例探针属于测试项目。'}]
