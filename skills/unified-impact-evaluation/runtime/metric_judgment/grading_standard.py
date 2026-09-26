"""Current user supplied grading standard, independent of transport and evidence."""
import json
from pathlib import Path

STANDARD=json.loads((Path(__file__).resolve().parents[2]/'references/grading-standard-20260925.json').read_text(encoding='utf-8'))
VERSION=STANDARD['version']
L_LEVEL_CRITERIA={key:value['name']+'：'+value['condition'] for key,value in STANDARD['levels'].items()}

FINAL_JUDGMENT_POLICY='''
【当前优先判级标准：2026-09-25 19:30】
用户提供的《科研成果六级影响力分级及理论依据-09251930》覆盖输入中的旧L级、旧D6范围与缺证留空规则。
每个完成的维度必须给G1-G5，成果和本轮范围必须给L1-L6；禁止用待确认、待核验、初步评价、null代替等级。
L1成果形成与基本有效性验证；L2局部真实任务作用；L3独立外部采用及实际结果；L4多主体持续或重复采用及后续成果；L5长期嵌入流程的领域基础能力；L6实质改变研究或工作方式。研究内部验证支持L1，不必先有真实应用；真实任务使用从L2开始。
按现有证据支持的最高状态判级，不求平均，不为了给等级发明事实。G1是本轮证据未建立更高成熟度时的保守基档：允许无引文，但须明确本轮材料范围和缺少的更高档依据，不能断言现实中绝对不存在影响。G2及以上必须有依据。L级必须有成果本身的形成/验证证据。
所有状态字段使用明确成立、部分成立、本轮未体现、尚未形成、不适用等schema允许值，不输出待核验。缺少材料只说明本轮未体现，不把它当作否定性原始事实。已评等级是最终输出，低置信度和升级所需材料不能清空等级。
采用当前已提交材料证明的技术和影响状态；阶段截止日仍作为历史审计边界。内部回顾报告可以支持其记载的成果事实；事件日期不明写入时间限制，不能倒推为截止日前完成，也不能因此清空现有成果等级。
D6考察项目、平台或组织主线的接入、实际调用、反馈及持续运行，不限浦江。设计关系不等于实际调用，一次闭环不等于长期运行。
D7评定独立第三方评测、专业采用或权威认可。仅正式论文、专利、宣传或同源转载不证明外部认可；公开不等于复用，关注不等于认可。归属与适用范围可以解释，但不得让分类悬而未决取代等级。
只引用本轮提供的证据，技术背景文献不能冒充本项目的外部使用或独立认可；不得虚构引用、使用者、日期或数量。
'''


def apply_current_dimension_scope(payload):
    """Keep evidence and IDs; replace superseded scope/policy, not source facts."""
    payload['grading_standard']=STANDARD
    dim=payload.get('dimension',{})
    key=dim.get('dimension_id') or dim.get('question_id')
    if key in STANDARD['dimensions']:
        dim.update(name=STANDARD['dimensions'][key]['name'],question=STANDARD['dimensions'][key]['question'])
    return payload
