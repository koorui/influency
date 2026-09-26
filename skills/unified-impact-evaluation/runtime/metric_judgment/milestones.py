from __future__ import annotations

import re
from typing import Any, Iterable


DEFAULT_MILESTONE_CODES = ("M0", "M12", "M18", "M24", "M36")
DEFAULT_CURRENT_MILESTONE = "M12"
LEGACY_STAGE_ALIASES = {
    "S0": "M0",
    "T0": "M0",
    "S1": "M12",
    "T1": "M12",
    "S2": "M18",
    "T2": "M18",
    "S3": "M24",
    "T3": "M24",
    "S4": "M36",
    "T4": "M36",
}

EVIDENCE_TIME_ROLES = {
    "prior_baseline": "当前项目里程碑之前已经形成的版本、数据、论文、实验、平台和能力边界",
    "current_window_increment": "从上一项目里程碑到当前项目里程碑之间真正新增的能力、实验、结果和使用",
    "subsequent_effect": "当前项目里程碑之后形成的同行认可、真实使用、持续维护和长期影响；不得反向证明当前节点当时领先",
}

EVIDENCE_TIME_ROLE_LABELS = {
    "prior_baseline": "当前节点之前的基础",
    "current_window_increment": "当前评价窗口内的新增",
    "subsequent_effect": "当前节点之后形成的影响",
}


def normalize_milestone_code(value: Any) -> str:
    raw = str(value or "").strip().upper()
    if not raw:
        return ""
    if raw in LEGACY_STAGE_ALIASES:
        return LEGACY_STAGE_ALIASES[raw]
    match = re.fullmatch(r"M\s*[-_]?\s*(\d+)", raw)
    return f"M{int(match.group(1))}" if match else ""


def build_milestone_context(
    profile: dict[str, Any] | None,
    expected: dict[str, Any] | None = None,
) -> dict[str, Any]:
    profile = profile or {}
    expected = expected or {}
    custom_entries: list[Any] = []
    for source in (profile, expected):
        for field in ("milestone_axis", "project_milestones", "milestones"):
            custom_entries.extend(_as_entries(source.get(field)))

    labels: dict[str, str] = {
        code: label for code, label in zip(
            DEFAULT_MILESTONE_CODES,
            ("项目基线", "第一年度节点", "阶段评议", "中期节点", "项目完成节点"),
        )
    }
    codes = set(DEFAULT_MILESTONE_CODES)
    for entry in custom_entries:
        raw_code = entry
        label = ""
        if isinstance(entry, dict):
            raw_code = (
                entry.get("code") or entry.get("milestone") or entry.get("milestone_code")
                or entry.get("stage") or entry.get("id")
            )
            label = str(entry.get("name") or entry.get("label") or entry.get("title") or "").strip()
        code = normalize_milestone_code(raw_code)
        if code:
            codes.add(code)
            if label:
                labels[code] = label

    current_code = ""
    source_field = ""
    source_code = ""
    for source_name, source in (("project_profile", profile), ("expected_level_assessment", expected)):
        for field in ("current_milestone", "assessment_milestone", "milestone"):
            raw = source.get(field)
            code = normalize_milestone_code(raw)
            if code:
                current_code = code
                source_field = f"{source_name}.{field}"
                source_code = str(raw)
                break
        if current_code:
            break
    if not current_code:
        # Legacy T/S stage fields describe an assessment category, not a
        # project-month milestone. They remain in the source profile for audit
        # but must never silently move the active point on the M axis.
        for source_name, source in (("project_profile", profile), ("expected_level_assessment", expected)):
            for field in ("assessment_stage", "stage", "stage_code"):
                raw = str(source.get(field) or "").strip().upper()
                if raw.startswith("M"):
                    current_code = normalize_milestone_code(raw)
                    source_field = f"{source_name}.{field}"
                    source_code = str(source.get(field) or "")
                    break
            if current_code:
                break
    if not current_code:
        current_code = DEFAULT_CURRENT_MILESTONE
        source_field = "configured_default"
        source_code = DEFAULT_CURRENT_MILESTONE
    codes.add(current_code)

    ordered = sorted(codes, key=_milestone_month)
    current_index = ordered.index(current_code)
    axis = [
        {
            "code": code,
            "month": _milestone_month(code),
            "label": labels.get(code) or f"项目第{_milestone_month(code)}个月节点",
            "prescribed": code in DEFAULT_MILESTONE_CODES,
            "custom": code not in DEFAULT_MILESTONE_CODES,
            "current": code == current_code,
        }
        for code in ordered
    ]
    previous_code = ordered[current_index - 1] if current_index > 0 else ""
    next_code = ordered[current_index + 1] if current_index + 1 < len(ordered) else ""
    return {
        "schema_version": "project-milestone-axis.v1",
        "axis": axis,
        "codes": ordered,
        "current_milestone": current_code,
        "previous_milestone": previous_code,
        "next_milestone": next_code,
        "evaluation_window": {
            "from": previous_code or "项目启动前",
            "to": current_code,
        },
        "source_field": source_field,
        "source_code": source_code,
        "governance": "M0、M12、M18、M24、M36为规定节点；允许增加M6、M9、M30等项目自定义节点。成果、评价依据和评价标准必须绑定同一当前项目里程碑。",
    }


def bind_to_current_milestone(value: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    result = dict(value)
    result["milestone_code"] = str(context.get("current_milestone") or "M0")
    result["evaluation_window"] = dict(context.get("evaluation_window") or {})
    return result


def _as_entries(value: Any) -> list[Any]:
    if isinstance(value, (list, tuple, set)):
        return list(value)
    if isinstance(value, dict):
        if isinstance(value.get("axis"), list):
            return list(value["axis"])
        return [{"code": key, "label": label} for key, label in value.items()]
    if isinstance(value, str):
        return [part for part in re.split(r"[,，;；\s]+", value) if part]
    return []


def _milestone_month(code: str) -> int:
    match = re.fullmatch(r"M(\d+)", code)
    return int(match.group(1)) if match else 10**9


__all__ = [
    "DEFAULT_MILESTONE_CODES",
    "DEFAULT_CURRENT_MILESTONE",
    "EVIDENCE_TIME_ROLES",
    "EVIDENCE_TIME_ROLE_LABELS",
    "LEGACY_STAGE_ALIASES",
    "bind_to_current_milestone",
    "build_milestone_context",
    "normalize_milestone_code",
]
