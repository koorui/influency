"""Shared evaluation and evidence contracts from the September 4 design review.

These rules describe judgments, not the upstream extraction or manager UI.
"""
from __future__ import annotations

import copy
from typing import Any

OUTCOME_POSITIONS = ["核心成果", "关键支撑", "应用验证", "常规交付", "前期基础", "归属待核", "待判断"]
SOURCE_TYPES = ["项目侧统计", "项目材料声明", "外部独立核验", "实验/测试结果", "系统识别结果", "待核实"]
CONFIRMATION_METHODS = {
    "项目方补充材料": "项目方",
    "外部检索/独立核验": "外部检索与核验组",
    "补充对照或测试": "项目方与测试方",
    "领域专家专业判断": "领域专家",
    "成果粒度或映射确认": "Step 3成果凝练组",
}
COLLABORATION_STATES = ["只有设计关系", "发生真实输入输出", "形成跨课题任务链", "形成反馈闭环", "持续重复运行", "本轮未体现"]

CLASSIFICATION_POLICY = {
    "positions": OUTCOME_POSITIONS,
    "rule": "项目方宣称成果、代表成果组是输入，系统归类是评价结果。核心成果须同时说明对应核心问题、关键瓶颈推进和项目期实质新增；关键支撑与应用验证单列，归属不清标为归属待核。",
    "granularity": "只使用Step 3冻结ID。成果组、子成果与独立评价单元分别计数；组内模型、数据、材料、反应和自动化的证据必须注明具体子成果ID，不能以单个子成果优势推定整组核心性或AI贡献。缺独立评价边界时请求Step 3确认，不自行拆分。",
    "evidence": "归类依据包含核心问题链接、项目方声明来源、D1/D2依据和未决归属；上游角色标签不能替代系统判断。",
}
PROJECT_AGGREGATION_POLICY = {
    "innovation": "D1–D2以经系统判断的核心成果牵引，列明项目期新增、同期同口径最佳方法比较、AI实际贡献；没有确认核心成果时保留待判断，不为了汇总强行选核心。",
    "impact": "D3–D7以核心成果为主，按维度纳入其他真正产生影响的成果；数据库等关键支撑即使不是核心创新，有独立真实复用也进入D4。",
    "scope": "每个D列出涉及成果ID、纳入理由、覆盖度、深度和集中度；共享来源、同一团队或事件去重，父子成果不重复统计。单任务优势不得扩大为项目整体领先。",
    "summary": "先给明确判断，再给2–4个有解释力的事实；不足2条按实有展示。创新分项目期新增、同期比较、AI贡献；影响分学术与开放复用、真实应用、项目主线、外部专业认可与领域影响四类。",
}
EVIDENCE_ORGANIZATION = {
    "schema_version": "indicator-evidence-organization.v1",
    "levels": [
        {"level": "classification", "name": "归类依据", "question": "为什么属于核心成果、关键支撑或应用验证", "contents": "核心问题链接、项目方声明、系统归类理由与缺口；引用成果维度事实，不重复复制原件。"},
        {"level": "outcome", "name": "成果依据", "question": "这项具体成果为什么得到当前评价", "contents": "核心问题、项目前基础与本期新增、同期比较、AI归因、实际影响，保留冻结父子ID。"},
        {"level": "dimension", "name": "项目维度依据", "question": "整个项目为何得到这个维度判断", "contents": "涉及成果、纳入理由、关键事实、支持与限制、覆盖范围及补证责任；原始来源通过引用下钻。"},
    ],
    "fact_fields": ["事实", "来源及定位", "来源性质", "支持什么", "还不能证明什么", "涉及成果", "时间与适用范围"],
    "source_types": SOURCE_TYPES,
    "quantity_rule": "数量必须标明对象、单位、统计时段、范围、去重状态和核验状态。项目侧平台用户不等于外部独立科研用户，注册、下载、测试与真实运行分别记录。未知数量用空值及待去重/待汇总/待核实，只有明确零值证据才能写0。",
    "direction_rule": "影响是否发生与评价方向分开。D7同时记录正面认可、专业质疑、争议与中性讨论；负面讨论不计为正面认可，不相互抵消或折成分数。",
    "source_rule": "只引用当前输入的可追溯来源，保留原始编号、URL或文件定位；没有外部核验就标待补充。规则说明属于评价标准，已有证据和待补充属于评价依据。",
    "confirmation_methods": CONFIRMATION_METHODS,
}
COLLABORATION_POLICY = {
    "states": COLLABORATION_STATES,
    "rule": "先从任务书还原应有关系，再核查实际输入输出，依次判断任务链、反馈闭环、持续重复运行；采用证据能支持的最高阶段。任务书设计不证明协同发生，一次运行不证明持续闭环。",
    "chain_fields": ["提供课题", "使用课题", "交付对象", "实际任务", "产生结果", "接口或调用日志", "反馈记录", "重复运行时段与次数"],
    "boundary": "项目内部课题协同独立判断，项目或组织主线正式集成只进入D6。集成课题可能协调多个节点，不能强画成最后一个串行节点。",
}
REVIEW_POLICY = {
    "evaluation_state": "系统独立评测 · 专家校准前",
    "rule": "先独立判断，再提出会改变结论且材料和检索无法解决的专业争议。历史答辩意见和设计示例不作为待拟合答案；未实际完成校准不得标记已专家校准。",
    "responsibility": "缺材料由项目方补充，外部事实交检索核验，同口径验证交项目方与测试方；有没有日志不交专家。归类粒度问题交Step 3。这里只说明责任，不分发任务或收集专家意见。",
    "management": "只输出最多4项可能改变总体判断的项目级动作，分别考虑核心问题、核心贡献、价值转化和项目结构缺口，写明下一阶段应看到什么；不逐D补短板或照抄专家意见。",
}

