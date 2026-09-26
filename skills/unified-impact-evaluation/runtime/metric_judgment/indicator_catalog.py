from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any

from .evidence_repository import load_evidence_repository
from .external_search_import import load_external_search_group
from .d_dimension_framework import d_dimension_contract
from .evidence_adapter import build_evidence_adapter, build_step3_outcome_cards
from .integration_v4 import (
    build_strategic_context,
    enrich_outcome_cards,
    outcome_aliases,
)
from .indicator_product import build_indicator_input_contract
from .milestones import bind_to_current_milestone, build_milestone_context


LAYER_POLICIES = {
    "L2": {
        "name": "学科与共性能力层",
        "governance": "llm_dynamic_with_human_review",
        "purpose": "根据项目所属学科、共性技术主线和成果类型动态选择或生成专业指标。",
        "comparison": "仅在同学科、同任务口径下比较。",
    },
    "L3": {
        "name": "场景与任务专业层",
        "governance": "llm_dynamic_with_human_review",
        "purpose": "根据具体科学问题、场景任务、测试协议和阶段目标动态拆分指标。",
        "comparison": "必须绑定任务对象、数据、测试条件和阶段阈值。",
    },
    "L4": {
        "name": "项目特有成果与声明层",
        "governance": "llm_dynamic_with_human_review",
        "purpose": "提取通用与专业篮子无法覆盖的项目独有成果、交付物和可证伪声明。",
        "comparison": "原则上不跨项目横向比较，只核验自身声明、阶段目标和证据链。",
    },
}


COMPONENT_RESULT_OUTCOME_MAP = {
    "P01": {
        "RES-MECH-01": ["OC-P01-01"],
        "RES-MECH-02": ["OC-P01-03"],
        "RES-MECH-03": ["OC-P01-02"],
        "RES-MECH-04": ["OC-P01-03"],
        "RES-MECH-05": ["OC-P01-02"],
    },
    "P02": {
        "RES-ORG-01": ["MAIN-005"],
        "RES-ORG-02": ["MAIN-005"],
        "RES-ORG-03": ["MAIN-003"],
    },
    "P06": {
        "RES-SCI-01": ["OC-P06-01"],
        "RES-SCI-02": ["OC-P06-02"],
        "RES-SCI-03": ["OC-P06-02"],
        "RES-SCI-04": ["OC-P06-03"],
        "RES-SCI-05": ["OC-P06-03"],
    },
}


AI_ATTRIBUTION_OUTCOME_MAP = {
    "P02": {
        "CONTRIB-001": ["MAIN-005"],
        "CONTRIB-002": ["MAIN-001"],
        "CONTRIB-003": ["MAIN-002"],
        "CONTRIB-004": ["MAIN-005"],
        "CONTRIB-005": ["MAIN-001"],
        "CONTRIB-006": ["MAIN-005"],
        "CONTRIB-007": ["MAIN-003"],
        "CONTRIB-008": ["MAIN-003"],
    },
}


