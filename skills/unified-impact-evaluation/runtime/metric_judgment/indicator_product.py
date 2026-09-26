from __future__ import annotations

import copy
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any

from .d_dimension_framework import (
    AGENT_EXECUTION_PROTOCOL,
    D_BRANCH_INDICATORS,
    D_DIMENSIONS,
    DIMENSION_INPUT_CONTRACTS,
    DIMENSION_STATUSES,
    HARD_RULES,
    LAYER_SUMMARY_METHOD,
    UPSTREAM_COMPONENT_CONTRACTS,
)
from .milestones import EVIDENCE_TIME_ROLES
from .trace import TracingLLMClient
from .prepared_evidence import build_prepared_evidence
from .active_indicators import build_indicator_tree, criteria_for_dimension, POLICY
from .material_routing import REVIEW as MATERIAL_REVIEW
from .evaluation_policy import (
    CLASSIFICATION_POLICY, PROJECT_AGGREGATION_POLICY, EVIDENCE_ORGANIZATION,
    COLLABORATION_POLICY, COLLABORATION_STATES, REVIEW_POLICY, OUTCOME_POSITIONS,
    DIMENSION_OBSERVABLES, G_LEVEL_CRITERIA, L_LEVEL_CRITERIA, DIMENSION_OUTPUT_REQUIREMENTS,
    OUTCOME_OUTPUT_REQUIREMENTS, PROJECT_OUTPUT_REQUIREMENTS,
    normalize_facts, normalize_requests, normalize_ai, text_list, evidence_dossier,
)

PUBLIC_NARRATIVE_REQUIREMENTS = """

【面向使用者的中文叙述规范】
JSON键名和编号仅供程序解析；所有会展示给使用者的文字值必须写成自然、完整、可直接阅读的中文，包括原因、结论、分析、摘要、事实、反证、缺口、不确定性和管理建议。
1. 禁止在文字值中复述任何内部字段名、数据库键名或英文枚举，例如 contribution_attribution、human_intervention_risk、data_platform_confounding_risk、claim_evidence、source_gap、time_role、metric_id、outcome_id、current_level、evidence_confidence、judgment_confidence。
2. 禁止使用“字段名为‘值’”“某记录显示某键为某枚举”这类技术描述。应直接翻译业务含义，例如写“人工干预风险尚本轮未体现，数据与平台因素可能造成中等程度的混杂”，不得写原始字段名。
3. 禁止在叙述中出现内部编号和来源编号，例如 IQ、D、G、P、OUT、EXT、EVD、SRC、DECL、SIM、EXP、L1—L4及其带数字或连字符的变体。需要引用时使用中文名称，例如“人工智能实质贡献度”“技术性能与任务表现”“成果综合等级”“项目综合层级”“外部核验记录”。编号只允许放在JSON专用ID字段或source_ids数组中。
4. 禁止输出 Level 1、Level 2、high、medium、low、core、decisive、corroborative、not_primary 等英文等级或角色；分别写成“1级、2级”“高、中、低”“核心依据、决定性依据、校验性依据、非主要依据”。
5. E_conf和J_conf只作为内部键存在，公开文字中分别称为“证据可信度”和“判断把握度”。不得把二者写成统计概率或置信区间。
6. Search、SOTA等流程术语在公开文字中分别写成“检索核验”“当前最佳水平”。模型、数据集、论文、机构和材料的正式专有名称可以保留，但首次出现时应尽量补充中文含义；不得把程序字段误当成专业术语。
7. 输出前逐句自检：如果一句话像在解释JSON、数据库或程序日志，必须改写为业务事实、评价含义及其限制。
"""

EVALUATION_STANDARD_VERSION = "outcome-d1-d7-evaluation.v19"

D_DIMENSION_SYSTEM_PROMPT = """你是重大科研项目创新影响力评价专家。本次只评价一项Step 3冻结成果的一个D维度。
当前正式指标由 active_indicator_criteria 提供。先按成果类型判断适用性，再用所需材料核验；新增指标不代表已有依据，缺材料必须本轮未体现。历史材料中的旧数量目标、规模标签和被移除指标不能作为现行评价标准。下级指标只细化三个分支，不按条数加权或增设总分。
评价对象及父子ID已经由Step 3冻结；项目材料、检索核验、AI贡献组件和L2-L4专业事实已经由适配层路由到该成果。你不得合并、拆分、改名或重新凝练成果，不得自行检索或制造上游事实。
先逐个判断本维度的三个原子分支，再依照本维度输入契约和综合规则形成维度状态。项目方声明与外部事实必须分开；检索事实只能标为支持、限制或反驳，不能直接充当D结论。材料缺失或公开检索未发现只能写“本轮未体现”，不能写成事实不存在。
严格执行输入中的 agent_execution_protocol 和本维度三组 upstream_component_contract：先按 input_path 找到材料，再逐项核对 package_id、target_branches、required_fields 和 prohibited_use，然后严格依照 agent_use_steps 的顺序执行。每一步只能更新其 writes_to 指定的 JSON 字段；先写原子分支、证据链、支持/反证和缺口，最后才综合维度状态。内部Search组件用于还原项目内部事实与声明，AI贡献组件只用于规定的归因或对象消歧，外部Search组件用于外部核验。某组在本维度标为非主要或无必需组件时，不得强行从该组材料推断结论；不得跨组替代缺失组件。缺少必需字段时，相应原子判断必须保留证据缺口并按规则降为本轮未体现或部分成立。
D1的核心问题对应只能读取Step 3显式问题链接；若只收到核心问题清单但没有成果—问题映射，D1.1必须本轮未体现，禁止模型按关键词自行匹配。
D1判断核心问题推进、能力增量和横向先进性；D2判断项目期新增、新增性质和可归因性；D3判断独立学术行为深度；D4判断开放、可用和真实复用；D5分别判断内部真实使用、外部独立使用及效果持续性；D6只判断项目或组织主线接入、调用和持续运行；D7只接受独立专业主体的评价、认可或采纳。项目内部课题协同不得计入D6，专利、项目方宣传和同源转载不得计入D7。
AI归因贯穿D1、D2和D5的相应事实链，必须区分AI、数据、算力、自动化、设备、领域知识、传统方法和人工的作用，但不得作为等权独立分数。L2-L4只作为专业事实，不得读取其历史等级、另行评分或按数量赋权。
区分当前节点之前的基础、当前评价窗口内的新增和当前节点之后的影响；后续影响不得反证项目期当时领先。
不打分、不计算平均值、不输出成果G级。状态只允许“明确成立、部分成立、尚未形成、本轮未体现、不适用”；不适用必须有明确范围依据。
专家只处理项目材料和检索都无法解决、且会改变当前判断的专业争议；不得让专家重复评价所有分支。
只输出JSON对象：
{
  "status":"明确成立|部分成立|尚未形成|本轮未体现|不适用",
  "branch_judgments":[{"branch_id":"当前分支ID","status":"明确成立|部分成立|尚未形成|本轮未体现|不适用","conclusion":"原子判断","decisive_source_ids":["来源编号"]}],
  "core_position":"核心成果|关键支撑|应用验证|常规交付|前期基础|归属待核|待判断",
  "conclusion":"不超过120字的直接判断",
  "expert_analysis":"完整说明事实、比较、时间归属、反证与结论边界",
  "time_assessment":{"prior_baseline":"项目前或当前节点前基础","current_window_increment":"项目期新增","subsequent_effect":"后续影响"},
  "evidence_chain":[{"claim":"子判断","fact":"材料中的具体事实","source_ids":["来源编号"],"outcome_ids":["当前冻结成果或其子成果ID"],"source_type":"项目材料声明|外部独立核验|实验/测试结果|待核实","supports":"支持的具体判断","does_not_prove":"不能据此证明的范围","effect":"支持|限制|反驳|待分类","direction":"正面|负面|争议|中性|待分类","time_scope":"证据所属时段","analysis":"证据如何支持或限制","reliability":"高|中|低"}],
  "basis":[{"source_id":"来源编号","fact":"支持事实"}],
  "counterevidence":[{"source_id":"来源编号","fact":"反证或限制"}],
  "professional_metric_use":[{"metric_id":"原L2-L4编号","role":"该专业事实如何支撑本维度"}],
  "ai_attribution":"D1/D2/D5填写AI作用、增量和混杂边界；其他维度写非主要判断对象",
  "missing_inputs":["可能改变结论的关键材料"],
  "expert_question":"只保留一个真正需要专家校准的问题，没有则为空",
  "evidence_confidence":"高|中|低",
  "judgment_confidence":"高|中|低"
}""" + PUBLIC_NARRATIVE_REQUIREMENTS


