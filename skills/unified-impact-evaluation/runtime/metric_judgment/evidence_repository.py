from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


CATEGORY_DIRS = {
    "internal_search": "内部Search",
    "contribution_attribution": "贡献归因",
    "external_search": "外部Search",
}

EXTERNAL_SECTIONS = (
    "00_项目输入与审计边界",
    "01_SOTA与对比指标验证",
    "02_项目前既有成果追溯",
    "03_成果使用评价与媒体报道",
    "04_综合结论",
)


def load_evidence_repository(evidence_root: str | Path, project_id: str) -> dict[str, Any]:
    root = Path(evidence_root).resolve()
    project_root = root / project_id
    categories = {
        key: _category_summary(project_root / dirname)
        for key, dirname in CATEGORY_DIRS.items()
    }
    external_root = project_root / CATEGORY_DIRS["external_search"]
    packages = sorted(
        (path for path in external_root.glob("Search验证综合评估_*") if path.is_dir()),
        key=lambda path: path.name,
        reverse=True,
    )
    package = packages[0] if packages else None
    sections = {
        name: {
            "path": str(package / name) if package else "",
            "status": "available" if package and (package / name).is_dir() else "missing",
            "file_count": _file_count(package / name) if package else 0,
        }
        for name in EXTERNAL_SECTIONS
    }
    current_milestone = _read_current_milestone(project_root / "README.md")
    internal_achievement = _load_internal_achievement_package(
        project_root / CATEGORY_DIRS["internal_search"]
    )
    internal_achievement["current_milestone"] = current_milestone
    return {
        "schema_version": "evaluation-evidence-repository.v1",
        "project_id": project_id,
        "status": "loaded" if project_root.is_dir() else "not_available",
        "root": str(project_root),
        "current_milestone": current_milestone,
        "categories": categories,
        "internal_achievement": internal_achievement,
        "external_package": str(package) if package else "",
        "external_package_name": package.name if package else "",
        "external_sections": sections,
        "governance": {
            "category_names": list(CATEGORY_DIRS.values()),
            "milestone_axis": ["M0", "M12", "M18", "M24", "M36"],
            "custom_milestones_allowed": True,
        },
    }