DIMENSION_OBSERVABLES = {
    "D1": ["核心问题与具体成果对应", "同任务能力增量", "同期比较对象、数据集、协议和关键结果"],
    "D2": ["项目前版本及日期", "本期新增及形成时间", "新增性质与AI/非AI归因证据"],
    "D3": ["去重后的独立学术响应数", "独立团队数", "实质跟进、复现与使用深度"],
    "D4": ["项目侧注册/活跃/测试规模", "独立团队真实运行", "复现与二次开发"],
    "D5": ["真实科研或工程任务", "使用案例及独立团队", "效果对照与持续时间"],
    "D6": ["平台或流程侧正式接入记录", "实际调用次数与任务", "运行时段与维护责任"],
    "D7": ["标准或规范采纳", "独立专业评价和机构采用", "公开专业讨论、质疑及争议的方向"],
}

G_LEVEL_CRITERIA = {
    "D1": ["提出问题或方案", "完成内部验证", "形成清楚、可比较的改进", "经外部验证达到专业领先", "推动技术前沿或形成新范式"],
    "D2": ["沿用已有基础", "形成项目期适配或改进", "形成边界清楚的新方法或产品", "原创路线获独立确认", "形成基础性原创并被广泛沿用"],
    "D3": ["尚无独立关注", "成果公开并开始传播", "出现独立引用、比较或跟进", "多团队持续跟进并形成方向影响", "改变研究议题或学术路径"],
    "D4": ["尚不可获得", "已经公开或可申请获得", "有独立团队成功复用", "形成持续复用和开发群体", "成为广泛依赖的开放基础设施"],
    "D5": ["尚未进入真实任务", "在项目内部真实任务中使用", "独立外部团队实际使用", "多家单位持续用于专业工作", "成为多个领域的常规能力"],
    "D6": ["单点成果", "接入项目内部流程", "与多环节或外部流程协同", "成为稳定平台或主线能力", "成为跨平台、跨领域基础能力"],
    "D7": ["主要为项目方自述", "取得独立第三方的具体评测或专业评价", "获得独立同行实质采用或多项认可", "获得高层次采纳、标准或权威认可", "形成跨领域广泛共识"],
}
from .grading_standard import L_LEVEL_CRITERIA