OUTCOME_SYNTHESIS_SYSTEM_PROMPT = """你是重大科研项目成果综合分析专家。依据同一成果D1-D7的直接判断形成成果观点。
不得新增指标、不得打分、不得计算平均值、不得输出G级。D1用于判断成果是否真正回应核心问题，D2判断原创和项目期新增；D3-D7形成影响力画像。
成果定位只允许“核心成果、关键支撑、应用验证、常规交付、前期基础、归属待核、待判断”。项目方宣称成果不等于系统核心成果，证据不足时只能待判断。
只输出JSON对象：
{
  "core_position":"核心成果|关键支撑|应用验证|常规交付|前期基础|归属待核|待判断",
  "innovation_conclusion":"综合D1-D2的创新判断",
  "influence_conclusion":"综合D3-D7的影响判断",
  "overall_conclusion":"不超过180字的成果观点",
  "decisive_evidence":[{"dimension_ids":["D1"],"source_ids":["来源"],"reason":"决定性作用"}],
  "main_limitations":["主要短板或结论边界"],
  "expert_questions":["最多3个需要专业校准的争议"],
  "next_evidence_requests":["最多5项应由上游补充的证据"],
  "evidence_confidence":"高|中|低",
  "judgment_confidence":"高|中|低"
}""" + PUBLIC_NARRATIVE_REQUIREMENTS


PROJECT_SYNTHESIS_SYSTEM_PROMPT = """你是重大科研项目创新影响力综合分析专家。输入是Step 3冻结成果的D1-D7判断及成果观点。
特定层只归纳D1、D2以及D5中的项目内部真实使用和效果，回答项目自己的核心问题解决得怎样；全局层只归纳D3、D4、D6、D7以及D5中的外部独立真实使用，回答成果是否走出去形成更广泛价值。两层不是新指标，不重新打分。
项目系统性/课题协同单独判断，不并入任何D维度，也不能替代外部扩散和真实影响。不得输出项目总分、平均分、G级或另一套维度。
项目级每个D都必须输出覆盖度、深度和集中度：覆盖度说明多少冻结主要成果得到有效证据；深度说明最强行为达到哪里；集中度说明证据是否过度集中在单一成果。不得平均，也不得让一个强成果代表全项目。
层级状态只允许“强、较强、初步形成、尚未形成、本轮未体现”。
只输出JSON对象：
{
  "dimension_portfolio":{"D1":{"coverage":"覆盖情况","depth":"最深证据或行为","concentration":"集中度及边界"},"D2":{},"D3":{},"D4":{},"D5":{},"D6":{},"D7":{}},
  "specific_layer":{"status":"强|较强|初步形成|尚未形成|本轮未体现","conclusion":"特定层判断","basis":["关键成果与维度依据"],"limitations":["限制"]},
  "global_layer":{"status":"强|较强|初步形成|尚未形成|本轮未体现","conclusion":"全局层判断","basis":["关键成果与维度依据"],"limitations":["限制"]},
  "system_collaboration":{"status":"只有设计关系|发生真实输入输出|形成跨课题任务链|形成反馈闭环|持续重复运行|本轮未体现","conclusion":"单独的项目系统性判断","evidence":["协同事实"],"gaps":["缺口"]},
  "overall_judgment":"项目整体创新影响力观点",
  "leading_outcomes":["真正值得重点看的成果"],
  "overclaimed_outcomes":["当前不宜认定为核心的成果及理由"],
  "expert_questions":["最多5个关键争议"],
  "management_advice":["下一阶段可行动建议"],
  "evidence_confidence":"高|中|低",
  "judgment_confidence":"高|中|低"
}""" + PUBLIC_NARRATIVE_REQUIREMENTS

D_DIMENSION_SYSTEM_PROMPT += DIMENSION_OUTPUT_REQUIREMENTS
D_DIMENSION_SYSTEM_PROMPT += """
证据链必须使用上方完整结构，每条都提供具体事实、来源编号和适用成果编号，不能只写子判断与分析。
没有可追溯事实时，key_facts与evidence_chain返回空数组；材料缺口写入missing_inputs，不得编造来源或成果编号来补齐结构。
三个分支必须全部保留。同一事实只陈述一次，分析说明其作用和限制，避免反复复述。证据链最多8条。
"""
OUTCOME_SYNTHESIS_SYSTEM_PROMPT += OUTCOME_OUTPUT_REQUIREMENTS
PROJECT_SYNTHESIS_SYSTEM_PROMPT += PROJECT_OUTPUT_REQUIREMENTS
D_DIMENSION_SYSTEM_PROMPT += """
【当前分级口径】本维度另给G1-G5成熟度。依据已核实且适用于本成果的事实，给出能够支撑的最高当前等级；尚待补充的分支、下一等级所需材料分别写入missing_inputs和gap_to_next，不因这些缺口清空已有证据支持的当前等级。本轮证据未建立更高成熟度时给G1保守基档，说明材料范围，不把缺证写成现实中的不存在。等级须依据本维度grade_criteria、可追溯事实和反证独立说明，不由定性状态机械换算。分级示例仍受本维度现行证据边界约束：D6只以项目主线接入、调用和持续运行评定；D7不能仅凭专利、项目方宣传或同源转载升级。
在JSON中增加"grade":{"level":"G1|G2|G3|G4|G5","reason":"当前等级的关键事实与边界","source_ids":["本轮输入的来源编号"],"gap_to_next":"进入下一级还缺什么"}。
"""
OUTCOME_SYNTHESIS_SYSTEM_PROMPT += """
【成果整体影响分级】依照当前impact_level_criteria从成果形成与验证开始判断L1-L6，不平均七维G级；证据有限时选有依据的较低等级，具体边界另列。
在JSON中增加"impact_level":{"level":"L1|L2|L3|L4|L5|L6","reason":"整体影响阶段及关键事实","source_ids":["本轮输入的来源编号"],"gap_to_next":"上一级所需的关键事实"}。
"""
PROJECT_SYNTHESIS_SYSTEM_PROMPT += """
【本轮评价范围影响分级】按当前六级门槛判断本轮覆盖成果的L1-L6，不扩大为全项目，不平均。
在JSON中增加"scope_impact_level":{"level":"L1|L2|L3|L4|L5|L6","reason":"本轮范围的整体影响判断","source_ids":["本轮输入的来源编号"],"gap_to_next":"上一级所需的关键事实","scope":"本轮实际评价范围"}。
"""


from .grading_standard import FINAL_JUDGMENT_POLICY, VERSION as GRADING_VERSION, apply_current_dimension_scope
D_DIMENSION_SYSTEM_PROMPT += FINAL_JUDGMENT_POLICY
OUTCOME_SYNTHESIS_SYSTEM_PROMPT += FINAL_JUDGMENT_POLICY
PROJECT_SYNTHESIS_SYSTEM_PROMPT += FINAL_JUDGMENT_POLICY

