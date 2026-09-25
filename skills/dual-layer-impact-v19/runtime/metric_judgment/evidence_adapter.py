from __future__ import annotations

from .active_indicators import replacement_for
from .upstream_materials import import_upstream_materials
from .input_coverage import dimension_input_coverage

import copy
import json
import re
from collections import Counter
from typing import Any

from .d_dimension_framework import (
    D_BRANCH_INDICATORS,
    D_DIMENSIONS,
    DIMENSION_INPUT_CONTRACTS,
    UPSTREAM_COMPONENT_CONTRACTS,
    route_professional_metric,
)
from .external_claim_routing import external_claim_route
from .evaluation_policy import EVIDENCE_ORGANIZATION, DIMENSION_OBSERVABLES
from .material_routing import REVIEW, review_materials, explicit_project_facts


RESULT_KEYWORDS = {
    "RES-MECH-01": ["流场", "unifield", "prosnet", "神经算子", "符号回归", "pde", "drsr"],
    "RES-MECH-02": ["连续介质", "本构", "蠕变", "材料", "应力", "介质"],
    "RES-MECH-03": ["飞行器", "气动", "燃烧", "反应流", "gassdata", "跨流域"],
    "RES-MECH-04": ["车轴", "列车", "轨道", "淬火", "疲劳", "制造"],
    "RES-MECH-05": ["爆炸", "地下工程", "cDEM", "巷道", "冲击", "知识图谱"],
    "RES-ORG-01": ["有机功能", "拉曼", "探针", "oled", "tadf", "激光", "反应", "分子"],
    "RES-ORG-02": ["cpi", "聚酰亚胺", "胶膜", "透光率", "cte", "玻璃化"],
    "RES-ORG-03": ["nmr", "核磁", "谱学", "specxmaster", "nmrnet", "数据库"],
    "RES-SCI-01": ["丰登", "基因", "作物", "育种", "蛋白", "gene", "seed"],
    "RES-SCI-02": ["光刻胶", "krf", "树脂", "lgbo", "贝叶斯", "pdi"],
    "RES-SCI-03": ["石墨", "ni-c", "机器学习势", "碳", "刻蚀"],
    "RES-SCI-04": ["脑电", "脑磁", "brainomni", "meg", "eeg", "语言解码", "数据库"],
    "RES-SCI-05": ["视觉假体", "视皮层", "猕猴", "神经假体", "刺激"],
}


def build_step3_outcome_cards(
    project_id: str, frozen_snapshot: dict[str, Any]
) -> list[dict[str, Any]]:
    """Use only the frozen Step 3 parent/child IDs as evaluation objects."""
    if (
        frozen_snapshot.get("schema_version") != "step3-frozen-outcomes.v1"
        or frozen_snapshot.get("status") != "frozen"
        or str(frozen_snapshot.get("project_id") or "") != project_id
    ):
        return []
    cards = []
    seen_ids: set[str] = set()
    for source in frozen_snapshot.get("outcomes") or []:
        if not isinstance(source, dict):
            continue
        outcome_id = str(source.get("outcome_id") or "").strip()
        children = [copy.deepcopy(row) for row in source.get("child_outcomes") or [] if isinstance(row, dict)]
        child_ids = [str(row.get("outcome_id") or "").strip() for row in children]
        if not outcome_id or outcome_id in seen_ids or any(not value or value in seen_ids for value in child_ids):
            raise ValueError(f"Step 3冻结成果ID缺失或重复：{outcome_id or '<empty>'}")
        seen_ids.update([outcome_id, *child_ids])
        child_titles = [str(row.get("title") or row.get("outcome_id") or "") for row in children]
        cards.append(
            {
                "outcome_id": outcome_id,
                "canonical_outcome_id": outcome_id,
                "global_outcome_id": f"OUT-{project_id}-{outcome_id}",
                "title": str(source.get("title") or outcome_id),
                "child_outcomes": children,
                "child_outcome_ids": child_ids,
                "step3_role": str(source.get("step3_role") or ""),
                "problem_ids": [str(value) for value in source.get("problem_ids") or []],
                "scope": "；".join(child_titles),
                "upstream_status": "frozen",
                "status": "frozen",
                "confirmation_status": "step3_frozen",
                "source_provider": str(frozen_snapshot.get("source_provider") or "Step 3成果凝练组"),
                "source_schema": str(frozen_snapshot.get("schema_version") or ""),
                "source_file": str(frozen_snapshot.get("source_file") or ""),
                "source_card": copy.deepcopy(source),
                "linked_metric_ids": [],
                "external_claim_ids": [],
            }
        )
    return cards