def load_indicator_workspace(output_dir: str | Path, project_id: str) -> dict[str, Any]:
    root = Path(output_dir) / project_id
    module_root = Path(__file__).resolve().parents[1]
    evidence_root = module_root / "评价依据"
    evidence_repository = load_evidence_repository(evidence_root, project_id)
    internal_evidence_root = evidence_root / project_id / "内部Search"
    contribution_evidence_root = evidence_root / project_id / "贡献归因"
    professional_search_path = _prefer_file(
        internal_evidence_root / "score_sota_evidence.json",
        root / "score_sota_evidence.json",
    )
    ai_attribution_path = _prefer_file(
        contribution_evidence_root / "ai_attribution.json",
        root / "ai_attribution.json",
    )
    component_extraction_path = contribution_evidence_root / "ai_contribution_component_extraction.json"
    step3_path = evidence_root / project_id / "Step3冻结成果" / "step3_frozen_outcomes.json"
    profile = _required_json(root / "project_profile.json")
    layered = _required_json(root / "layer_evaluations.json")
    expected = _optional_json(root / "expected_level_assessment.json")
    milestone_context = build_milestone_context(profile, expected)
    profile = {**profile, "milestone_context": copy.deepcopy(milestone_context)}
    fact_base = _optional_json(root / "acceptance_fact_base.json")
    professional_search = _optional_json(professional_search_path)
    ai_attribution = _optional_value(ai_attribution_path)
    component_extraction = _optional_json(component_extraction_path)
    step3_frozen = _optional_json(step3_path)
    layers = []
    for layer_id in ("L2", "L3", "L4"):
        source_layer = next(
            (row for row in layered.get("layers") or [] if row.get("layer_id") == layer_id),
            {},
        )
        metrics = []
        for source_metric in source_layer.get("metrics") or []:
            metric_id = str(source_metric.get("metric_id") or "")
            metric = {
                "metric_id": metric_id,
                "metric_name": str(source_metric.get("metric_name") or metric_id),
                "layer": layer_id,
                "axis": str(source_metric.get("axis") or "innovation"),
                "criterion": str(
                    source_metric.get("criterion")
                    or ""
                ),
                "benchmark": str(source_metric.get("benchmark") or ""),
                "stage_target": str(source_metric.get("stage_target") or ""),
                "core": bool(source_metric.get("core")),
                "applicable": source_metric.get("applicable", True) is not False,
                "evidence_count": int(source_metric.get("evidence_count") or 0),
                "evidence_preview": [
                    {
                        "evidence_id": str(item.get("evidence_id") or ""),
                        "summary": str(item.get("summary") or item.get("content") or ""),
                        "direction": str(item.get("direction") or ""),
                        "strength": str(item.get("strength") or ""),
                        "source_ref": dict(item.get("source_ref") or {}),
                    }
                    for item in (source_metric.get("evidence_items") or [])
                ],
                "missing_evidence": list(source_metric.get("missing_evidence") or []),
                "source_metric_ids": list(source_metric.get("source_metric_ids") or []),
                "catalog_status": "professional_fact",
                "generation_source": _generation_source(source_layer),
            }
            metric = bind_to_current_milestone(metric, milestone_context)
            metrics.append(metric)
        layers.append(
            {
                "layer_id": layer_id,
                **LAYER_POLICIES[layer_id],
                "route_code": str(source_layer.get("route_code") or layer_id),
                "route_name": str(source_layer.get("route_name") or ""),
                "source_scope": str(source_layer.get("scope") or ""),
                "implementation": dict(source_layer.get("implementation") or {}),
                "metric_count": len(metrics),
                "metrics": metrics,
            }
        )

    indicator_system = {
        "version": "d1-d7-professional-facts.v3",
        "governance_note": "L2-L4仅作为专业事实底座归集到D1-D7，不独立评分或综合。",
        "layers": layers,
        "counts": {layer["layer_id"]: layer["metric_count"] for layer in layers},
    }
    materials_root = Path(output_dir).resolve().parent.parent / "reference_materials"
    reference_root = materials_root / "修改意见3"
    external_group = load_external_search_group(reference_root, project_id, evidence_root)
    current_d_framework = d_dimension_contract()
    framework = {
        "schema_version": "innovation-impact-outcome-d1-d7.v3",
        "outcome_questions": copy.deepcopy(current_d_framework["dimensions"]),
        "branch_indicators": copy.deepcopy(current_d_framework["branch_indicators"]),
        "dimension_statuses": copy.deepcopy(current_d_framework["statuses"]),
        "dimension_input_contracts": copy.deepcopy(current_d_framework["dimension_input_contracts"]),
        "layer_summary_method": copy.deepcopy(current_d_framework["layer_summary_method"]),
        "professional_metric_policy": current_d_framework["professional_metric_policy"],
        "scoring_policy": current_d_framework["scoring_policy"],
        "outcome_cards": build_step3_outcome_cards(project_id, step3_frozen),
        "governance": (
            "评价对象只采用Step 3冻结的主要成果和分支成果ID；指标组不得合并、拆分、改名或重做成果凝练，"
            "只负责把检索、AI归因、项目材料和L2-L4专业事实路由后完成逐成果D1-D7评价。"
        ),
        "mainline": [
            "直接采用Step 3冻结主要成果作为评价对象并保留分支成果ID",
            "按显式路由把内部Search、AI贡献组件和外部Search绑定到冻结成果",
            "按21个跨项目统一分支组织D1-D7评价依据",
            "将L2-L4指标作为专业事实挂到对应分支，不读取旧等级、不按数量赋权",
            "逐成果形成有依据的创新与影响力判断",
            "由既有D结果归纳特定层和全局层",
            "项目系统性与课题协同单独判断",
        ],
        "report_sections": [
            "核心问题与成果定位",
            "逐成果D1-D7判断",
            "特定层与全局层归纳",
            "项目系统性与课题协同",
            "专家争议、证据缺口与管理建议",
        ],
    }
    framework["outcome_cards"] = enrich_outcome_cards(
        profile, framework.get("outcome_cards") or []
    )
    framework["outcome_cards"] = [
        bind_to_current_milestone(card, milestone_context)
        for card in framework.get("outcome_cards") or []
    ]
    for card in framework.get("outcome_cards") or []:
        outcome_id = str(card.get("outcome_id") or "")
        aliases = outcome_aliases(card)
        linked = {str(value) for value in card.get("linked_metric_ids") or []}
        exact_external_claim_ids = {
            str(value) for value in card.get("external_claim_ids") or [] if value
        }
        matched_claims = [
            str(claim.get("claim_id"))
            for claim in external_group.get("claims") or []
            if (
                str(claim.get("claim_id") or "") in exact_external_claim_ids
                if exact_external_claim_ids else (
                    aliases.intersection(str(value) for value in claim.get("related_outcome_ids") or [])
                    or (
                        not claim.get("related_outcome_ids")
                        and linked.intersection(str(value) for value in claim.get("related_metric_ids") or [])
                    )
                )
            )
        ]
        card["external_claim_ids"] = matched_claims
        card["external_claim_count"] = len(matched_claims)
        card["external_source_count"] = len({
            str(source_id)
            for claim in external_group.get("claims") or []
            if str(claim.get("claim_id") or "") in set(matched_claims)
            for source_id in claim.get("source_record_ids") or []
            if source_id
        })
    project_materials = _build_project_materials(
        fact_base,
        framework.get("outcome_cards") or [],
        [],
    )
    outcome_card_confirmation = _confirm_outcome_cards(
        fact_base, framework.get("outcome_cards") or [], project_materials
    )
    outcome_portfolio = _build_outcome_portfolio(
        framework.get("outcome_cards") or [], outcome_card_confirmation
    )
    contribution_attribution = _build_contribution_attribution(
        ai_attribution,
        framework.get("outcome_cards") or [],
        ai_attribution_path,
        component_extraction,
        component_extraction_path,
        project_id,
    )
    use_integration_evidence = _build_use_integration_evidence(
        fact_base, framework.get("outcome_cards") or [], root / "acceptance_fact_base.json"
    )
    strategic_context = build_strategic_context(
        root, profile, indicator_system, framework.get("outcome_cards") or []
    )
    workspace = {
        "schema_version": "indicator-workspace.v6",
        "project_profile": profile,
        "milestone_context": milestone_context,
        "indicator_system": indicator_system,
        "evaluation_framework": framework,
        "step3_frozen_outcomes": step3_frozen,
        "project_materials": project_materials,
        "outcome_card_confirmation": outcome_card_confirmation,
        "outcome_portfolio": outcome_portfolio,
        "contribution_attribution": contribution_attribution,
        "use_integration_evidence": use_integration_evidence,
        "strategic_context": strategic_context,
        "evidence_repository": evidence_repository,
        "source_inventory": {
            "project_dir": str(root),
            "layered_evaluation_file": str(root / "layer_evaluations.json"),
            "expected_level_file": str(root / "expected_level_assessment.json"),
            "fact_base_file": str(root / "acceptance_fact_base.json"),
            "fact_base_summary": dict(fact_base.get("summary") or {}),
            "evidence_repository_root": str(evidence_root / project_id),
            "professional_search_file": str(professional_search_path),
            "external_search_archive": str(external_group.get("archive_file") or ""),
            "external_search_repository": str(external_group.get("repository_root") or ""),
            "ai_attribution_file": str(ai_attribution_path),
            "ai_contribution_component_file": str(component_extraction_path),
            "step3_frozen_outcomes_file": str(step3_path),
            "expert_feedback_file": str(root / "expert_feedback.json"),
        },
        "available_search": {
            "professional": professional_search,
            "external_group": external_group,
        },
    }
    workspace["evidence_adapter"] = build_evidence_adapter(workspace)
    workspace["indicator_input_contract"] = build_indicator_input_contract(workspace)
    return workspace


