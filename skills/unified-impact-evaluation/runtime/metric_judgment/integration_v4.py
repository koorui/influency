from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from .milestones import EVIDENCE_TIME_ROLES, build_milestone_context

EVIDENCE_PACKAGE_DEFINITIONS = [
    {"package_id": "EP1", "name": "难题依据", "purpose": "说明过去真正卡在哪里，以及为什么是专业上的决定性瓶颈。"},
    {"package_id": "EP2", "name": "国内外水平", "purpose": "在同任务、同数据、同协议和同资源口径下确定外部强路线。"},
    {"package_id": "EP3", "name": "当前节点之前的基础", "purpose": "追溯团队、承担单位和外部技术前序，明确技术继承关系。"},
    {"package_id": "EP4", "name": "当前评价窗口内的新增", "purpose": "说明从上一项目里程碑到当前项目里程碑新增了什么，以及增量属于何种类型。"},
    {"package_id": "EP5", "name": "AI作用边界", "purpose": "记录AI输入、输出、人工修改、实际执行、结果反馈和反事实。"},
    {"package_id": "EP6", "name": "同行认可与真实使用", "purpose": "区分被提及与被真实采用，优先独立复现、外部使用和下游结果。"},
]


def enrich_outcome_cards(
    project_profile: dict[str, Any], cards: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Add exchange IDs without changing the frozen Step 3 outcome ID."""
    project_id = str(project_profile.get("project_id") or "PROJECT")
    enriched = []
    for index, source in enumerate(cards, start=1):
        card = copy.deepcopy(source)
        local_id = str(card.get("canonical_outcome_id") or f"OUT-{index:02d}")
        global_id = str(card.get("global_outcome_id") or f"OUT-{project_id}-{index:02d}")
        problem_ids = [str(value) for value in card.get("problem_ids") or [] if value]
        if card.get("problem_id") and str(card.get("problem_id")) not in problem_ids:
            problem_ids.insert(0, str(card.get("problem_id")))
        card.update(
            {
                "canonical_outcome_id": local_id,
                "global_outcome_id": global_id,
                "problem_ids": list(dict.fromkeys(problem_ids)),
                "id_governance": "outcome_id与canonical_outcome_id均保持Step 3冻结ID；global_outcome_id只用于跨项目交换，不改变评价对象。",
            }
        )
        enriched.append(card)
    return enriched


def build_strategic_context(
    project_root: Path,
    project_profile: dict[str, Any],
    indicator_system: dict[str, Any],
    _cards: list[dict[str, Any]],
) -> dict[str, Any]:
    upstream = _load_first_mapping(
        project_root,
        ("problem_out_cap.json", "strategic_assessment.json", "outcome_catalog.json"),
    )
    problems = _normalize_problems(upstream.get("problems") or upstream.get("core_problems"))
    outcomes = _normalize_outcomes(
        upstream.get("outcomes") or upstream.get("signature_outcomes")
    )
    capabilities = _normalize_capabilities(
        upstream.get("capabilities") or upstream.get("common_capabilities")
    )
    lineage = _load_lineage_snapshot(str(project_profile.get("project_id") or ""))
    return {
        "schema_version": "problem-out-cap-lineage.v1",
        "source_status": "upstream_loaded" if upstream else "not_available",
        "source_files": list(upstream.get("source_files") or []) if upstream else [],
        "problems": problems,
        "outcomes": outcomes,
        "capabilities": capabilities,
        "technical_lineage": lineage,
        "evidence_package_definitions": copy.deepcopy(EVIDENCE_PACKAGE_DEFINITIONS),
        "evidence_time_roles": copy.deepcopy(EVIDENCE_TIME_ROLES),
        "governance": {
            "primary_key": "canonical_outcome_id（项目内）/ global_outcome_id（跨项目）",
            "boundary": "Problem、OUT和CAP仅接收上游正式交付；缺失时保持为空，指标组不生成兜底草案。",
            "feedback_loop": "高一级限制条件转成下一轮材料补充或Search核验任务，不得由指标组自行补写缺失事实。",
        },
        "layer_counts": dict(indicator_system.get("counts") or {}),
    }


def outcome_aliases(card: dict[str, Any]) -> set[str]:
    return {
        str(value)
        for value in (
            card.get("outcome_id"),
            card.get("canonical_outcome_id"),
            card.get("global_outcome_id"),
            *(card.get("legacy_outcome_ids") or []),
        )
        if value
    }


def _normalize_problems(value: Any) -> list[dict[str, Any]]:
    rows = value if isinstance(value, list) else []
    if rows:
        result = []
        for index, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                continue
            result.append(
                {
                    "problem_id": str(row.get("problem_id") or f"PROBLEM-{index:02d}"),
                    "past_bottleneck": str(row.get("past_bottleneck") or row.get("bottleneck") or ""),
                    "why_important": str(row.get("why_important") or row.get("significance") or ""),
                    "claimed_change": str(row.get("claimed_change") or row.get("expected_change") or ""),
                    "source_ids": list(row.get("source_ids") or []),
                    "status": str(row.get("status") or "candidate_awaiting_confirmation"),
                }
            )
        return result
    return []


def _normalize_outcomes(value: Any) -> list[dict[str, Any]]:
    rows = value if isinstance(value, list) else []
    result = []
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            continue
        result.append(
            {
                "outcome_id": str(row.get("outcome_id") or f"OUT-{index:02d}"),
                "canonical_outcome_id": row.get("canonical_outcome_id"),
                "global_outcome_id": row.get("global_outcome_id"),
                "title": str(row.get("title") or row.get("name") or ""),
                "problem_ids": list(row.get("problem_ids") or []),
                "linked_metric_ids": list(row.get("linked_metric_ids") or []),
                "status": str(row.get("status") or "candidate_awaiting_confirmation"),
            }
        )
    return result


def _normalize_capabilities(value: Any) -> list[dict[str, Any]]:
    rows = value if isinstance(value, list) else []
    if rows:
        normalized = []
        for index, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                continue
            normalized.append(
                {
                    "capability_id": str(row.get("capability_id") or f"CAP-{index:02d}"),
                    "name": str(row.get("name") or row.get("title") or ""),
                    "role": str(row.get("role") or row.get("description") or ""),
                    "outcome_ids": list(row.get("outcome_ids") or []),
                    "source_ids": list(row.get("source_ids") or []),
                    "status": str(row.get("status") or "candidate_awaiting_confirmation"),
                }
            )
        return normalized
    return []


def _load_lineage_snapshot(project_id: str) -> dict[str, Any]:
    if project_id != "P01":
        return {
            "status": "not_provided",
            "records": [],
            "note": "上游尚未提供结构化的前期基础—当前窗口新增技术血缘包；不得把缺失解释为不存在前期基础。",
        }
    value = _read_json(_examples_root() / "P01_prior_foundation.json")
    return {**value, "status": "loaded" if value.get("records") else "not_provided"}


def _load_first_mapping(root: Path, names: tuple[str, ...]) -> dict[str, Any]:
    for name in names:
        value = _read_json(root / name)
        if value:
            value.setdefault("source_files", []).append(str(root / name))
            return value
    return {}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _examples_root() -> Path:
    return Path(__file__).resolve().parent.parent / "examples"


__all__ = [
    "EVIDENCE_PACKAGE_DEFINITIONS",
    "EVIDENCE_TIME_ROLES",
    "build_strategic_context",
    "enrich_outcome_cards",
    "outcome_aliases",
]