def build_evidence_adapter(workspace: dict[str, Any]) -> dict[str, Any]:
    cards = list((workspace.get("evaluation_framework") or {}).get("outcome_cards") or [])
    project_id = str((workspace.get("project_profile") or {}).get("project_id") or "")
    metrics = _professional_metrics(workspace)
    metric_bindings = _bind_metrics(cards, metrics)
    external = (workspace.get("available_search") or {}).get("external_group") or {}
    upstream = import_upstream_materials(external, project_id, cards, REVIEW.get('outcome_contracts',{}).get(project_id,{}))
    contribution = workspace.get("contribution_attribution") or {}
    project_materials = workspace.get("project_materials") or {}
    use_records = workspace.get("use_integration_evidence") or {}
    step1_core_problems = copy.deepcopy(
        ((workspace.get("evidence_repository") or {}).get("internal_achievement") or {}).get("core_problems") or []
    )
    routed_external = _route_external_claims(
        project_id,
        external.get("claims") or [],
        {str(card.get("outcome_id") or "") for card in cards},
    )

    outcome_packets: dict[str, dict[str, Any]] = {}
    for card in cards:
        outcome_id = str(card.get("outcome_id") or "")
        external_claims = copy.deepcopy((routed_external["by_outcome"] or {}).get(outcome_id) or [])
        # No internal-Search-group delivery exists yet.  Contribution/result
        # files under the historical 内部Search folder must not be relabeled as
        # internal Search evidence.
        internal_groups: list[dict[str, Any]] = []
        components = _contribution_components(contribution, outcome_id)
        card_metrics = [copy.deepcopy(row) for row in metric_bindings if outcome_id in row["outcome_ids"]]
        for row in card_metrics:
            row['metric'].pop('excluded_evidence', None)
            current = replacement_for(project_id, row['metric']['metric_id'])
            if current:
                row['metric']['metric_name'] = current['name']
                row['metric']['criterion'] = current['question']
                row['metric']['current_indicator_id'] = current['indicator_id']
        card_metrics = _merge_current_metrics(card_metrics)
        card["linked_metric_ids"] = [str(row["metric"]["metric_id"]) for row in card_metrics]
        card["external_claim_ids"] = [str(row.get("claim_id") or "") for row in external_claims]
        dimensions = {
            dimension["question_id"]: _dimension_packet(
                dimension["question_id"],
                card,
                card_metrics,
                external_claims,
                internal_groups,
                components,
                (project_materials.get("outcome_packets") or {}).get(outcome_id) or {},
                (use_records.get("outcome_packets") or {}).get(outcome_id) or [],
                step1_core_problems,
            )
            for dimension in D_DIMENSIONS
        }
        for did, dimension_packet in dimensions.items():
            dimension_packet['supplemental_materials'] = [copy.deepcopy(record) for record in upstream['records']
                if outcome_id in record['outcome_ids'] and any(b.startswith(did+'.') for b in record['branch_ids'])]
            dimension_packet['source_counts']['supplemental_materials'] = len(dimension_packet['supplemental_materials'])
            if dimension_packet['supplemental_materials']:
                dimension_packet['missing_state'] = '已有材料，待核验'
        outcome_packets[outcome_id] = {
            "outcome_id": outcome_id,
            "source_card": copy.deepcopy(card.get("source_card") or {}),
            "source_provider": str(card.get("source_provider") or "Step 3成果凝练组"),
            "internal_search": internal_groups,
            "ai_contribution": components,
            "external_search": external_claims,
            "professional_metric_bindings": card_metrics,
            "dimensions": dimensions,
            "counts": {
                "internal_search": len(internal_groups),
                "ai_contribution_components": len(components.get("components") or []),
                "ai_attribution_records": len(components.get("attribution_records") or []),
                "external_search": len(external_claims),
                "professional_metrics": len(card_metrics),
            },
        }

    dimension_counts = Counter(
        row["dimension_id"] for row in metric_bindings
    )
    branch_counts = Counter(
        row["branch_id"] for row in metric_bindings
    )
    return {
        "schema_version": "outcome-evidence-adapter.v6",
        "upstream_materials": upstream,
        "material_review": {
            "revision": REVIEW['revision'],
            "coverage_schema": "actual-dimension-input-coverage.v2",
            "metric_count": len(metric_bindings),
            "related_material_links": sum(len(row['metric']['evidence_preview']) for row in metric_bindings),
            "held_material_links": sum(len(row['metric']['excluded_evidence']) for row in metric_bindings),
            "unassigned_metric_count": sum(not row['branch_id'] for row in metric_bindings),
            "branch_limits": copy.deepcopy(REVIEW['branch_limits']),
            "dimension_coverage": dimension_input_coverage(outcome_packets),
        },
        "project_id": project_id,
        "status": "loaded" if cards else "no_outcome_cards",
        "card_source": "Step 3冻结成果/step3_frozen_outcomes.outcomes",
        "source_channels": ["internal_search", "ai_contribution", "external_search"],
        "channel_status": {
            "internal_search": {
                "status": "not_delivered",
                "provider": "内部 Search 组",
                "note": "上游尚未交付；当前为0是正常状态，成果组历史文件不计入内部 Search。",
            },
            "ai_contribution": {
                "status": "loaded" if (contribution.get("component_extraction") or {}).get("status") == "loaded" else "not_delivered",
                "provider": "贡献组",
                "note": "组件和归因记录按显式路由挂到Step 3冻结成果；不得改变冻结成果边界。",
            },
            "external_search": {
                "status": "loaded" if external.get("status") == "loaded" else "not_delivered",
                "provider": "外部 Search 组",
                "note": "按显式声明路由矩阵挂接；禁止关键词兜底。",
            },
        },
        "professional_metric_policy": (
            "三个项目共用21个D1-D7分支指标；L2-L4只作为可追溯专业事实挂到相应分支，"
            "不定义分支、不独立评分，也不按事实数量决定维度权重。"
        ),
        "branch_indicators": [
            {
                **copy.deepcopy(row),
                "professional_metric_count": branch_counts.get(row["branch_id"], 0),
            }
            for row in D_BRANCH_INDICATORS
        ],
        "outcome_packets": outcome_packets,
        "project_context_external_search": copy.deepcopy(routed_external["project_context"]),
        "external_routing_audit": copy.deepcopy(routed_external["audit"]),
        "professional_metric_bindings": metric_bindings,
        "dimension_branch_counts": {
            row["question_id"]: sum(
                branch["dimension_id"] == row["question_id"]
                for branch in D_BRANCH_INDICATORS
            )
            for row in D_DIMENSIONS
        },
        "branch_metric_counts": {
            row["branch_id"]: branch_counts.get(row["branch_id"], 0)
            for row in D_BRANCH_INDICATORS
        },
        "dimension_metric_counts": {row["question_id"]: dimension_counts.get(row["question_id"], 0) for row in D_DIMENSIONS},
        "unmatched": {
            "internal_search_groups": [],
            "external_search_claims": copy.deepcopy(routed_external["unrouted"]),
        },
        "governance": {
            "boundary": "适配层使用跨项目统一分支问题组织证据，只做格式统一、对象绑定和事实挂接，不生成新的检索事实或贡献归因结论。",
            "traceability": "每条归集记录保留上游来源编号、原始指标编号和提供方。",
            "missing_data": "没有匹配到成果的材料保留在未匹配区，不强行绑定。",
            "anti_bias": "专业事实数量只表示已有事实密度，不表示D维度的重要性、得分或权重。",
            "external_routing": "外部声明只允许显式映射为成果直接证据、多成果共享组件或项目级背景；禁止文本关键词自动挂接。",
            "source_chain": "成果级外部依据保留声明、来源记录、原始URL和本地证据路径四级追溯链。",
            "internal_search_state": "内部 Search 未交付时统一标记not_delivered，不把成果组或其他目录材料冒充其交付。",
        },
    }