def _generation_source(layer: dict[str, Any]) -> str:
    mode = str((layer.get("implementation") or {}).get("mode") or "")
    return {
        "vendored_rule_engine": "原项目专项规则引擎",
        "supplied_prompt_and_tree": "原项目交付指标树",
        "repository_metric_adapter": "原项目固定专业指标目录",
    }.get(mode, "原项目现有分层评价输出")


def _required_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"缺少指标工作台输入：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _prefer_file(primary: Path, fallback: Path) -> Path:
    return primary if primary.is_file() else fallback


def _optional_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        return value if isinstance(value, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _optional_value(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


OUTCOME_KEYWORDS = {
    "OC-P01-01": ["流场", "高铁", "磁流体", "mhd", "pde", "drivaer", "driver", "压力场", "神经算子"],
    "OC-P01-02": ["飞行器", "燃烧", "爆炸", "地下工程", "气动", "超声速", "hydrogen", "反应流"],
    "OC-P01-03": ["车轴", "本构", "材料", "淬火", "疲劳", "制造", "应力应变", "连续介质"],
    "OC-P02-01": ["mr-tadf", "oled", "有机激光", "发光", "功能材料", "候选筛选", "分子设计"],
    "OC-P02-02": ["nmrexp", "specxmaster", "核磁", "nmr", "谱学", "fid", "数据库", "解析"],
    "OC-P02-03": ["cpi", "聚酰亚胺", "胶膜", "透光率", "cte", "玻璃化", "成膜"],
    "OC-P02-04": ["拉曼", "探针", "rie", "谱图", "表征"],
    "OC-P02-05": ["新型功能化反应", "新型功能分子", "干湿闭环", "反应", "分子", "实验验证"],
    "OC-P06-01": ["育种", "作物", "基因", "生物", "蛋白", "丰登"],
    "OC-P06-02": ["材料", "光刻胶", "石墨", "实验", "贝叶斯", "力场"],
    "OC-P06-03": ["脑电", "脑磁", "神经", "假体", "dbs", "动物"],
}


def _build_project_materials(
    fact_base: dict[str, Any],
    cards: list[dict[str, Any]],
    new_internal_claims: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    new_internal_claims = new_internal_claims or []
    packets = {}
    for card in cards:
        outcome_id = str(card.get("outcome_id") or "")
        aliases = outcome_aliases(card)
        keywords = OUTCOME_KEYWORDS.get(outcome_id) or _fallback_keywords(card)
        packets[outcome_id] = {
            "keywords": keywords,
            "achievement_groups": [
                _compact_group(row) for row in _matched(fact_base.get("achievement_groups"), keywords, 4)
            ],
            "major_achievements": [
                _compact_achievement(row) for row in _matched(fact_base.get("major_achievements"), keywords, 8)
            ],
            "achievement_claims": [
                _compact_claim(row) for row in _matched(fact_base.get("achievement_claims"), keywords, 8)
            ],
            "claim_evidence": [
                _compact_evidence(row) for row in _matched(fact_base.get("claim_evidence"), keywords, 8)
            ],
            "acceptance_baselines": [
                _compact_baseline(row) for row in _matched(fact_base.get("acceptance_baselines"), keywords, 8)
            ],
            "new_internal_claims": [
                copy.deepcopy(row)
                for row in new_internal_claims
                if aliases.intersection(str(value) for value in row.get("outcome_ids") or [])
            ],
        }
        packets[outcome_id]["counts"] = {
            key: len(value)
            for key, value in packets[outcome_id].items()
            if isinstance(value, list) and key != "keywords"
        }
    return {
        "schema_version": "indicator-project-materials.v1",
        "summary": dict(fact_base.get("summary") or {}),
        "source_policy": dict(fact_base.get("source_policy") or {}),
        "baseline_source_files": list(fact_base.get("baseline_source_files") or []),
        "outcome_source_files": list(fact_base.get("outcome_source_files") or []),
        "outcome_packets": packets,
        "project_evidence_inventory": {
            "achievement_claims": [_compact_claim(row) for row in fact_base.get("achievement_claims") or []],
            "claim_evidence": [_compact_evidence(row) for row in fact_base.get("claim_evidence") or []],
            "acceptance_baselines": [_compact_baseline(row) for row in fact_base.get("acceptance_baselines") or []],
            "new_internal_claims": copy.deepcopy(new_internal_claims),
        },
        "new_internal_claim_count": len(new_internal_claims),
        "project_supporting_claims": [
            copy.deepcopy(row)
            for row in new_internal_claims
            if not row.get("outcome_ids")
        ],
    }


def _build_contribution_attribution(
    value: Any,
    cards: list[dict[str, Any]],
    source_file: Path,
    component_extraction: dict[str, Any] | None = None,
    component_source_file: Path | None = None,
    project_id: str = "",
) -> dict[str, Any]:
    records = value if isinstance(value, list) else list((value or {}).get("ai_attributions") or [])
    packets = {}
    summaries = {}
    assigned_records = _assign_attributions(records, cards, project_id)
    for card in cards:
        outcome_id = str(card.get("outcome_id") or "")
        matched = assigned_records.get(outcome_id) or []
        packets[outcome_id] = [_compact_attribution(row) for row in matched]
        summaries[outcome_id] = _aggregate_outcome_attribution(outcome_id, matched)
    component_extraction = component_extraction or {}
    components = list(component_extraction.get("components") or [])
    result_cards = list(component_extraction.get("result_cards") or [])
    component_type_counts: dict[str, int] = {}
    for row in components:
        component_type = str(row.get("component_type") or "未标注")
        component_type_counts[component_type] = component_type_counts.get(component_type, 0) + 1
    result_outcome_map = COMPONENT_RESULT_OUTCOME_MAP.get(project_id, {})
    component_outcome_packets = {}
    for card in cards:
        outcome_id = str(card.get("outcome_id") or "")
        matched_result_ids = {
            result_id for result_id, outcome_ids in result_outcome_map.items()
            if outcome_id in outcome_ids
        }
        if any(str(row.get("result_id") or "") == outcome_id for row in result_cards):
            matched_result_ids.add(outcome_id)
        component_outcome_packets[outcome_id] = {
            "result_cards": [
                copy.deepcopy(row) for row in result_cards
                if str(row.get("result_id") or "") in matched_result_ids
            ],
            "components": [
                copy.deepcopy(row) for row in components
                if matched_result_ids.intersection(str(value) for value in row.get("result_ids") or [])
            ],
        }
    return {
        "status": "loaded" if records else "not_available",
        "source_file": str(source_file),
        "record_count": len(records),
        "records": [_compact_attribution(row) for row in records],
        "outcome_packets": packets,
        "outcome_summaries": summaries,
        "attribution_routing_audit": {
            "mode": "explicit_step3_id_map_only",
            "record_count": len(records),
            "routed_record_count": sum(len(value) for value in assigned_records.values()),
            "keyword_fallback_used": False,
        },
        "unassigned_attribution_records": [
            _compact_attribution(row) for row in records
            if not (AI_ATTRIBUTION_OUTCOME_MAP.get(project_id) or {}).get(str(row.get("contribution_id") or ""))
        ],
        "component_extraction": {
            "status": "loaded" if component_extraction else "not_available",
            "source_file": str(component_source_file or ""),
            "schema": str(component_extraction.get("schema") or ""),
            "project": copy.deepcopy(component_extraction.get("project") or {}),
            "result_card_count": len(result_cards),
            "component_count": len(components),
            "traditional_method_count": len(component_extraction.get("traditional_methods") or []),
            "component_type_counts": component_type_counts,
            "outcome_packets": component_outcome_packets,
            "data": copy.deepcopy(component_extraction),
        },
    }


def _assign_attributions(
    rows: Any, cards: list[dict[str, Any]], project_id: str
) -> dict[str, list[dict[str, Any]]]:
    """Route attribution records only through an explicit frozen-ID map."""
    assignments = {str(card.get("outcome_id") or ""): [] for card in cards}
    routes = AI_ATTRIBUTION_OUTCOME_MAP.get(project_id) or {}
    for row in rows or []:
        contribution_id = str(row.get("contribution_id") or "")
        for outcome_id in routes.get(contribution_id) or []:
            if outcome_id in assignments:
                assignments[outcome_id].append(row)
    return assignments


def _aggregate_outcome_attribution(outcome_id: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    compact_rows = [_compact_attribution(row) for row in rows]
    if not compact_rows:
        return {
            "contribution_id": f"ATTR-{outcome_id}",
            "ai_position": "尚未从上游材料中识别成果级作用位置",
            "attribution_type": "证据不足，暂无法归因",
            "attribution_status": "待核验",
            "causal_chain": [],
            "incremental_judgement": "当前没有可明确归属于该成果的AI贡献记录，尚不能形成肯定性归因结论。",
            "attribution_basis": [],
            "baseline_comparability": "尚未形成",
            "ablation_sufficiency": "尚未形成",
            "human_intervention_risk": "待核验",
            "data_platform_confounding_risk": "待核验",
            "evidence_state": "缺少成果级归因材料",
            "evidence_gaps": ["补充该成果中AI方法、关键决策与最终结果之间的可复核因果链。"],
            "local_record_count": 0,
            "detail_records": [],
        }

    positions = _unique_text(
        row.get("ai_position") for row in compact_rows
        if row.get("ai_position") and "尚未" not in str(row.get("ai_position"))
    )
    types = {str(row.get("attribution_type") or "") for row in compact_rows}
    if "AI直接贡献" in types and "AI辅助贡献" in types:
        attribution_type = "AI直接贡献（含辅助环节）"
    elif "AI直接贡献" in types:
        attribution_type = "AI直接贡献"
    elif "AI辅助贡献" in types:
        attribution_type = "AI辅助贡献"
    else:
        attribution_type = "证据不足，暂无法归因"
    conditional = any(row.get("attribution_status") == "条件归因" for row in compact_rows)
    gaps = _unique_text(gap for row in compact_rows for gap in (row.get("evidence_gaps") or []))[:5]
    bases = _unique_text(value for row in compact_rows for value in (row.get("attribution_basis") or []))
    subjects = _unique_text(
        str((row.get("causal_chain") or [""])[0]) for row in compact_rows
        if row.get("causal_chain")
    )
    position_text = "、".join(positions) if positions else "作用位置尚待核验"
    return {
        "contribution_id": f"ATTR-{outcome_id}",
        "ai_position": position_text,
        "attribution_type": attribution_type,
        "attribution_status": "条件归因" if conditional else "不宜归因",
        "causal_chain": subjects,
        "incremental_judgement": (
            f"现有材料显示AI主要作用于{position_text}，涉及{len(compact_rows)}项局部技术记录。"
            "目前仅形成条件性成果归因，仍需通过同口径对照、消融实验或过程记录验证AI对最终结果的实质贡献。"
            if conditional else "现有材料不足以确认AI对该成果形成了可归因的实质贡献。"
        ),
        "attribution_basis": bases,
        "baseline_comparability": "；".join(_unique_text(row.get("baseline_comparability") for row in compact_rows)) or "尚未形成",
        "ablation_sufficiency": "；".join(_unique_text(row.get("ablation_sufficiency") for row in compact_rows)) or "尚未形成",
        "human_intervention_risk": "；".join(_unique_text(row.get("human_intervention_risk") for row in compact_rows)) or "待核验",
        "data_platform_confounding_risk": "；".join(_unique_text(row.get("data_platform_confounding_risk") for row in compact_rows)) or "待核验",
        "evidence_state": "成果级综合归因待验证" if conditional else "证据不足",
        "evidence_gaps": gaps,
        "local_record_count": len(compact_rows),
        "detail_records": compact_rows,
    }


def _unique_text(values: Any) -> list[str]:
    result = []
    seen = set()
    for value in values:
        text = str(value or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _confirm_outcome_cards(
    fact_base: dict[str, Any],
    cards: list[dict[str, Any]],
    project_materials: dict[str, Any],
) -> dict[str, Any]:
    coverage = float((fact_base.get("summary") or {}).get("achievement_coverage_rate") or 0)
    packets = project_materials.get("outcome_packets") or {}
    card_checks = []
    step3_cards = bool(cards) and all(
        str(card.get("confirmation_status") or "") == "step3_frozen" for card in cards
    )
    for card in cards:
        outcome_id = str(card.get("outcome_id") or "")
        packet = packets.get(outcome_id) or {}
        counts = packet.get("counts") or {}
        fact_count = int(counts.get("major_achievements") or 0)
        claim_count = int(counts.get("achievement_claims") or 0)
        evidence_count = int(counts.get("claim_evidence") or 0)
        upstream_candidate = str(card.get("confirmation_status") or "") == "candidate"
        card_checks.append({
            "outcome_id": outcome_id,
            "global_outcome_id": card.get("global_outcome_id"),
            "confirmed": bool(step3_cards or (fact_count and claim_count and not upstream_candidate)),
            "upstream_status": card.get("confirmation_status") or "project_fact_catalog",
            "major_achievement_count": fact_count,
            "achievement_claim_count": claim_count,
            "claim_evidence_count": evidence_count,
        })
    has_new_candidates = any(
        str(card.get("confirmation_status") or "") == "candidate" for card in cards
    )
    confirmed = bool(
        cards and (
            step3_cards
            or (
                coverage >= 1.0 and not has_new_candidates
                and all(row["confirmed"] for row in card_checks)
            )
        )
    )
    return {
        "status": "confirmed" if confirmed else "requires_review",
        "method": (
            "step3_frozen_outcomes_accepted_as_evaluation_objects"
            if step3_cards else (
                "upstream_candidate_outcomes_require_owner_confirmation"
                if has_new_candidates else "authoritative_achievement_catalog_and_evidence_mapping"
            )
        ),
        "basis": (
            "直接采用Step 3冻结的主要成果和分支成果ID作为逐成果D1-D7评价对象；"
            "指标组不合并、拆分、改名或重新凝练成果。"
            if step3_cards else (
                "原项目权威成果目录覆盖率为100%，每张成果卡均已关联项目成果事实和成果声明；"
                "成果卡作为标志性成果链正式进入评价。"
            )
            if confirmed else (
                "已完整接收成果抽取组候选及内部宣称，但候选不能由指标组自行转为正式成果卡；"
                "需由成果抽取组或项目负责人选择、合并或否定候选，并确认最终1—3项成果组合。"
                if has_new_candidates else "成果目录或成果卡关联仍不完整。"
            )
        ),
        "candidate_count": len(cards) if has_new_candidates else 0,
        "human_confirmation_required": has_new_candidates,
        "confirmation_owner": "成果抽取组/项目负责人" if has_new_candidates else "已确认成果目录",
        "external_expert_required": False,
        "achievement_coverage_rate": coverage,
        "cards": card_checks,
    }


def _build_outcome_portfolio(
    cards: list[dict[str, Any]], confirmation: dict[str, Any]
) -> dict[str, Any]:
    confirmed_count = sum(bool(row.get("confirmed")) for row in confirmation.get("cards") or [])
    requires_selection = bool(confirmation.get("human_confirmation_required"))
    return {
        "schema_version": "outcome-portfolio-governance.v2",
        "status": "requires_human_selection" if requires_selection else "confirmed",
        "candidate_count": len(cards),
        "confirmed_count": confirmed_count,
        "required_final_outcome_range": {},
        "human_confirmation_required": requires_selection,
        "confirmation_owner": "成果抽取组/项目负责人" if requires_selection else "已确认成果目录",
        "external_expert_required": False,
        "formal_evaluation_gate": (
            "blocked_until_1_to_3_flagship_outcomes_confirmed"
            if requires_selection else "open"
        ),
        "governance": (
            "当前成果卡仍需上游确认后才能进入正式评价。"
            if requires_selection else
            "当前直接采用Step 3冻结成果作为评价对象；是否属于核心创新成果由D1、D2评价给出观点，不改变冻结成果边界。"
        ),
    }


def _build_use_integration_evidence(
    fact_base: dict[str, Any], cards: list[dict[str, Any]], source_file: Path
) -> dict[str, Any]:
    use_words = ["服务", "应用", "交付", "用户", "平台", "调用", "运行", "集成", "部署", "合同", "效率", "自动化", "闭环"]
    records = [
        row for row in fact_base.get("claim_evidence") or []
        if _text(row).lower().find("第三方") >= 0 or any(word in _text(row) for word in use_words)
    ]
    packets = {}
    for card in cards:
        outcome_id = str(card.get("outcome_id") or "")
        keywords = OUTCOME_KEYWORDS.get(outcome_id) or _fallback_keywords(card)
        packets[outcome_id] = [_compact_evidence(row) for row in _matched(records, keywords, 12)]
    return {
        "status": "candidate_internal_records" if records else "not_available",
        "source_file": str(source_file),
        "record_count": len(records),
        "records": [_compact_evidence(row) for row in records[:40]],
        "outcome_packets": packets,
        "governance": "这些是原项目事实库中的候选使用/集成记录；是否足以证明真实影响仍由指标组逐条判断。",
    }


def _matched(rows: Any, keywords: list[str], limit: int) -> list[dict[str, Any]]:
    ranked = []
    for index, row in enumerate(rows or []):
        text = _text(row).lower()
        score = sum(1 for word in keywords if word.lower() in text)
        if score:
            ranked.append((score, -index, row))
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    return [row for _, _, row in ranked[:limit]]


def _text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _fallback_keywords(card: dict[str, Any]) -> list[str]:
    text = f"{card.get('title', '')} {card.get('core_problem_candidate', '')}"
    return [token for token in re.split(r"[、，。；：\s/]+", text) if len(token) >= 2][:12]


def _source(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "file_name": source.get("file_name"),
        "page": source.get("page"),
        "sheet": source.get("sheet"),
        "location_label": source.get("location_label"),
        "source_ref": source.get("source_ref"),
        "material_type": source.get("material_type"),
        "material_category": source.get("material_category"),
        "quote": str(source.get("quote") or "")[:800],
    }


def _compact_group(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "group_id": row.get("group_id"), "group_name": row.get("group_name"),
        "group_summary": str(row.get("group_summary") or "")[:1000],
        "child_achievement_ids": row.get("child_achievement_ids") or [],
        "claim_ids": row.get("claim_ids") or [], "evidence_ids": row.get("evidence_ids") or [],
        "sources": [_source(source) for source in (row.get("sources") or [])[:4]],
    }


def _compact_achievement(row: dict[str, Any]) -> dict[str, Any]:
    sources = [
        _source(source)
        for statement in row.get("supporting_statements") or []
        for source in statement.get("sources") or []
    ]
    return {
        "achievement_id": row.get("achievement_id"), "achievement_name": row.get("achievement_name"),
        "achievement_type": row.get("achievement_type"), "summary": str(row.get("summary") or "")[:1000],
        "claim_ids": row.get("claim_ids") or [], "aligned_baseline_ids": row.get("aligned_baseline_ids") or [],
        "evidence_status": row.get("evidence_status"), "gaps": row.get("gaps") or [],
        "sources": sources[:4],
    }


def _compact_claim(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "claim_id": row.get("claim_id"), "claim_type": row.get("claim_type"),
        "claim_text": str(row.get("claim_text") or "")[:1000],
        "achievement_ids": row.get("achievement_ids") or [], "evidence_ids": row.get("evidence_ids") or [],
        "attainment_status": row.get("attainment_status"), "evidence_status": row.get("evidence_status"),
        "source": _source(row.get("source") or {}),
    }


def _compact_evidence(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "evidence_id": row.get("evidence_id"), "evidence_type": row.get("evidence_type"),
        "evidence_text": str(row.get("evidence_text") or "")[:1000],
        "evidence_status": row.get("evidence_status"), "claim_ids": row.get("claim_ids") or [],
        "llm_validation": row.get("llm_validation") or {}, "external_verification": row.get("external_verification") or {},
        "source": _source(row.get("source") or {}),
    }


def _compact_baseline(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "baseline_id": row.get("baseline_id"), "indicator_name": row.get("indicator_name"),
        "requirement_text": str(row.get("requirement_text") or "")[:800],
        "target_values": row.get("target_values") or [], "verification_method": row.get("verification_method"),
        "status": row.get("status"), "source": _source(row.get("source") or {}),
    }


def _compact_attribution(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "contribution_id": row.get("contribution_id"), "ai_position": row.get("ai_position"),
        "attribution_type": row.get("attribution_type"), "attribution_status": row.get("attribution_status"),
        "causal_chain": [str(value)[:1200] for value in row.get("causal_chain") or []],
        "incremental_judgement": str(row.get("incremental_judgement") or "")[:800],
        "attribution_basis": row.get("attribution_basis") or [], "baseline_comparability": row.get("baseline_comparability"),
        "ablation_sufficiency": row.get("ablation_sufficiency"), "human_intervention_risk": row.get("human_intervention_risk"),
        "data_platform_confounding_risk": str(row.get("data_platform_confounding_risk") or "")[:800],
        "evidence_state": row.get("evidence_state"),
        "evidence_gaps": [str(value)[:500] for value in row.get("evidence_gaps") or []],
    }