def build_indicator_input_contract(workspace: dict[str, Any]) -> dict[str, Any]:
    framework = workspace.get("evaluation_framework") or {}
    cards = copy.deepcopy(framework.get("outcome_cards") or [])
    adapter = workspace.get("evidence_adapter") or {}
    search = workspace.get("available_search") or {}
    external = search.get("external_group") or {}
    contribution = workspace.get("contribution_attribution") or {}
    channel_status = adapter.get("channel_status") or {}
    internal_search_status = channel_status.get("internal_search") or {}
    external_routing_audit = adapter.get("external_routing_audit") or {}
    step3_frozen = workspace.get("step3_frozen_outcomes") or {}
    outcome_portfolio = workspace.get("outcome_portfolio") or {}
    card_confirmation = workspace.get("outcome_card_confirmation") or {}
    cards_confirmed = card_confirmation.get("status") == "confirmed"
    if cards_confirmed:
        for card in cards:
            card["status"] = "confirmed"
            card["confirmation_basis"] = card_confirmation.get("basis")

    receipts = [
        _receipt(
            "step3_frozen_outcomes", "Step 3冻结成果", "Step 3成果凝练组", bool(cards) and cards_confirmed, len(cards),
            "已接收" if cards_confirmed else "待确认",
        ),
        _receipt(
            "internal_search", "内部 Search", "内部 Search 组",
            internal_search_status.get("status") == "loaded",
            sum(
                int((packet.get("counts") or {}).get("internal_search") or 0)
                for packet in (adapter.get("outcome_packets") or {}).values()
            ),
            state=(
                "已接收" if internal_search_status.get("status") == "loaded"
                else "上游未交付"
            ),
            required=False,
        ),
        _receipt(
            "ai_contribution", "AI贡献组件与归因", "贡献组",
            (contribution.get("component_extraction") or {}).get("status") == "loaded",
            int((contribution.get("component_extraction") or {}).get("component_count") or 0),
            required=False,
        ),
        _receipt(
            "external_search", "外部 Search", "外部 Search 组",
            external.get("status") == "loaded" and int(external_routing_audit.get("unrouted_claim_count") or 0) == 0,
            int(external.get("claim_count") or 0),
            state=(
                "已接收" if external.get("status") == "loaded" and int(external_routing_audit.get("unrouted_claim_count") or 0) == 0
                else "路由本轮未体现" if external.get("status") == "loaded"
                else "上游未交付"
            ),
            required=False,
        ),
        _receipt(
            "professional_metrics", "L2-L4专业事实", "指标事实底座",
            bool(adapter.get("professional_metric_bindings")),
            len(adapter.get("professional_metric_bindings") or []),
        ),
    ]
    return {
        "schema_version": "indicator-input-contract.v9",
        "milestone_context": copy.deepcopy(workspace.get("milestone_context") or {}),
        "evidence_time_roles": copy.deepcopy(EVIDENCE_TIME_ROLES),
        "boundary": {
            "indicator_group_owns": ["逐成果D1-D7评价", "特定层与全局层归纳", "项目系统性与课题协同单独判断", "证据冲突、缺口与专家问题识别"],
            "upstream_only": ["Step 3成果冻结", "内部 Search", "外部 Search与多源核验", "AI贡献组件抽取与归因材料生产", "外部专家复核与跨组回写"],
            "boundary_note": "指标组只按冻结ID做证据路由、规则综合和评价；不合并、拆分或改名成果，不重做检索、贡献材料生产或专家系统。",
        },
        "receipts": receipts,
        "ready_count": sum(row["state"] == "已接收" for row in receipts if row.get("required", True)),
        "required_count": sum(bool(row.get("required", True)) for row in receipts),
        "available_count": sum(row["state"] == "已接收" for row in receipts),
        "formal_evaluation_ready": all(row["state"] == "已接收" for row in receipts if row.get("required", True)),
        "step3_frozen_outcomes": {
            "schema_version": step3_frozen.get("schema_version"),
            "status": step3_frozen.get("status"),
            "source_provider": step3_frozen.get("source_provider"),
            "source_file": step3_frozen.get("source_file"),
        },
        "outcome_cards": cards,
        "outcome_portfolio": copy.deepcopy(outcome_portfolio),
        "internal_search": copy.deepcopy(internal_search_status),
        "evidence_adapter": {
            "schema_version": adapter.get("schema_version"),
            "status": adapter.get("status"),
            "source_channels": copy.deepcopy(adapter.get("source_channels") or []),
            "channel_status": copy.deepcopy(adapter.get("channel_status") or {}),
            "external_routing_audit": copy.deepcopy(adapter.get("external_routing_audit") or {}),
            "dimension_branch_counts": copy.deepcopy(adapter.get("dimension_branch_counts") or {}),
            "dimension_metric_counts": copy.deepcopy(adapter.get("dimension_metric_counts") or {}),
        },
    }