def _load_internal_achievement_package(internal_root: Path) -> dict[str, Any]:
    packages = sorted(
        (path for path in internal_root.glob("成果组输出_v*") if path.is_dir()),
        key=lambda path: path.name,
        reverse=True,
    )
    if not packages:
        return {
            "schema_version": "internal-achievement-evidence.v1",
            "status": "not_available",
            "snapshot_name": "",
            "summary": {},
            "core_problems": [],
            "candidate_items": [],
            "signature_groups": [],
            "professional_questions": [],
            "source_files": [],
        }

    package = packages[0]
    profile = _optional_json(package / "project_profile.json")
    core = _optional_json(package / "core_problem_candidates.json")
    signatures = _optional_json(package / "signature_achievement_groups.json")
    fact_base = _optional_json(package / "acceptance_fact_base.json")
    questions = _optional_json(package / "professional_review_questions.json")
    intake = _optional_json(package / "material_intake_raw.json")

    problem_rows = []
    for row in core.get("core_problem_candidates") or []:
        semantic_fields = row.get("semantic_field_evidence") or {}
        source_rows = []
        for source in _as_list(row.get("source_evidence")):
            if not isinstance(source, dict):
                continue
            source_rows.append({
                "file_name": str(source.get("file_name") or ""),
                "page": source.get("page"),
                "location_label": str(source.get("location_label") or ""),
                "has_location": bool(source.get("has_location")),
                "quote": str(source.get("quote") or ""),
            })
        problem_rows.append({
            "problem_id": str(row.get("problem_id") or ""),
            "problem_level": str(row.get("problem_level") or ""),
            "problem_title": str(row.get("problem_title") or ""),
            "prior_method_bottleneck": str(row.get("prior_method_bottleneck") or ""),
            "required_change_after_project": str(row.get("required_change_after_project") or ""),
            "semantic_field_evidence": {
                field: {
                    "status": str((semantic_fields.get(field) or {}).get("status") or ""),
                    "note": str((semantic_fields.get(field) or {}).get("note") or ""),
                }
                for field in ("prior_method_bottleneck", "required_change_after_project")
            },
            "why_it_matters": str(row.get("why_it_matters") or ""),
            "confidence": str(row.get("confidence") or ""),
            "needs_external_search": bool(row.get("needs_external_search")),
            "needs_expert_confirmation": bool(row.get("needs_expert_confirmation")),
            "sources": source_rows,
        })

    disposition = signatures.get("inventory_disposition") or {}
    candidate_rows = []
    for kind, rows in (
        ("main_achievement", disposition.get("main_achievement_disposition") or []),
        ("branch_achievement", disposition.get("branch_achievement_disposition") or []),
    ):
        for row in rows:
            candidate_rows.append({
                "item_kind": kind,
                "item_id": str(row.get("item_id") or ""),
                "item_name": str(row.get("item_name") or ""),
                "item_type": str(row.get("item_type") or ""),
                "suggested_position": str(row.get("suggested_position") or ""),
                "parent_main_achievement_id": str(row.get("parent_main_achievement_id") or ""),
                "claim_count": len(row.get("claim_ids") or []),
                "branch_count": len(row.get("branch_achievement_ids") or []),
                "handling_note": str(row.get("handling_note") or ""),
            })

    group_rows = []
    for row in signatures.get("signature_achievement_groups") or []:
        timeline = row.get("contribution_timeline") or {}
        group_rows.append({
            "group_id": str(row.get("group_id") or ""),
            "outcome_id": str(row.get("outcome_id") or ""),
            "group_name": str(row.get("group_name") or ""),
            "linked_problem_ids": [str(value) for value in row.get("linked_problem_ids") or []],
            "problem_alignment_summary": str(row.get("problem_alignment_summary") or ""),
            "source_selection_method": str(row.get("source_selection_method") or ""),
            "internal_evidence_summary": str(row.get("internal_evidence_summary") or ""),
            "evidence_boundaries": [str(value) for value in _as_list(row.get("evidence_boundaries"))],
            "expert_acceptance_risk": str(row.get("expert_acceptance_risk") or ""),
            "prior_foundation_clues": [
                str(value) for value in timeline.get("T0_prior_foundation_clues") or []
            ],
            "current_increment_clues": [
                str(value) for value in timeline.get("T1_current_increment_clues") or []
            ],
            "time_boundary_status": str(timeline.get("boundary_status") or ""),
            "traceable_source_locations": [
                str(value) for value in row.get("traceable_source_locations") or []
            ],
        })

    question_rows = []
    for row in questions.get("professional_review_questions") or []:
        question_rows.append({
            "group_id": str(row.get("group_id") or ""),
            "group_name": str(row.get("group_name") or ""),
            "domain": str(row.get("domain") or ""),
            "expert_review_required": bool(row.get("expert_review_required")),
            "required_evidence": [str(value) for value in _as_list(row.get("required_evidence"))],
            "key_questions": [str(value) for value in _as_list(row.get("key_questions"))],
            "risk_flags": [str(value) for value in _as_list(row.get("risk_flags"))],
            "current_professional_boundary": str(row.get("current_professional_boundary") or ""),
            "suggested_expert_type": str(row.get("suggested_expert_type") or ""),
        })

    fact_summary = fact_base.get("summary") or {}
    inventory_summary = disposition.get("summary") or {}
    main_count = int(fact_summary.get("major_achievement_count") or 0)
    branch_count = int(fact_summary.get("branch_achievement_count") or 0)
    candidate_count = main_count + branch_count
    disposition_count = len(candidate_rows)
    return {
        "schema_version": "internal-achievement-evidence.v1",
        "status": "loaded",
        "provider": "成果组",
        "snapshot_name": package.name,
        "snapshot_path": str(package),
        "source_project_id": str(profile.get("project_id") or ""),
        "project_title": str(profile.get("title") or core.get("project_title") or ""),
        "principal_investigator": str(profile.get("principal_investigator") or ""),
        "summary": {
            "problem_count": len(problem_rows),
            "main_achievement_count": main_count,
            "branch_achievement_count": branch_count,
            "candidate_count": candidate_count,
            "claim_count": int(fact_summary.get("achievement_claim_count") or 0),
            "disposition_count": disposition_count,
            "undispositioned_count": max(candidate_count - disposition_count, 0),
            "signature_candidate_count": int(inventory_summary.get("signature_candidate_count") or 0),
            "supporting_capability_count": int(inventory_summary.get("supporting_capability_count") or 0),
            "supporting_output_count": int(inventory_summary.get("supporting_output_count") or 0),
            "needs_mapping_review_count": int(inventory_summary.get("needs_mapping_review_count") or 0),
            "signature_group_count": len(group_rows),
            "professional_question_count": len(question_rows),
            "unassigned_branch_achievement_count": int(
                fact_summary.get("unassigned_branch_achievement_count") or 0
            ),
        },
        "core_problems": problem_rows,
        "candidate_items": candidate_rows,
        "signature_groups": group_rows,
        "professional_questions": question_rows,
        "source_files": [str(value) for value in intake.get("completed_files") or []],
        "governance": {
            "problem_status": "立项问题候选，需按正式立项材料复核。",
            "achievement_status": "成果组候选池，不等于已通过核心性评价。",
            "classification_status": "展示成果组当前建议位置；待评价端后续形成正式核心性判断。",
        },
    }


def _optional_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


def _category_summary(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "status": "available" if path.is_dir() else "missing",
        "file_count": _file_count(path),
        "byte_count": _byte_count(path),
    }


def _file_count(path: Path) -> int:
    return sum(1 for item in path.rglob("*") if item.is_file()) if path.is_dir() else 0


def _byte_count(path: Path) -> int:
    if not path.is_dir():
        return 0
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _read_current_milestone(path: Path) -> str:
    if not path.is_file():
        return ""
    match = re.search(r"当前里程碑[：:]\s*`?(M\d+)", path.read_text(encoding="utf-8"))
    return match.group(1) if match else ""


__all__ = ["load_evidence_repository"]