# Appended after each task's base prompt so the same schema reaches the actual
# model call, the normalizer, and the public product.
DIMENSION_OUTPUT_REQUIREMENTS = """
【9.4修订：事实与评价依据输出】
当前判断先给具体观点，优先用实际数量/行为解释，禁止无参照的“影响有限”。
在原JSON中增加：
"key_facts":[{"fact":"具体事实","source_ids":["输入中的来源编号"],"source_type":"项目侧统计|项目材料声明|外部独立核验|实验/测试结果|系统识别结果|待核实","supports":"支持的具体判断","does_not_prove":"仍不能证明的范围","effect":"支持|限制|反驳|待分类","direction":"正面|负面|争议|中性|待分类","outcome_ids":["当前冻结成果或其子成果ID"],"time_scope":"证据所属时段","quantity":{"value":null,"unit":"单位","population":"统计对象及范围","period":"统计时段","status":"已核实|项目侧报告|待去重|待汇总|待核实","deduplication":"去重口径或待去重"}}],
"confirmation_requests":[{"issue":"还需确认什么","method":"项目方补充材料|外部检索/独立核验|补充对照或测试|领域专家专业判断|成果粒度或映射确认","changes_judgment":true,"professional_dispute":false,"expected_evidence":"应补充的材料","affected_judgment":"会改变哪个具体判断"}],
"ai_analysis":{"position":"AI参与位置","mechanism":"作用机制","observed_change":"实际变化","controls":"对照或消融","attributable_extent":"能够归因到什么程度","confounders":["非AI混杂因素"],"source_ids":["归因证据来源"]}。
key_facts最多4条，不足按实有；完整依据放evidence_chain，每条也记录fact、source_type、supports、does_not_prove、effect、direction、outcome_ids、time_scope。来源只能用当前输入编号。
关键数字必须标明性质、对象、时段、范围和去重状态；未取得记录不是0；未知数量value为null。不确定性写待核实/待汇总/待去重。
AI分析用于D1、D2、D5，其他维度为空对象；自动化效率提升不能充当AI贡献率。
D7判断外部专业评价及领域影响是否发生，正面认可、负面专业质疑和争议都记录但不混成正面认可。
同一冻结组内不同子成果分别注明证据适用ID，不能把模型、数据、实验混成统一创新或AI归因结论。
只有真正会改变判断且需专业判断的争议才交专家；没有日志或材料不是专家问题。
"""
OUTCOME_OUTPUT_REQUIREMENTS = """
【9.4修订：成果归类与依据输出】
成果定位使用：核心成果、关键支撑、应用验证、常规交付、前期基础、归属待核、待判断。
保留冻结父子ID与输入声明；不因为上游名为代表/重点成果而认定核心，不新增或拆并评价对象。
增加"classification_reason":"对应核心问题、瓶颈推进和本期新增为何支持该归类",
"evaluated_child_ids":["得到直接判断的冻结子成果ID"],"scope_limitations":["未能覆盖的子成果或独立评价粒度待确认"],
"confirmed":"目前可以确认什么","unconfirmed":"目前还不能确认什么"。
涉及不同性质的子成果且无法形成统一归类时，整体保留待判断，并指出需要上游明确的独立单元，不能抹掉子成果差异。
decisive_evidence只引用输入维度中的source_ids；核心成果必须有D1和D2证据，不能由传播热度或项目方包装决定。
"""
PROJECT_OUTPUT_REQUIREMENTS = """
【9.4修订：项目级综合和依据输出】
按project_aggregation_policy执行核心成果牵引、逐维度纳入真实贡献、项目范围校正，不平均、不强选核心。
dimension_portfolio中每个D除coverage/depth/concentration，增加conclusion、included_outcomes（[{outcome_id,reason}]）、key_facts和confirmation_requests。
key_facts沿用输入中的结构化事实（fact、source_ids、source_type、supports、does_not_prove、effect、direction、outcome_ids、time_scope、quantity），最多4条；完整依据引用原有成果维度，不编新事实或来源。
增加"innovation_summary":{"project_increment":"本期新增判断","contemporary_comparison":"同期同口径比较","ai_contribution":"AI实际贡献"}，
"influence_summary":{"academic_and_reuse":"学术与开放复用","real_application":"真实应用","pujiang_integration":"项目主线","professional_response":"外部专业认可与领域影响，区分方向"}。
system_collaboration.status只能是只有设计关系、发生真实输入输出、形成跨课题任务链、形成反馈闭环、持续重复运行、本轮未体现；增加design_basis（任务书设计来源）和chains：
[{provider,consumer,artifact,task,result,source_ids,invocation_source_ids,feedback_source_ids,repeat_source_ids}]。
提供方/使用方是实际课题名；设计来源不是调用证据；没有实际输入输出记录不能高于只有设计关系，反馈和持续运行分别需要独立记录。
协同原始材料中的历史专家意见、专业复核问题及示例不得作为结论；系统先独立评测，专家后校准。
management_advice最多4条，每条写项目级动作及下一阶段应看到什么，须能改变总体判断，不机械逐D补短板。
"""