def build_indicator_product(
    workspace: dict[str, Any], run: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Build the current product: one outcome card, one direct D1-D7 evaluation surface."""
    contract = build_indicator_input_contract(workspace)
    prepared = build_prepared_evidence(workspace)
    supplied_run = run if isinstance(run, dict) else {}
    supplied_standard = str((supplied_run.get("run") or {}).get("standard_version") or "")
    run_compatible = bool(
        supplied_run.get("schema_version") == "indicator-evaluation.run.v5"
        and supplied_standard == EVALUATION_STANDARD_VERSION
    )
    current_run = supplied_run if run_compatible else {}
    evaluated_by_id = {
        str(row.get("outcome_id") or ""): row for row in current_run.get("outcomes") or []
    }
    adapter_packets = (workspace.get("evidence_adapter") or {}).get("outcome_packets") or {}
    outcomes = []
    for card in contract.get("outcome_cards") or []:
        outcome_id = str(card.get("outcome_id") or "")
        evaluated = copy.deepcopy(evaluated_by_id.get(outcome_id) or {})
        evaluated_dimensions = {
            str(row.get("dimension_id") or row.get("question_id") or ""): row
            for row in evaluated.get("dimensions") or []
        }
        packet = adapter_packets.get(outcome_id) or {}
        dimensions = []
        for definition in D_DIMENSIONS:
            dimension_id = str(definition["question_id"])
            source = copy.deepcopy(evaluated_dimensions.get(dimension_id) or {})
            evidence = ((packet.get("dimensions") or {}).get(dimension_id) or {})
            grade = copy.deepcopy(source.get("grade") or {"level": "未评定", "reason": "本轮记录未包含七维分级。", "source_ids": [], "gap_to_next": ""})
            if grade.get("level") == "待确认" and str(grade.get("gap_to_next") or "").startswith(("进入G", "升至G")):
                grade["gap_to_next"] = "先核对等级依据的来源及成果范围，再判断可达到的等级。"
            dimensions.append({
                **copy.deepcopy(definition),
                "dimension_id": dimension_id,
                "status": str(source.get("status") or "待评价"),
                "grade": grade,
                "branch_judgments": copy.deepcopy(source.get("branch_judgments") or []),
                "core_position": str(source.get("core_position") or "待判断") if dimension_id == "D1" else "",
                "conclusion": str(source.get("conclusion") or "尚未运行本维度评价。"),
                "expert_analysis": str(source.get("expert_analysis") or ""),
                "time_assessment": copy.deepcopy(source.get("time_assessment") or {}),
                "evidence_chain": copy.deepcopy(source.get("evidence_chain") or []),
                "key_facts": copy.deepcopy(source.get("key_facts") or []),
                "confirmation_requests": copy.deepcopy(source.get("confirmation_requests") or []),
                "ai_analysis": copy.deepcopy(source.get("ai_analysis") or {}),
                "basis": copy.deepcopy(source.get("basis") or []),
                "counterevidence": copy.deepcopy(source.get("counterevidence") or []),
                "professional_metric_use": copy.deepcopy(source.get("professional_metric_use") or []),
                "ai_attribution": str(source.get("ai_attribution") or ""),
                "missing_inputs": copy.deepcopy(source.get("missing_inputs") or []),
                "expert_question": str(source.get("expert_question") or ""),
                "evidence_confidence": str(source.get("evidence_confidence") or "--"),
                "judgment_confidence": str(source.get("judgment_confidence") or "--"),
                "confidence": str(source.get("judgment_confidence") or "--"),
                "professional_metrics": copy.deepcopy(evidence.get("professional_metrics") or []),
                "source_counts": copy.deepcopy(evidence.get("source_counts") or {}),
            })
        synthesis = copy.deepcopy(evaluated.get("synthesis") or {})
        outcomes.append({
            **copy.deepcopy(card),
            "dimensions": dimensions,
            "core_position": str(synthesis.get("core_position") or "待判断"),
            "innovation_conclusion": str(synthesis.get("innovation_conclusion") or "尚未评价。"),
            "influence_conclusion": str(synthesis.get("influence_conclusion") or "尚未评价。"),
            "overall_conclusion": str(synthesis.get("overall_conclusion") or "尚未完成逐成果D1-D7评价。"),
            "synthesis": synthesis,
            "impact_level": copy.deepcopy(synthesis.get("impact_level") or {"level": "未评定", "reason": "本轮记录未包含成果整体分级。", "gap_to_next": ""}),
            "milestone_context": copy.deepcopy(workspace.get("milestone_context") or {}),
            "adapter_counts": copy.deepcopy(packet.get("counts") or {}),
        })
    project_synthesis = copy.deepcopy(current_run.get("project_synthesis") or {
        "dimension_portfolio": {
            dimension_id: {"coverage": "本轮未体现", "depth": "本轮未体现", "concentration": "本轮未体现"}
            for dimension_id in DIMENSION_INPUT_CONTRACTS
        },
        "specific_layer": {"status": "本轮未体现", "conclusion": "尚未完成D1、D2和目标场景D5的归纳。", "basis": [], "limitations": []},
        "global_layer": {"status": "本轮未体现", "conclusion": "尚未完成D3、D4、D6、D7及跨场景D5的归纳。", "basis": [], "limitations": []},
        "system_collaboration": {"status": "本轮未体现", "conclusion": "尚未单独判断项目系统性与课题协同。", "evidence": [], "gaps": []},
        "overall_judgment": "尚未运行评价。",
        "leading_outcomes": [],
        "overclaimed_outcomes": [],
        "expert_questions": [],
        "management_advice": [],
    })
    project_synthesis.setdefault("scope_impact_level", {"level": "未评定", "reason": "本轮记录未包含评价范围整体分级。", "gap_to_next": "", "scope": str((workspace.get("project_profile") or {}).get("evaluation_scope") or "")})
    return {
        "schema_version": "indicator-standard-product.v7",
        "result_compatibility": {
            "status": "native" if run_compatible else (
                "incompatible_result_ignored" if supplied_run else "not_run"
            ),
            "source_standard_version": supplied_standard,
            "note": (
                "当前运行结果与逐成果D1-D7标准一致。" if run_compatible else
                "不兼容的评价结果不映射为当前结论。" if supplied_run else
                "尚未运行逐成果D1-D7评价。"
            ),
        },
        "grading_compatibility": {
            "status": "graded_contract" if (current_run.get("run") or {}).get("output_contract_version") == "structured-dimension-facts-with-grades.v3" else "legacy_ungraded",
            "source": "2026-09-17 七维分级与六级影响力对应建议",
            "note": "旧批次不从定性状态推算等级；未执行分级判断时显示未评定。",
        },
        "project_profile": copy.deepcopy(workspace.get("project_profile") or {}),
        "milestone_context": copy.deepcopy(workspace.get("milestone_context") or {}),
        "input_contract": contract,
        "prepared_evidence": prepared,
        "evaluation_standard": {
            "version": EVALUATION_STANDARD_VERSION,
            "classification_policy": copy.deepcopy(CLASSIFICATION_POLICY),
            "project_aggregation_policy": copy.deepcopy(PROJECT_AGGREGATION_POLICY),
            "evidence_organization": copy.deepcopy(EVIDENCE_ORGANIZATION),
            "collaboration_policy": copy.deepcopy(COLLABORATION_POLICY),
            "review_policy": copy.deepcopy(REVIEW_POLICY),
            "dimension_observables": copy.deepcopy(DIMENSION_OBSERVABLES),
            "agent_execution_protocol": copy.deepcopy(AGENT_EXECUTION_PROTOCOL),
            "dimensions": copy.deepcopy(D_DIMENSIONS),
            "outcome_questions": copy.deepcopy(D_DIMENSIONS),
            "branch_indicators": copy.deepcopy(D_BRANCH_INDICATORS),
            "indicator_tree": build_indicator_tree(workspace, D_DIMENSIONS, D_BRANCH_INDICATORS, prepared),
            "dimension_statuses": copy.deepcopy(DIMENSION_STATUSES),
            "g_level_criteria": copy.deepcopy(G_LEVEL_CRITERIA),
            "l_level_criteria": copy.deepcopy(L_LEVEL_CRITERIA),
            "dimension_input_contracts": copy.deepcopy(DIMENSION_INPUT_CONTRACTS),
            "upstream_component_contracts": copy.deepcopy(UPSTREAM_COMPONENT_CONTRACTS),
            "layer_summary_method": copy.deepcopy(LAYER_SUMMARY_METHOD),
            "professional_metric_policy": "三个项目共用21个D1-D7分支；L2-L4只作分支事实来源，正式链不读取历史等级、不独立评分、不按数量赋权。",
            "ai_contribution_policy": "AI归因贯穿D1、D2和D5的相应事实链，不作为等权独立分数，并与数据、算力、自动化、设备、领域知识、传统方法和人工贡献区分。",
            "scoring_policy": "直接形成逐维度定性判断，并分别给出G1-G5；整体影响给出L1-L6。不计算平均分或总分，等级须有关键事实与边界。",
            "evidence_time_roles": copy.deepcopy(EVIDENCE_TIME_ROLES),
            "hard_rules": copy.deepcopy(HARD_RULES),
        },
        "outcomes": outcomes,
        "project_synthesis": project_synthesis,
        "evaluation_state": (REVIEW_POLICY["evaluation_state"] if current_run.get("formal") else "系统评价未完成 · 专家校准前") if run_compatible else "尚未运行当前标准评价",
        "evidence_dossier": evidence_dossier(outcomes, project_synthesis),
        "evidence_adapter": {
            "schema_version": (workspace.get("evidence_adapter") or {}).get("schema_version"),
            "status": (workspace.get("evidence_adapter") or {}).get("status"),
            "source_channels": copy.deepcopy((workspace.get("evidence_adapter") or {}).get("source_channels") or []),
            "channel_status": copy.deepcopy((workspace.get("evidence_adapter") or {}).get("channel_status") or {}),
            "external_routing_audit": copy.deepcopy((workspace.get("evidence_adapter") or {}).get("external_routing_audit") or {}),
            "dimension_branch_counts": copy.deepcopy((workspace.get("evidence_adapter") or {}).get("dimension_branch_counts") or {}),
            "dimension_metric_counts": copy.deepcopy((workspace.get("evidence_adapter") or {}).get("dimension_metric_counts") or {}),
        },
        "run": copy.deepcopy(current_run.get("run") or {}),
        "llm_trace": copy.deepcopy(current_run.get("llm_trace") or {"summary": {"call_count": 0}, "calls": []}),
    }


def _dimension_output_error(data: dict[str, Any], dimension_id: str) -> str:
    branches = data.get('branch_judgments')
    if (not isinstance(branches, list) or len(branches) != 3
            or any(not isinstance(row, dict) for row in branches)
            or {row.get('branch_id') for row in branches} != {f'{dimension_id}.{i}' for i in range(1, 4)}):
        return '模型输出未完整提供规定的三个分支，需要重试生成；这不是上游材料缺口。'
    for field in ('key_facts', 'evidence_chain'):
        rows = data.get(field, [])
        if not isinstance(rows, list) or any(
            not isinstance(row, dict) or not isinstance(row.get('fact'), str) or not row['fact'].strip()
            or not isinstance(row.get('source_ids'), list) or not row['source_ids']
            or not isinstance(row.get('outcome_ids'), list) or not row['outcome_ids']
            for row in rows
        ):
            return '模型输出的事实记录缺少具体事实、来源编号或成果范围，需要重试生成；这不是上游材料缺口。'
    return ''


class IndicatorEvaluationPipeline:
    """Indicator-group-only evaluation: consume upstream packets and issue judgments."""

    def __init__(self, settings: Any, llm: Any):
        self.settings = settings
        self.traced = llm if isinstance(llm, TracingLLMClient) else TracingLLMClient(llm)

    def run(
        self,
        workspace: dict[str, Any],
        *,
        model: str | None = None,
        timeout: float = 240.0,
        parallelism: int = 4,
    ) -> dict[str, Any]:
        contract = build_indicator_input_contract(workspace)
        cards = contract.get("outcome_cards") or []
        if not cards:
            raise ValueError("上游尚未提供Step 3冻结成果，指标组不能开始评价。")
        if not contract.get("formal_evaluation_ready"):
            missing = [
                str(row.get("name") or row.get("input_id") or "")
                for row in contract.get("receipts") or []
                if row.get("required", True) and row.get("state") != "已接收"
            ]
            raise ValueError(f"正式输入契约尚未闭合：{'、'.join(missing)}")
        units = [(card, dimension) for card in cards for dimension in D_DIMENSIONS]
        dimensions_by_outcome: dict[str, list[dict[str, Any]]] = {
            str(card.get("outcome_id")): [] for card in cards
        }
        with ThreadPoolExecutor(max_workers=max(1, min(int(parallelism), 8))) as pool:
            futures = {
                pool.submit(
                    self._judge_d_dimension, workspace, card, dimension, model, timeout,
                ): (card, dimension)
                for card, dimension in units
            }
            for future in as_completed(futures):
                card, dimension = futures[future]
                try:
                    judgment = future.result()
                except Exception as exc:
                    judgment = _failed_d_judgment(dimension, f"{type(exc).__name__}: {exc}")
                dimensions_by_outcome[str(card.get("outcome_id"))].append(judgment)

        # A cluster-level RPM limit can exhaust the transport retries of one
        # logical unit even while neighboring units succeed.  Retry only those
        # failed logical units before any outcome/project synthesis is allowed
        # to consume their placeholders.
        for _retry_round in range(2):
            pending = []
            for card, dimension in units:
                outcome_id = str(card.get("outcome_id"))
                dimension_id = str(dimension.get("question_id"))
                current = next(
                    (
                        row
                        for row in dimensions_by_outcome[outcome_id]
                        if str(row.get("dimension_id")) == dimension_id
                    ),
                    None,
                )
                if current is not None and _is_failed_d_judgment(current):
                    pending.append((card, dimension))
            if not pending:
                break
            with ThreadPoolExecutor(max_workers=max(1, min(int(parallelism), len(pending)))) as pool:
                futures = {
                    pool.submit(
                        self._judge_d_dimension, workspace, card, dimension, model, timeout,
                    ): (card, dimension)
                    for card, dimension in pending
                }
                for future in as_completed(futures):
                    card, dimension = futures[future]
                    try:
                        judgment = future.result()
                    except Exception as exc:
                        judgment = _failed_d_judgment(dimension, f"{type(exc).__name__}: {exc}")
                    outcome_id = str(card.get("outcome_id"))
                    dimension_id = str(dimension.get("question_id"))
                    dimensions_by_outcome[outcome_id] = [
                        judgment if str(row.get("dimension_id")) == dimension_id else row
                        for row in dimensions_by_outcome[outcome_id]
                    ]

        partial_outcomes = []
        for card in cards:
            dimensions = sorted(
                dimensions_by_outcome[str(card.get("outcome_id"))],
                key=lambda row: int(str(row.get("dimension_id") or "D99").removeprefix("D")),
            )
            partial_outcomes.append({
                "outcome_id": card.get("outcome_id"),
                "title": card.get("title"),
                "child_outcomes": copy.deepcopy(card.get("child_outcomes") or []),
                "problem_ids": copy.deepcopy(card.get("problem_ids") or []),
                "dimensions": dimensions,
            })

        synthesis_by_outcome: dict[str, dict[str, Any]] = {}
        with ThreadPoolExecutor(max_workers=max(1, min(int(parallelism), 8))) as pool:
            futures = {
                pool.submit(self._synthesize_d_outcome, row, model, timeout): row
                for row in partial_outcomes
            }
            for future in as_completed(futures):
                row = futures[future]
                outcome_id = str(row.get("outcome_id"))
                try:
                    synthesis_by_outcome[outcome_id] = future.result()
                except Exception as exc:
                    synthesis_by_outcome[outcome_id] = _failed_d_outcome_synthesis(
                        f"{type(exc).__name__}: {exc}"
                    )

        outcomes = []
        for row in partial_outcomes:
            synthesis = synthesis_by_outcome[str(row.get("outcome_id"))]
            outcomes.append({
                **row,
                "core_position": synthesis.get("core_position") or "待判断",
                "innovation_conclusion": synthesis.get("innovation_conclusion") or "",
                "influence_conclusion": synthesis.get("influence_conclusion") or "",
                "overall_conclusion": synthesis.get("overall_conclusion") or "综合分析未完成。",
                "synthesis": synthesis,
            })

        try:
            project_synthesis = self._synthesize_d_project(workspace, outcomes, model, timeout)
        except Exception as exc:
            project_synthesis = _failed_d_project_synthesis(f"{type(exc).__name__}: {exc}")

        trace = self.traced.snapshot()
        completed = int(trace.get("summary", {}).get("successful_call_count") or 0)
        expected = len(units) + len(cards) + 1
        return {
            "schema_version": "indicator-evaluation.run.v5",
            "run": {
                "model": model or getattr(self.settings, "glm_model", ""),
                "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
                "expected_call_count": expected,
                "completed_call_count": completed,
                "evaluation_unit": "outcome_direct_d1_d7",
                "call_formula": "每成果7次D维度直接评价 + 1次成果观点综合；全项目1次特定层/全局层/协同归纳",
                "formal_input_ready": contract["formal_evaluation_ready"],
                "standard_version": EVALUATION_STANDARD_VERSION,
                "rubric_version": RUBRIC_VERSION,
                "grading_standard": GRADING_VERSION,
                "output_contract_version": "structured-dimension-facts-with-grades.v3",
            },
            "input_contract": contract,
            "milestone_context": copy.deepcopy(workspace.get("milestone_context") or {}),
            "outcomes": outcomes,
            "project_synthesis": project_synthesis,
            "formal": bool(contract.get("formal_evaluation_ready") and completed == expected),
            "llm_trace": trace,
        }

    def _judge_d_dimension(self, workspace, card, dimension, model, timeout):
        dimension_id = str(dimension.get("question_id") or "")
        pid = (workspace.get('project_profile') or {}).get('project_id','')
        expected = MATERIAL_REVIEW.get('outcome_contracts',{}).get(pid,{}).get(card.get('outcome_id'))
        criteria_scope = card.get('outcome_id') if expected and {key:card.get(key) for key in ('title','child_outcome_ids')} == expected else ''
        payload = {
            "project": workspace.get("project_profile") or {},
            "milestone_context": workspace.get("milestone_context") or {},
            "outcome_card": card,
            "dimension": dimension,
            "active_indicator_criteria": criteria_for_dimension(pid, dimension_id, criteria_scope),
            "active_indicator_policy": copy.deepcopy(POLICY),
            "agent_execution_protocol": copy.deepcopy(AGENT_EXECUTION_PROTOCOL),
            "dimension_input_contract": copy.deepcopy(DIMENSION_INPUT_CONTRACTS[dimension_id]),
            "grade_criteria": {f"G{i}": label for i, label in enumerate(G_LEVEL_CRITERIA[dimension_id], 1)},
            "upstream_component_contract": copy.deepcopy(UPSTREAM_COMPONENT_CONTRACTS[dimension_id]),
            "dimension_statuses": DIMENSION_STATUSES,
            "adapted_evidence": _outcome_evidence(workspace, card, dimension_id),
            "judgment_boundaries": HARD_RULES,
            "classification_policy": CLASSIFICATION_POLICY,
            "evidence_organization": EVIDENCE_ORGANIZATION,
            "observables": DIMENSION_OBSERVABLES[dimension_id],
            "review_policy": REVIEW_POLICY,
        }
        payload = apply_current_dimension_scope(_independent_materials(payload))
        result = self.traced.chat_json(
            D_DIMENSION_SYSTEM_PROMPT,
            json.dumps(payload, ensure_ascii=False),
            model=model, temperature=0.2, max_attempts=4, timeout=timeout,
            _trace_stage="D01_outcome_dimension",
            _trace_unit=f"{card.get('outcome_id')}:{dimension_id}",
        )
        if not result.ok or not isinstance(result.data, dict):
            return _failed_d_judgment(dimension, result.error or "模型未返回可解析JSON。")
        schema_error = _dimension_output_error(result.data, dimension_id)
        if schema_error:
            self.traced.reject_response(f"{card.get('outcome_id')}:{dimension_id}", schema_error)
            return _failed_d_judgment(dimension, schema_error)
        judgment = _normalize_d_judgment(dimension, result.data)
        _validate_fact_scope(judgment, payload["adapted_evidence"], card)
        if dimension_id == 'D1' and not card.get('problem_ids'):
            for branch in judgment['branch_judgments']:
                if branch['branch_id'] == 'D1.1':
                    branch['status'] = '本轮未体现'
                    branch['conclusion'] = '尚缺主要成果与核心问题的明确对应关系，不能认定核心任务已解决。'
            if judgment['status'] == '明确成立':
                judgment['status'] = '部分成立'
                judgment['conclusion'] = '核心问题对应关系尚缺；性能或边界材料不能替代核心任务解决判断。'
            grade = judgment.get('grade') or {}
            if str(grade.get('level') or '').startswith('G'):
                grade['reason'] = f"{grade.get('reason', '')}；成果与核心问题的显式映射仍待补齐，不能据此认定核心任务已解决。"
                grade['gap_to_next'] = f"补齐成果与核心问题的映射及同口径验证；{grade.get('gap_to_next', '')}"
        return judgment


    def _synthesize_d_outcome(self, outcome, model, timeout):
        result = self.traced.chat_json(
            OUTCOME_SYNTHESIS_SYSTEM_PROMPT,
            json.dumps({**outcome, "classification_policy": CLASSIFICATION_POLICY, "impact_level_criteria": L_LEVEL_CRITERIA}, ensure_ascii=False),
            model=model, temperature=0.0, max_attempts=4, timeout=timeout,
            _trace_stage="D02_outcome_synthesis",
            _trace_unit=str(outcome.get("outcome_id") or ""),
        )
        if not result.ok or not isinstance(result.data, dict):
            return _failed_d_outcome_synthesis(result.error or "模型未返回可解析JSON。")
        synthesis = _normalize_d_outcome_synthesis(result.data)
        _validate_synthesis_sources(synthesis, outcome.get("dimensions") or [])
        child_ids = {str(row.get("outcome_id")) for row in outcome.get("child_outcomes") or []}
        unknown = set(synthesis["evaluated_child_ids"]) - child_ids
        if unknown:
            synthesis["evaluated_child_ids"] = [oid for oid in synthesis["evaluated_child_ids"] if oid in child_ids]
            synthesis["scope_limitations"].append("模型引用了未在冻结输入中的子成果，需上游确认评价粒度。")
        innovation = [row for row in outcome.get("dimensions") or [] if row.get("dimension_id") in {"D1", "D2"}]
        if synthesis["core_position"] == "核心成果" and (
            unknown or not outcome.get("problem_ids") or len(innovation) != 2
            or any(row.get("status") not in {"明确成立", "部分成立"} or not (row.get("basis") or row.get("key_facts") or row.get("evidence_chain")) for row in innovation)
        ):
            synthesis["core_position"] = "待判断"
            synthesis["classification_reason"] = "核心问题显式映射、创新依据或冻结子成果范围尚未闭合，暂不能确认核心成果。"
        return synthesis

    def _synthesize_d_project(self, workspace, outcomes, model, timeout):
        payload = {
            "project": workspace.get("project_profile") or {},
            "outcomes": outcomes,
            "layer_summary_method": LAYER_SUMMARY_METHOD,
            "milestone_context": workspace.get("milestone_context") or {},
            "project_aggregation_policy": PROJECT_AGGREGATION_POLICY,
            "impact_level_criteria": L_LEVEL_CRITERIA,
            "collaboration_policy": COLLABORATION_POLICY,
            "review_policy": REVIEW_POLICY,
            "system_collaboration_evidence": {
                "result_group_project_materials": _independent_materials(
                    (workspace.get("evidence_repository") or {}).get("internal_achievement") or {}
                ),
                "unmatched_internal_search": (
                    (workspace.get("evidence_adapter") or {}).get("unmatched") or {}
                ).get("internal_search_groups") or [],
            },
        }
        result = self.traced.chat_json(
            PROJECT_SYNTHESIS_SYSTEM_PROMPT,
            json.dumps(payload, ensure_ascii=False),
            model=model, temperature=0.0, max_attempts=4, timeout=timeout,
            _trace_stage="D03_project_synthesis",
            _trace_unit="PROJECT_D1_D7_SYNTHESIS",
        )
        if not result.ok or not isinstance(result.data, dict):
            return _failed_d_project_synthesis(result.error or "模型未返回可解析JSON。")
        project_data = copy.deepcopy(result.data)
        collaboration = project_data.get("system_collaboration")
        if isinstance(collaboration, dict):
            sources = _source_identifiers(payload["system_collaboration_evidence"])
            collaboration["design_basis"] = [sid for sid in text_list(collaboration.get("design_basis")) if sid in sources]
            for chain in collaboration.get("chains") or []:
                if isinstance(chain, dict):
                    for key in ("source_ids", "invocation_source_ids", "feedback_source_ids", "repeat_source_ids"):
                        chain[key] = [sid for sid in text_list(chain.get(key)) if sid in sources]
        synthesis = _normalize_d_project_synthesis(project_data)
        synthesis["scope_impact_level"]["scope"] = str((workspace.get("project_profile") or {}).get("evaluation_scope") or "")
        scope_level = synthesis["scope_impact_level"]
        if str(scope_level.get("level") or "").startswith("L") and not set(scope_level.get("source_ids") or []) <= _source_identifiers(outcomes):
            scope_level["level"] = "待确认"
            scope_level["reason"] = "整体等级所引来源未在本轮成果中闭合。"
        valid_ids = {str(row.get("outcome_id")) for row in outcomes}
        all_cards = {str(row.get("outcome_id")): row for row in outcomes}
        for dimension_id, portfolio in synthesis["dimension_portfolio"].items():
            portfolio["included_outcomes"] = [row for row in portfolio["included_outcomes"] if row["outcome_id"] in valid_ids]
            allowed_facts = [fact for outcome in outcomes for dimension in outcome.get("dimensions") or []
                             if dimension.get("dimension_id") == dimension_id
                             for fact in [*(dimension.get("key_facts") or []), *(dimension.get("evidence_chain") or [])]]
            # Project synthesis can select and explain existing facts; it cannot
            # silently add a new source or turn a child fact into project scale.
            scoped_card = {"outcome_id": "", "child_outcomes": [
                {"outcome_id": oid} for oid in valid_ids | {str(child.get("outcome_id")) for row in all_cards.values() for child in row.get("child_outcomes") or []}
            ]}
            _validate_fact_scope(portfolio, allowed_facts, scoped_card)
        return synthesis

def _validate_synthesis_sources(synthesis, dimensions):
    sources_by_dimension = {row.get("dimension_id"): _source_identifiers({
        "basis": row.get("basis") or [],
        "facts": [fact for fact in [*(row.get("key_facts") or []), *(row.get("evidence_chain") or [])]
                  if not str(fact.get("source_verification") or "").startswith("待核实")],
    }) for row in dimensions}
    level = synthesis.get("impact_level") or {}
    available_sources = set().union(*sources_by_dimension.values()) if sources_by_dimension else set()
    if str(level.get("level") or "").startswith("L") and not set(level.get("source_ids") or []) <= available_sources:
        level["level"] = "待确认"
        level["reason"] = "成果等级所引来源未在本轮维度判断中闭合。"
    accepted = []
    for row in synthesis.get("decisive_evidence") or []:
        if not isinstance(row, dict):
            continue
        dims, cited = set(text_list(row.get("dimension_ids"))), set(text_list(row.get("source_ids")))
        if dims and dims <= sources_by_dimension.keys() and cited and cited <= set().union(*(sources_by_dimension[d] for d in dims)):
            accepted.append(row)
    if len(accepted) != len(synthesis.get("decisive_evidence") or []):
        synthesis["scope_limitations"].append("综合判断引用了对应维度中未确认来源的材料，需补齐可追溯依据。")
        synthesis["core_position"] = "待判断"
        synthesis["classification_reason"] = "综合判断的决定性依据尚未闭合，暂不确认成果定位。"
        synthesis["overall_conclusion"] = "综合判断的来源范围尚未闭合，结论本轮未体现。"
    synthesis["decisive_evidence"] = accepted


def _outcome_evidence(
    workspace: dict[str, Any], card: dict[str, Any], dimension_id: str
) -> dict[str, Any]:
    packet = (
        ((workspace.get("evidence_adapter") or {}).get("outcome_packets") or {}).get(
            str(card.get("outcome_id") or "")
        )
        or {}
    )
    dimension = copy.deepcopy((packet.get("dimensions") or {}).get(dimension_id) or {})
    return {
        "schema_version": "adapted-outcome-dimension-evidence.v1",
        "outcome_id": str(card.get("outcome_id") or ""),
        "dimension_id": dimension_id,
        "outcome_card_source": copy.deepcopy(packet.get("source_card") or {}),
        **dimension,
        "adapter_governance": copy.deepcopy(
            (workspace.get("evidence_adapter") or {}).get("governance") or {}
        ),
    }


def _independent_materials(value: Any) -> Any:
    """Keep source facts while withholding historical expert/role judgments."""
    excluded = {"professional_questions", "expert_questions", "expert_feedback", "expert_opinions",
                "reviewer_comments", "expert_consensus", "classification_status", "system_classification"}
    if isinstance(value, dict):
        return {key: _independent_materials(item) for key, item in value.items() if key not in excluded}
    if isinstance(value, list):
        return [_independent_materials(item) for item in value]
    return value


def _source_identifiers(value: Any) -> set[str]:
    ids: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            if key in {"source_id", "evidence_id", "claim_id", "contribution_id", "component_id"} and isinstance(item, str):
                ids.add(item)
            elif key in {"source_ids", "source_record_ids", "core_evidence_ids", "decisive_source_ids"}:
                ids.update(text_list(item))
            elif isinstance(item, (dict, list)):
                ids.update(_source_identifiers(item))
    elif isinstance(value, list):
        for item in value:
            ids.update(_source_identifiers(item))
    return ids


def _validate_fact_scope(judgment: dict[str, Any], evidence: Any, card: dict[str, Any]) -> None:
    allowed_sources = _source_identifiers(evidence)
    allowed_outcomes = {str(card.get("outcome_id") or ""), *text_list(card.get("child_outcome_ids")),
                        *(str(child.get("outcome_id")) for child in card.get("child_outcomes") or [])} - {""}
    invalid = False
    for field in ('basis', 'counterevidence'):
        valid_rows = []
        for row in judgment.get(field) or []:
            if row.get('source_id') and row['source_id'] in allowed_sources:
                valid_rows.append(row)
            else:
                invalid = True
                judgment.setdefault('unverified_references', []).append({**row, 'reason': '来源不在本次材料中，不能作为已追溯依据。'})
        if field in judgment:
            judgment[field] = valid_rows
    for branch in judgment.get('branch_judgments') or []:
        cited = set(branch.get('decisive_source_ids') or [])
        if (cited and not cited <= allowed_sources) or (branch.get('status') in {'明确成立','部分成立','尚未形成'} and not cited):
            invalid = True
            branch['decisive_source_ids'] = [sid for sid in branch.get('decisive_source_ids') or [] if sid in allowed_sources]
            branch['status'] = '本轮未体现'
            branch['conclusion'] = '该分支尚缺可追溯的直接依据，不能形成确定判断。'
    for row in [*(judgment.get("key_facts") or []), *(judgment.get("evidence_chain") or [])]:
        cited = set(row.get("source_ids") or [])
        targets = set(row.get("outcome_ids") or [])
        if not cited or not cited <= allowed_sources or not targets or not targets <= allowed_outcomes:
            invalid = True
            row["source_verification"] = "待核实：来源编号或成果范围未在本次输入中闭合"
            row["source_ids"] = [sid for sid in row.get("source_ids") or [] if sid in allowed_sources]
            row["outcome_ids"] = [oid for oid in row.get("outcome_ids") or [] if oid in allowed_outcomes]
            row["source_type"], row["effect"] = "待核实", "待分类"
            row["does_not_prove"] = "来源或成果范围待核实，当前不能作为已确认依据。"
            if "quantity" in row:
                row["quantity"]["value"], row["quantity"]["status"] = None, "待核实"
        else:
            row["source_verification"] = "编号可追溯；事实内容仍按评价规则核验"
    grade = judgment.get("grade") or {}
    if str(grade.get("level") or "").startswith("G") and not set(grade.get("source_ids") or []) <= allowed_sources:
        grade["level"] = "待确认"
        grade["reason"] = "等级所引来源未在本轮材料中闭合。"
        grade["gap_to_next"] = "先核对等级依据的来源及成果范围，再判断可达到的等级。"
        invalid = True
    if invalid:
        judgment.setdefault("confirmation_requests", []).append({
            "issue": "关键事实的来源或成果适用范围未闭合", "method": "项目方补充材料", "owner": "项目方",
            "expected_evidence": "提供可追溯原文及具体成果对应关系", "affected_judgment": "事实支持范围",
            "changes_judgment": True, "professional_dispute": False,
        })
        judgment["conclusion"] = "关键事实的来源或成果范围尚未闭合，当前判断本轮未体现。"
        if judgment.get("status") in {"明确成立", "部分成立", "尚未形成"}:
            judgment["status"] = "本轮未体现"


def _collaboration_chains(value: Any) -> list[dict[str, Any]]:
    return [{**{key: str(row.get(key) or "") for key in ("provider", "consumer", "artifact", "task", "result")},
             **{key: text_list(row.get(key)) for key in ("source_ids", "invocation_source_ids", "feedback_source_ids", "repeat_source_ids")}}
            for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _collaboration_status(collaboration: dict[str, Any]) -> tuple[str, bool]:
    requested = str(collaboration.get("status") or "本轮未体现")
    if requested not in COLLABORATION_STATES or requested == "本轮未体现":
        return "本轮未体现", requested != "本轮未体现"
    chains = _collaboration_chains(collaboration.get("chains"))
    actual = [row for row in chains if all(row.get(key) for key in ("provider", "consumer", "artifact", "task", "result", "invocation_source_ids"))
              and row["provider"] != row["consumer"]]
    ceiling = 0 if collaboration.get("design_basis") else -1
    if actual:
        ceiling = 1
        linked = any(left["consumer"] == right["provider"] and left["task"] == right["task"] for left in actual for right in actual if left is not right)
        if linked:
            ceiling = 2
            if any(row["feedback_source_ids"] for row in actual):
                ceiling = 3
                if any(row["repeat_source_ids"] and row["feedback_source_ids"] for row in actual):
                    ceiling = 4
    requested_index = COLLABORATION_STATES.index(requested)
    if requested_index <= ceiling:
        return requested, False
    return (COLLABORATION_STATES[ceiling] if ceiling >= 0 else "本轮未体现"), True


def _evidence_chain(value: Any) -> list[dict[str, Any]]:
    rows = []
    for item in value or []:
        if not isinstance(item, dict):
            continue
        reliability = str(item.get("reliability") or "中")
        rows.append({
            **(normalize_facts([item], limit=1)[0] if item.get("fact") else {}),
            "claim": str(item.get("claim") or "")[:800],
            "source_ids": [str(row)[:160] for row in item.get("source_ids") or []],
            "time_role": str(item.get("time_role") or "")[:80],
            "analysis": str(item.get("analysis") or "")[:1600],
            "reliability": reliability if reliability in {"高", "中", "低"} else "中",
        })
    return rows[:8]

def _confidence(value: Any, fallback: str = "低") -> str:
    text = str(value or "").strip()
    aliases = {"high": "高", "medium": "中", "low": "低", "强": "高", "较强": "中"}
    text = aliases.get(text.lower(), aliases.get(text, text))
    return text if text in {"高", "中", "低"} else fallback


def _normalize_level(value: Any, prefix: str, *, require_sources: bool = False) -> dict[str, Any]:
    row = value if isinstance(value, dict) else {}
    allowed = {f"{prefix}{i}" for i in range(1, 6 if prefix == "G" else 7)}
    level = str(row.get("level") or "待确认")
    reason = str(row.get("reason") or "").strip()
    source_ids = text_list(row.get("source_ids"))
    if level not in allowed or not reason or (require_sources and not source_ids and level != "G1"):
        level = "待确认"
        reason = reason or "缺少可追溯的等级依据。"
    return {"level": level, "reason": reason, "gap_to_next": str(row.get("gap_to_next") or ""), "source_ids": source_ids}

def _fact_rows(value: Any) -> list[dict[str, str]]:
    rows = []
    for item in value or []:
        if isinstance(item, dict):
            rows.append({"source_id": str(item.get("source_id") or ""), "fact": str(item.get("fact") or "")[:500]})
        elif item:
            rows.append({"source_id": "", "fact": str(item)[:500]})
    return rows


def _receipt(
    key: str,
    name: str,
    provider: str,
    available: bool,
    count: int,
    state: str | None = None,
    *,
    required: bool = True,
):
    return {
        "input_id": key,
        "name": name,
        "provider": provider,
        "state": state or ("已接收" if available else "缺失"),
        "count": int(count or 0),
        "required": required,
    }

def _normalize_d_judgment(
    dimension: dict[str, Any], value: dict[str, Any]
) -> dict[str, Any]:
    allowed_statuses = {row["status"] for row in DIMENSION_STATUSES}
    status = str(value.get("status") or "本轮未体现")
    if status not in allowed_statuses:
        status = "本轮未体现"
    dimension_id = str(dimension.get("question_id") or dimension.get("metric_id") or "")
    positions = set(OUTCOME_POSITIONS)
    core_position = str(value.get("core_position") or "待判断")
    if dimension_id != "D1" or core_position not in positions:
        core_position = "待判断" if dimension_id == "D1" else ""
    branch_definitions = [
        row for row in D_BRANCH_INDICATORS if row.get("dimension_id") == dimension_id
    ]
    supplied_branches = {
        str(row.get("branch_id") or ""): row
        for row in value.get("branch_judgments") or []
        if isinstance(row, dict)
    }
    branch_judgments = []
    for definition in branch_definitions:
        branch_id = str(definition.get("branch_id") or "")
        supplied = supplied_branches.get(branch_id) or {}
        branch_status = str(supplied.get("status") or "本轮未体现")
        if branch_status not in allowed_statuses:
            branch_status = "本轮未体现"
        branch_judgments.append({
            "branch_id": branch_id,
            "name": str(definition.get("name") or ""),
            "status": branch_status,
            "conclusion": str(supplied.get("conclusion") or "该原子判断尚本轮未体现。")[:500],
            "decisive_source_ids": [str(row)[:160] for row in supplied.get("decisive_source_ids") or []][:8],
        })
    return {
        **copy.deepcopy(dimension),
        "dimension_id": dimension_id,
        "status": status,
        "grade": _normalize_level(value.get("grade"), "G", require_sources=True),
        "branch_judgments": branch_judgments,
        "core_position": core_position,
        "conclusion": str(value.get("conclusion") or "当前证据不足，暂本轮未体现。")[:500],
        "expert_analysis": str(value.get("expert_analysis") or ""),
        "time_assessment": copy.deepcopy(value.get("time_assessment") or {}),
        "evidence_chain": _evidence_chain(value.get("evidence_chain")),
        "key_facts": normalize_facts(value.get("key_facts")),
        "confirmation_requests": normalize_requests(value.get("confirmation_requests")),
        "ai_analysis": normalize_ai(value.get("ai_analysis")) if dimension_id in {"D1", "D2", "D5"} else {},
        "basis": _fact_rows(value.get("basis")),
        "counterevidence": _fact_rows(value.get("counterevidence")),
        "professional_metric_use": [
            {
                "metric_id": str(row.get("metric_id") or ""),
                "role": str(row.get("role") or ""),
            }
            for row in value.get("professional_metric_use") or []
            if isinstance(row, dict)
        ],
        "ai_attribution": str(value.get("ai_attribution") or ""),
        "missing_inputs": [str(row) for row in value.get("missing_inputs") or []],
        "expert_question": str(value.get("expert_question") or ""),
        "evidence_confidence": _confidence(value.get("evidence_confidence")),
        "judgment_confidence": _confidence(value.get("judgment_confidence")),
        "confidence": _confidence(value.get("judgment_confidence")),
    }


def _failed_d_judgment(dimension: dict[str, Any], error: str) -> dict[str, Any]:
    return _normalize_d_judgment(
        dimension,
        {
            "status": "本轮未体现",
            "conclusion": "本维度评价调用未完成，不能形成事实判断。",
            "expert_analysis": error,
            "missing_inputs": ["重新运行本维度评价并保留完整调用记录。"],
            "evidence_confidence": "低",
            "judgment_confidence": "低",
        },
    )


def _is_failed_d_judgment(value: dict[str, Any]) -> bool:
    return str(value.get("conclusion") or "") == "本维度评价调用未完成，不能形成事实判断。"


def _normalize_d_outcome_synthesis(value: dict[str, Any]) -> dict[str, Any]:
    positions = set(OUTCOME_POSITIONS)
    position = str(value.get("core_position") or "待判断")
    if position not in positions:
        position = "待判断"
    return {
        "core_position": position,
        "classification_reason": str(value.get("classification_reason") or "尚未形成系统归类依据。"),
        "evaluated_child_ids": text_list(value.get("evaluated_child_ids")),
        "scope_limitations": text_list(value.get("scope_limitations")),
        "confirmed": str(value.get("confirmed") or "待评价"),
        "unconfirmed": str(value.get("unconfirmed") or "待评价"),
        "innovation_conclusion": str(value.get("innovation_conclusion") or ""),
        "influence_conclusion": str(value.get("influence_conclusion") or ""),
        "overall_conclusion": str(value.get("overall_conclusion") or ""),
        "impact_level": _normalize_level(value.get("impact_level"), "L", require_sources=True),
        "decisive_evidence": copy.deepcopy(value.get("decisive_evidence") or []),
        "main_limitations": [str(row) for row in value.get("main_limitations") or []][:8],
        "expert_questions": [str(row) for row in value.get("expert_questions") or []][:3],
        "next_evidence_requests": [str(row) for row in value.get("next_evidence_requests") or []][:5],
        "evidence_confidence": _confidence(value.get("evidence_confidence")),
        "judgment_confidence": _confidence(value.get("judgment_confidence")),
        "confidence": _confidence(value.get("judgment_confidence")),
    }


def _failed_d_outcome_synthesis(error: str) -> dict[str, Any]:
    return {
        **_normalize_d_outcome_synthesis({"core_position": "待判断"}),
        "overall_conclusion": "成果综合分析调用未完成。",
        "main_limitations": [error],
    }


def _normalize_d_project_synthesis(value: dict[str, Any]) -> dict[str, Any]:
    layer_statuses = {"强", "较强", "初步形成", "尚未形成", "本轮未体现"}
    collaboration_statuses = set(COLLABORATION_STATES)

    def layer(key: str) -> dict[str, Any]:
        source = value.get(key) if isinstance(value.get(key), dict) else {}
        status = str(source.get("status") or "本轮未体现")
        return {
            "status": status if status in layer_statuses else "本轮未体现",
            "conclusion": str(source.get("conclusion") or ""),
            "basis": [str(row) for row in source.get("basis") or []],
            "limitations": [str(row) for row in source.get("limitations") or []],
        }

    collaboration = value.get("system_collaboration") if isinstance(value.get("system_collaboration"), dict) else {}
    collaboration_status, collaboration_downgraded = _collaboration_status(collaboration)
    supplied_portfolio = value.get("dimension_portfolio") if isinstance(value.get("dimension_portfolio"), dict) else {}
    dimension_portfolio = {}
    for dimension_id in DIMENSION_INPUT_CONTRACTS:
        row = supplied_portfolio.get(dimension_id) if isinstance(supplied_portfolio.get(dimension_id), dict) else {}
        dimension_portfolio[dimension_id] = {
            "conclusion": str(row.get("conclusion") or "待评价"),
            "included_outcomes": [{"outcome_id": str(item.get("outcome_id") or ""), "reason": str(item.get("reason") or "")}
                                  for item in row.get("included_outcomes") or [] if isinstance(item, dict)],
            "key_facts": normalize_facts(row.get("key_facts")),
            "confirmation_requests": normalize_requests(row.get("confirmation_requests")),
            "coverage": str(row.get("coverage") or "本轮未体现"),
            "depth": str(row.get("depth") or "本轮未体现"),
            "concentration": str(row.get("concentration") or "本轮未体现"),
        }
    return {
        "dimension_portfolio": dimension_portfolio,
        "innovation_summary": {key: str((value.get("innovation_summary") or {}).get(key) or "待评价")
                               for key in ("project_increment", "contemporary_comparison", "ai_contribution")},
        "influence_summary": {key: str((value.get("influence_summary") or {}).get(key) or "待评价")
                              for key in ("academic_and_reuse", "real_application", "pujiang_integration", "professional_response")},
        "specific_layer": layer("specific_layer"),
        "global_layer": layer("global_layer"),
        "system_collaboration": {
            "status": collaboration_status if collaboration_status in collaboration_statuses else "本轮未体现",
            "conclusion": "当前材料未支持所声称的协同阶段，需核实实际调用、反馈与重复运行记录。" if collaboration_downgraded else str(collaboration.get("conclusion") or ""),
            "design_basis": text_list(collaboration.get("design_basis")),
            "chains": _collaboration_chains(collaboration.get("chains")),
            "evidence": [str(row) for row in collaboration.get("evidence") or []],
            "gaps": [str(row) for row in collaboration.get("gaps") or []],
        },
        "overall_judgment": str(value.get("overall_judgment") or ""),
        "scope_impact_level": {**_normalize_level(value.get("scope_impact_level"), "L", require_sources=True), "scope": str((value.get("scope_impact_level") or {}).get("scope") or "") if isinstance(value.get("scope_impact_level"), dict) else ""},
        "leading_outcomes": [str(row) for row in value.get("leading_outcomes") or []],
        "overclaimed_outcomes": [str(row) for row in value.get("overclaimed_outcomes") or []],
        "expert_questions": [str(row) for row in value.get("expert_questions") or []][:5],
        "management_advice": [str(row) for row in value.get("management_advice") or []][:4],
        "evidence_confidence": _confidence(value.get("evidence_confidence")),
        "judgment_confidence": _confidence(value.get("judgment_confidence")),
        "confidence": _confidence(value.get("judgment_confidence")),
    }


def _failed_d_project_synthesis(error: str) -> dict[str, Any]:
    return {
        **_normalize_d_project_synthesis({}),
        "overall_judgment": "项目综合归纳调用未完成。",
        "management_advice": [error],
    }

__all__ = [
    "D_DIMENSION_SYSTEM_PROMPT",
    "EVALUATION_STANDARD_VERSION",
    "IndicatorEvaluationPipeline",
    "OUTCOME_SYNTHESIS_SYSTEM_PROMPT",
    "PROJECT_SYNTHESIS_SYSTEM_PROMPT",
    "PUBLIC_NARRATIVE_REQUIREMENTS",
    "build_indicator_input_contract",
    "build_indicator_product",
]