def _merge_current_metrics(rows):
    merged = {}
    for row in rows:
        metric = row['metric']
        key = metric.get('current_indicator_id') or metric['metric_id']
        if key not in merged:
            merged[key] = copy.deepcopy(row)
            merged[key]['metric']['source_metric_ids'] = []
            merged[key]['metric']['evidence_preview'] = []
        target = merged[key]['metric']
        target['source_metric_ids'].append(metric['metric_id'])
        known = {(json.dumps(item.get('source_ref') or {}, sort_keys=True, ensure_ascii=False),item.get('summary'))
                 for item in target['evidence_preview']}
        for item in metric['evidence_preview']:
            source_key = (json.dumps(item.get('source_ref') or {}, sort_keys=True, ensure_ascii=False),item.get('summary'))
            if source_key not in known:
                target['evidence_preview'].append(copy.deepcopy(item))
                known.add(source_key)
        target['evidence_count'] = len(target['evidence_preview'])
    return list(merged.values())


def _professional_metrics(workspace: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    professional_search = (
        ((workspace.get("available_search") or {}).get("professional") or {}).get("by_metric") or {}
    )
    for layer in (workspace.get("indicator_system") or {}).get("layers") or []:
        layer_id = str(layer.get("layer_id") or "")
        if layer_id not in {"L2", "L3", "L4"}:
            continue
        for source in layer.get("metrics") or []:
            metric = copy.deepcopy(source)
            metric['project_id'] = str((workspace.get('project_profile') or {}).get('project_id') or '')
            metric["source_layer"] = layer_id
            metric["internal_search"] = _compact_internal_search(
                professional_search.get(str(metric.get("metric_id") or "")) or {}
            )
            rows.append(metric)
    return rows


def _bind_metrics(cards: list[dict[str, Any]], metrics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    bindings = []
    for metric in metrics:
        route = route_professional_metric(metric)
        accepted, excluded = review_materials(metric, route)
        targets = set(route['review'].get('outcome_ids') or []) if accepted else set()
        expected_cards = REVIEW.get('outcome_contracts', {}).get(metric.get('project_id'), {})
        positive = [card for card in cards if card.get('outcome_id') in targets
                    and {key:card.get(key) for key in ('title','child_outcome_ids')} == expected_cards.get(card.get('outcome_id'))]
        scope = 'outcome_specific' if positive else 'unassigned_project_material'
        compact = _compact_metric(metric)
        compact.update(evidence_preview=accepted, excluded_evidence=excluded,
                       original_evidence_count=len(accepted)+len(excluded), evidence_count=len(accepted))
        bindings.append(
            {
                "metric": compact,
                "branch_id": route["branch_id"],
                "dimension_id": route["dimension_id"],
                "outcome_ids": [str(card.get("outcome_id") or "") for card in positive],
                "scope": scope,
                "routing_basis": route["routing_basis"],
                "routing_kind": route["routing_kind"],
                "matched_terms": list(route["matched_terms"]),
                "review_boundary": route['boundary'],
            }
        )
    return bindings


def _dimension_packet(
    dimension_id: str,
    card: dict[str, Any],
    metric_bindings: list[dict[str, Any]],
    external_claims: list[dict[str, Any]],
    internal_groups: list[dict[str, Any]],
    contribution: dict[str, Any],
    project_packet: dict[str, Any],
    use_records: list[dict[str, Any]],
    step1_core_problems: list[dict[str, Any]],
) -> dict[str, Any]:
    metrics = [copy.deepcopy(row) for row in metric_bindings if row["dimension_id"] == dimension_id]
    branches = []
    for definition in D_BRANCH_INDICATORS:
        if definition["dimension_id"] != dimension_id:
            continue
        branch_metrics = [
            copy.deepcopy(row) for row in metrics
            if row["branch_id"] == definition["branch_id"]
        ]
        branches.append({
            **copy.deepcopy(definition),
            "professional_metrics": branch_metrics,
            "professional_metric_count": len(branch_metrics),
        })
    external = [_compact_external(row) for row in external_claims if _external_relevant(dimension_id, row)]
    internal_facts = explicit_project_facts(_compact_project_packet(project_packet), card)
    if dimension_id in {"D3", "D4", "D7"}:
        internal_facts = []
    if dimension_id == "D6":
        # General project/platform facts and cross-topic calls belong to the
        # separate collaboration judgment. D6 accepts only evidence explicitly
        # delivered for the Pujiang National Laboratory AI4S mainline.
        internal_facts = []
    if dimension_id == "D5":
        internal_facts = [*internal_facts, *explicit_project_facts(use_records, card)]
    ai = copy.deepcopy(contribution) if dimension_id in {"D1", "D2", "D5"} else {
        "policy": "AI贡献不作为本维度的主要判断对象。",
        "components": [],
        "attribution_records": [],
    }
    return {
        "dimension_id": dimension_id,
        "outcome_id": str(card.get("outcome_id") or ""),
        "evidence_organization": copy.deepcopy(EVIDENCE_ORGANIZATION),
        "observables": copy.deepcopy(DIMENSION_OBSERVABLES[dimension_id]),
        "input_contract": copy.deepcopy(DIMENSION_INPUT_CONTRACTS[dimension_id]),
        "upstream_component_contract": copy.deepcopy(UPSTREAM_COMPONENT_CONTRACTS[dimension_id]),
        "step1_core_problems": copy.deepcopy(step1_core_problems) if dimension_id == "D1" else [],
        "step3_problem_links": [str(value) for value in card.get("problem_ids") or []] if dimension_id == "D1" else [],
        "problem_mapping_status": (
            "explicit" if dimension_id == "D1" and card.get("problem_ids")
            else "missing_requires_upstream" if dimension_id == "D1"
            else "not_applicable"
        ),
        "professional_metrics": metrics,
        "branches": branches,
        "internal_search": copy.deepcopy(internal_groups),
        "project_facts": internal_facts,
        "ai_contribution": ai,
        "external_search": external,
        "source_counts": {
            "professional_metrics": len(metrics),
            "branch_indicators": len(branches),
            "internal_search": len(internal_groups),
            "project_facts": len(internal_facts),
            "ai_components": len(ai.get("components") or []),
            "external_search": len(external),
        },
        "missing_state": "待核验" if not any((metrics, internal_facts, external, ai.get("components"))) else "已有依据",
    }


def _contribution_components(contribution: dict[str, Any], outcome_id: str) -> dict[str, Any]:
    component_delivery = contribution.get("component_extraction") or {}
    extraction = component_delivery.get("data") or {}
    routed = (component_delivery.get("outcome_packets") or {}).get(outcome_id) or {}
    result_cards = copy.deepcopy(routed.get("result_cards") or [])
    components = copy.deepcopy(routed.get("components") or [])
    attribution_records = list((contribution.get("outcome_packets") or {}).get(outcome_id) or [])
    result_ids = {str(row.get('result_id') or '') for row in result_cards}
    return {
        "result_cards": result_cards,
        "components": components,
        "attribution_records": attribution_records,
        "traditional_methods": [copy.deepcopy(row) for row in extraction.get('traditional_methods') or []
                                if result_ids.intersection(row.get('result_ids') or [])],
        "attribution_readiness": [
            copy.deepcopy(row) for row in extraction.get("attribution_readiness") or []
            if str(row.get("result_id") or "") == outcome_id
        ],
        "policy": "只使用贡献组已有拆解并按显式路由挂到Step 3冻结成果；D1、D2和D5按各自问题区分AI、数据、算力、自动化、设备、领域知识、传统方法和人工贡献。",
    }


def _route_external_claims(
    project_id: str,
    claims: list[dict[str, Any]],
    valid_outcome_ids: set[str],
) -> dict[str, Any]:
    by_outcome = {outcome_id: [] for outcome_id in sorted(valid_outcome_ids)}
    project_context = []
    unrouted = []
    scope_counts: Counter[str] = Counter()
    source_ids: set[str] = set()
    source_link_count = 0
    outcome_mount_count = 0

    for source in claims:
        claim_id = str(source.get("claim_id") or source.get("source_id") or "")
        route = external_claim_route(project_id, claim_id)
        compact = _compact_external(source)
        if route is None:
            compact["routing_error"] = "显式路由矩阵缺少该声明。"
            unrouted.append(compact)
            continue
        targets = [str(value) for value in route.get("outcome_ids") or []]
        invalid_targets = [value for value in targets if value not in valid_outcome_ids]
        scope = str(route.get("scope") or "")
        compact.update({
            "route_scope": scope,
            "route_basis": str(route.get("basis") or ""),
            "routed_outcome_ids": targets,
            "legacy_outcome_ids": [str(value) for value in source.get("related_outcome_ids") or []],
        })
        if invalid_targets or scope not in {"direct", "shared_component", "project_context"}:
            compact["routing_error"] = (
                f"路由目标不存在：{', '.join(invalid_targets)}" if invalid_targets
                else f"非法路由类型：{scope}"
            )
            unrouted.append(compact)
            continue
        if scope == "project_context":
            if targets:
                compact["routing_error"] = "项目级背景不得同时指定成果目标。"
                unrouted.append(compact)
                continue
            project_context.append(compact)
        else:
            if not targets:
                compact["routing_error"] = "成果级路由缺少目标成果。"
                unrouted.append(compact)
                continue
            for outcome_id in targets:
                by_outcome[outcome_id].append(copy.deepcopy(compact))
                outcome_mount_count += 1
        scope_counts[scope] += 1
        attached_ids = {str(value) for value in compact.get("source_record_ids") or [] if value}
        source_ids.update(attached_ids)
        source_link_count += len(attached_ids)

    return {
        "by_outcome": by_outcome,
        "project_context": project_context,
        "unrouted": unrouted,
        "audit": {
            "routing_mode": "explicit_claim_matrix_only",
            "claim_count": len(claims),
            "accounted_claim_count": len(claims) - len(unrouted),
            "outcome_routed_claim_count": scope_counts["direct"] + scope_counts["shared_component"],
            "project_context_claim_count": scope_counts["project_context"],
            "unrouted_claim_count": len(unrouted),
            "direct_claim_count": scope_counts["direct"],
            "shared_component_claim_count": scope_counts["shared_component"],
            "outcome_mount_count": outcome_mount_count,
            "unique_attached_source_record_count": len(source_ids),
            "claim_source_link_count": source_link_count,
            "keyword_fallback_used": False,
        },
    }


def _match_text_rows(card: dict[str, Any], rows: list[dict[str, Any]], fields: tuple[str, ...]) -> list[dict[str, Any]]:
    return [copy.deepcopy(row) for row in rows if _match_score(card, " ".join(str(row.get(field) or "") for field in fields)) > 0]


def _match_score(card: dict[str, Any], value: str) -> int:
    text = value.lower()
    outcome_id = str(card.get("outcome_id") or "")
    keywords = RESULT_KEYWORDS.get(outcome_id) or _tokens(
        " ".join(str(card.get(key) or "") for key in ("title", "domain", "task_object", "result_object", "scope"))
    )
    return sum(1 for keyword in keywords if len(keyword) >= 2 and keyword.lower() in text)


def _tokens(value: str) -> list[str]:
    return list(dict.fromkeys(re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}|[\u4e00-\u9fff]{2,8}", value.lower())))[:40]


def _external_relevant(dimension_id: str, row: dict[str, Any]) -> bool:
    declared_dimensions = {
        str(value) for value in row.get("related_metric_ids") or []
        if str(value).startswith("D")
    }
    if declared_dimensions:
        return dimension_id in declared_dimensions
    return False


def _compact_metric(metric: dict[str, Any]) -> dict[str, Any]:
    return {
        "metric_id": str(metric.get("metric_id") or ""),
        "metric_name": str(metric.get("metric_name") or ""),
        "source_layer": str(metric.get("source_layer") or metric.get("layer") or ""),
        "axis": str(metric.get("axis") or ""),
        "criterion": str(metric.get("criterion") or ""),
        "stage_target": str(metric.get("stage_target") or ""),
        "benchmark": str(metric.get("benchmark") or ""),
        "evidence_count": int(metric.get("evidence_count") or 0),
        "evidence_preview": copy.deepcopy(metric.get("evidence_preview") or []),
        "missing_evidence": copy.deepcopy(metric.get("missing_evidence") or []),
        "internal_search": copy.deepcopy(metric.get("internal_search") or {}),
    }


def _compact_internal_search(packet: dict[str, Any]) -> dict[str, Any]:
    if not packet:
        return {}
    return {
        "metric_id": str(packet.get("metric_id") or ""),
        "query": str(packet.get("query") or ""),
        "research_status": str(packet.get("research_status") or ""),
        "sota_summary": str(packet.get("sota_summary") or ""),
        "sota_value": str(packet.get("sota_value") or ""),
        "baseline": str(packet.get("baseline") or ""),
        "comparability_hint": str(packet.get("comparability_hint") or ""),
        "confidence": str(packet.get("confidence") or ""),
        "source_ids": [str(value) for value in packet.get("source_ids") or []],
        "sources": [
            {
                "source_id": str(source.get("source_id") or ""),
                "provider": str(source.get("provider") or ""),
                "title": str(source.get("title") or ""),
                "year": source.get("year"),
                "doi": str(source.get("doi") or ""),
                "url": str(source.get("url") or ""),
                "venue": str(source.get("venue") or ""),
            }
            for source in (packet.get("sources") or [])[:8]
            if isinstance(source, dict)
        ],
    }


def _compact_external(row: dict[str, Any]) -> dict[str, Any]:
    sources = [
        _compact_external_source(source)
        for source in row.get("source_records") or []
        if isinstance(source, dict)
    ]
    return {
        "claim_id": str(row.get("claim_id") or row.get("source_id") or ""),
        "external_use_assessment": str(row.get('external_use_assessment') or ''),
        "review_cutoff": str(row.get('review_cutoff') or ''),
        "domain": str(row.get("domain") or ""),
        "project_claim": str(row.get("project_claim") or ""),
        "project_conditions": str(row.get("project_conditions") or ""),
        "public_original": str(row.get("public_original") or ""),
        "current_strong_result": str(row.get("current_strong_result") or ""),
        "key_difference": str(row.get("key_difference") or ""),
        "verdict": str(row.get("verdict") or ""),
        "evidence_effect": _search_effect(row),
        "verification_gates": _search_verification_gates(row),
        "citation_usage": str(row.get("citation_usage") or "待分类"),
        "required_evidence": str(row.get("required_evidence") or ""),
        "source_record_ids": [str(value) for value in row.get("source_record_ids") or []],
        "source_records": sources,
        "source_record_count": len(sources),
        "primary_urls": [str(value) for value in row.get("primary_urls") or []],
        "local_evidence": [str(value) for value in row.get("local_evidence") or []],
        "core_evidence_ids": [str(value) for value in row.get("core_evidence_ids") or []],
        "related_metric_ids": [str(value) for value in row.get("related_metric_ids") or []],
        "related_outcome_ids": [str(value) for value in row.get("related_outcome_ids") or []],
    }


def _search_effect(row: dict[str, Any]) -> str:
    text = " ".join(str(row.get(key) or "") for key in ("verdict", "key_difference", "required_evidence")).lower()
    if any(term in text for term in ("反驳", "不支持", "错误", "明显落后", "refut")):
        return "反驳"
    if any(term in text for term in ("限定", "限制", "部分", "不可比", "尚不能", "待核", "limit")):
        return "限制"
    if any(term in text for term in ("支持", "确认", "一致", "成立", "support")):
        return "支持"
    return "待分类"


def _search_verification_gates(row: dict[str, Any]) -> dict[str, str]:
    records = [item for item in row.get("source_records") or [] if isinstance(item, dict)]
    has_time = any(item.get("event_date") or item.get("time_window_status") for item in records)
    has_public_source = any(item.get("url") for item in records) or bool(row.get("primary_urls"))
    has_protocol = bool(row.get("project_conditions") and row.get("current_strong_result"))
    return {
        "time": "已有时间信息" if has_time else "待核验",
        "object": "已由显式成果路由约束",
        "protocol": "已有比较条件、仍需同口径复核" if has_protocol else "待核验",
        "independence": "存在公开来源、仍需主体独立性复核" if has_public_source else "待核验",
    }


def _compact_external_source(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_id": str(source.get("source_id") or ""),
        "evidence_id": str(source.get("evidence_id") or ""),
        "title": str(source.get("title") or ""),
        "source_type": str(source.get("source_type") or source.get("source_channel") or ""),
        "provider": str(source.get("provider") or ""),
        "url": str(source.get("url") or ""),
        "local_member": str(source.get("local_member") or ""),
        "screenshot_member": str(source.get("screenshot_member") or ""),
        "locator": str(source.get("locator") or ""),
        "event_date": str(source.get("event_date") or ""),
        "time_window_status": str(source.get("time_window_status") or ""),
        "quote": str(source.get("quote") or ""),
        "evidence_text": str(source.get("evidence_text") or ""),
        "abstract_excerpt": str(source.get("abstract_excerpt") or ""),
        "content": str(source.get("content") or ""),
        "direction": str(source.get("direction") or "待分类"),
    }


def _compact_project_packet(packet: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for key in ("achievement_groups", "major_achievements", "achievement_claims", "claim_evidence", "acceptance_baselines", "new_internal_claims"):
        for row in packet.get(key) or []:
            rows.append({"fact_type": key, **copy.deepcopy(row)})
    return rows


def _text(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(_text(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_text(item) for item in value)
    return str(value or "")


__all__ = [
    "build_step3_outcome_cards",
    "build_evidence_adapter",
]