def text_list(value: Any) -> list[str]:
    return [str(item) for item in value if isinstance(item, (str, int))] if isinstance(value, list) else []


def normalize_facts(value: Any, *, limit: int = 4) -> list[dict[str, Any]]:
    rows = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, dict) or not item.get("fact"):
            continue
        quantity = item.get("quantity") if isinstance(item.get("quantity"), dict) else {}
        state = quantity.get("status", "待核实")
        if state not in {"已核实", "项目侧报告", "待去重", "待汇总", "待核实"}:
            state = "待核实"
        number = quantity.get("value")
        if state not in {"已核实", "项目侧报告"} or not item.get("source_ids"):
            number = None
        if number is not None and not all(quantity.get(key) for key in ("unit", "population", "period", "deduplication")):
            number, state = None, "待核实"
        rows.append({
            "fact": str(item["fact"]),
            "source_ids": text_list(item.get("source_ids")),
            "source_type": item.get("source_type") if item.get("source_type") in SOURCE_TYPES else "待核实",
            "supports": str(item.get("supports") or "待说明"),
            "does_not_prove": str(item.get("does_not_prove") or "适用范围待核实"),
            "effect": item.get("effect") if item.get("effect") in {"支持", "限制", "反驳"} else "待分类",
            "direction": item.get("direction") if item.get("direction") in {"正面", "负面", "争议", "中性"} else "待分类",
            "outcome_ids": text_list(item.get("outcome_ids")),
            "time_scope": str(item.get("time_scope") or "待核实"),
            "quantity": {"value": number, "status": state, **{key: str(quantity.get(key) or "") for key in ("unit", "population", "period", "deduplication")}},
        })
    return rows[:limit]


def normalize_requests(value: Any) -> list[dict[str, Any]]:
    rows = []
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, dict) or not item.get("issue"):
            continue
        method = str(item.get("method") or "待分派")
        professional = item.get("professional_dispute") is True
        changes = item.get("changes_judgment") is True
        if method not in CONFIRMATION_METHODS or (method == "领域专家专业判断" and not (professional and changes)):
            method = "待分派"
        rows.append({
            "issue": str(item["issue"]), "method": method,
            "owner": CONFIRMATION_METHODS.get(method, "待分派"),
            "professional_dispute": professional, "changes_judgment": changes,
            "expected_evidence": str(item.get("expected_evidence") or ""),
            "affected_judgment": str(item.get("affected_judgment") or ""),
        })
    return rows[:8]


def normalize_ai(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or not value:
        return {}
    return {**{key: str(value.get(key) or "待核实") for key in ("position", "mechanism", "observed_change", "controls", "attributable_extent")},
            "confounders": text_list(value.get("confounders")), "source_ids": text_list(value.get("source_ids"))}


def evidence_dossier(outcomes: list[dict[str, Any]], project: dict[str, Any]) -> dict[str, Any]:
    """Three reading levels referencing one set of outcome dimension facts."""
    classification, outcome_index = [], []
    for row in outcomes:
        oid = str(row.get("outcome_id") or "")
        synthesis = row.get("synthesis") or {}
        classification.append({"outcome_id": oid, "position": row.get("core_position", "待判断"),
                               "reason": synthesis.get("classification_reason", "尚未形成系统归类依据。"),
                               "evidence_refs": copy.deepcopy(synthesis.get("decisive_evidence") or []),
                               "scope_limitations": copy.deepcopy(synthesis.get("scope_limitations") or [])})
        outcome_index.append({"outcome_id": oid, "title": row.get("title"),
                              "dimension_ids": [d["dimension_id"] for d in row.get("dimensions") or []],
                              "child_outcome_ids": copy.deepcopy(row.get("child_outcome_ids") or [])})
    return {"schema_version": "indicator-evidence-dossier.v1", "classification": classification,
            "outcomes": outcome_index, "project_dimensions": copy.deepcopy(project.get("dimension_portfolio") or {})}
