from __future__ import annotations

from pathlib import Path
from typing import Any

from .common import finite_number, file_sha256, read_json, require_keys, require_unique_ids, write_csv, write_json
from .reports import render_attribution_report, render_unresolved_report


_SEARCH_CATEGORIES = {
    "conflicts": "查到但冲突",
    "not_found": "已检索仍查不到",
    "needs_expert": "需要专业判断",
}


def _validate(data: dict[str, Any]) -> None:
    require_keys(data, ["schema_version", "project", "target", "evidence", "factors", "comparisons", "claims"], "attribution input")
    if data["schema_version"] != "dca-attribution-input/v1":
        raise ValueError(f"unsupported attribution schema_version: {data['schema_version']}")
    if not isinstance(data["project"], dict) or not isinstance(data["target"], dict):
        raise ValueError("project and target must be objects")
    require_keys(data["project"], ["id", "name"], "project")
    require_keys(data["target"], ["id", "name"], "target")
    for field in ("evidence", "factors", "comparisons", "claims"):
        if not isinstance(data[field], list):
            raise ValueError(f"{field} must be an array")
    if not data["factors"]:
        raise ValueError("factors must be a non-empty array")
    evidence_ids = require_unique_ids(data["evidence"], "evidence")
    factor_ids = require_unique_ids(data["factors"], "factors")
    comparison_ids = require_unique_ids(data["comparisons"], "comparisons")
    claim_ids = require_unique_ids(data["claims"], "claims")
    del comparison_ids
    for comparison in data["comparisons"]:
        require_keys(comparison, ["id", "name", "baseline", "observed", "direction", "comparability_status", "evidence_ids", "involved_factor_ids", "isolated_factor_ids"], f"comparison {comparison.get('id', '')}")
        if comparison["direction"] not in {"lower_is_better", "higher_is_better", "descriptive_only"}:
            raise ValueError(f"comparison {comparison['id']} has unsupported direction")
        if comparison["comparability_status"] not in {"established", "partial", "unknown"}:
            raise ValueError(f"comparison {comparison['id']} has unsupported comparability_status")
        for side in ("baseline", "observed"):
            if not isinstance(comparison[side], dict):
                raise ValueError(f"comparison {comparison['id']} {side} must be an object")
            require_keys(comparison[side], ["value"], f"comparison {comparison['id']} {side}")
            finite_number(comparison[side]["value"], f"comparison {comparison['id']} {side}.value")
        baseline_unit = str(comparison["baseline"].get("unit", "")).strip()
        observed_unit = str(comparison["observed"].get("unit", "")).strip()
        if baseline_unit and observed_unit and baseline_unit != observed_unit:
            raise ValueError(f"comparison {comparison['id']} uses inconsistent units")
        unknown_evidence = set(comparison["evidence_ids"]) - evidence_ids
        unknown_factors = (set(comparison["involved_factor_ids"]) | set(comparison["isolated_factor_ids"])) - factor_ids
        if unknown_evidence:
            raise ValueError(f"comparison {comparison['id']} references unknown evidence: {sorted(unknown_evidence)}")
        if unknown_factors:
            raise ValueError(f"comparison {comparison['id']} references unknown factors: {sorted(unknown_factors)}")
        if set(comparison["isolated_factor_ids"]) - set(comparison["involved_factor_ids"]):
            raise ValueError(f"comparison {comparison['id']} isolates a factor that is not listed as involved")
    for claim in data["claims"]:
        require_keys(claim, ["id", "text", "evidence_ids"], f"claim {claim.get('id', '')}")
        if claim.get("factor_id") and claim["factor_id"] not in factor_ids:
            raise ValueError(f"claim {claim['id']} references unknown factor {claim['factor_id']}")
        if set(claim.get("evidence_ids", [])) - evidence_ids:
            raise ValueError(f"claim {claim['id']} references unknown evidence")
    search_findings = data.get("search_findings", [])
    if not isinstance(search_findings, list):
        raise ValueError("search_findings must be an array")
    search_ids = require_unique_ids(search_findings, "search_findings")
    for finding in search_findings:
        require_keys(finding, ["id", "status", "statement", "reason"], f"search finding {finding.get('id', '')}")
        if finding.get("status") not in _SEARCH_CATEGORIES:
            raise ValueError(f"search finding {finding.get('id', '')} has unsupported status")
        if set(finding.get("related_claim_ids", [])) - claim_ids:
            raise ValueError(f"search finding {finding.get('id', '')} references unknown claims")
        if set(finding.get("evidence_ids", [])) - evidence_ids:
            raise ValueError(f"search finding {finding.get('id', '')} references unknown evidence")
    additional = data.get("additional_unresolved_items", [])
    if not isinstance(additional, list):
        raise ValueError("additional_unresolved_items must be an array")
    additional_ids = require_unique_ids(additional, "additional_unresolved_items")
    if search_ids & additional_ids:
        raise ValueError("search finding and additional unresolved item IDs must not overlap")


def _calculate_comparison(comparison: dict[str, Any]) -> dict[str, Any]:
    baseline = finite_number(comparison["baseline"]["value"], f"comparison {comparison['id']} baseline.value")
    observed = finite_number(comparison["observed"]["value"], f"comparison {comparison['id']} observed.value")
    direction = comparison["direction"]
    if baseline == 0:
        percent_change = None
        ratio = None
    else:
        if direction == "lower_is_better":
            percent_change = (baseline - observed) / baseline * 100
            ratio = baseline / observed - 1 if observed else None
        elif direction == "higher_is_better":
            percent_change = (observed - baseline) / abs(baseline) * 100
            ratio = observed / baseline - 1
        elif direction == "descriptive_only":
            percent_change = (observed - baseline) / abs(baseline) * 100
            ratio = observed / baseline - 1
        else:
            raise ValueError(f"comparison {comparison['id']} has unsupported direction {direction}")
    if direction == "descriptive_only":
        effect_outcome = "descriptive"
    elif direction == "lower_is_better":
        effect_outcome = "improved" if observed < baseline else "worsened" if observed > baseline else "no_change"
    else:
        effect_outcome = "improved" if observed > baseline else "worsened" if observed < baseline else "no_change"
    return {
        "id": comparison["id"],
        "name": comparison["name"],
        "baseline_label": comparison["baseline"].get("label", "baseline"),
        "baseline_value": baseline,
        "observed_label": comparison["observed"].get("label", "observed"),
        "observed_value": observed,
        "unit": comparison["observed"].get("unit") or comparison["baseline"].get("unit", ""),
        "direction": comparison["direction"],
        "comparability_status": comparison["comparability_status"],
        "effect_outcome": effect_outcome,
        "absolute_difference": round(observed - baseline, 8),
        "percent_change_from_baseline": round(percent_change, 8) if percent_change is not None else None,
        "ratio_change": round(ratio, 8) if ratio is not None else None,
        "involved_factor_ids": comparison["involved_factor_ids"],
        "isolated_factor_ids": comparison["isolated_factor_ids"],
        "evidence_ids": comparison["evidence_ids"],
        "notes": comparison.get("notes", ""),
    }


def _factor_results(data: dict[str, Any], comparisons: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for factor in data["factors"]:
        factor_id = factor["id"]
        role_in_attribution = factor.get("role_in_attribution", "contributor")
        isolated_by = [item["id"] for item in comparisons if factor_id in item["isolated_factor_ids"]]
        positive_isolated = [item for item in comparisons if factor_id in item["isolated_factor_ids"] and item["effect_outcome"] == "improved"]
        established_by = [item["id"] for item in positive_isolated if item["comparability_status"] == "established"]
        conditional_by = [item["id"] for item in positive_isolated if item["comparability_status"] == "partial"]
        unknown_by = [item["id"] for item in positive_isolated if item["comparability_status"] == "unknown"]
        nonpositive_by = [item["id"] for item in comparisons if factor_id in item["isolated_factor_ids"] and item["effect_outcome"] in {"no_change", "worsened"}]
        descriptive_by = [item["id"] for item in comparisons if factor_id in item["isolated_factor_ids"] and item["effect_outcome"] == "descriptive"]
        involved_in = [item["id"] for item in comparisons if factor_id in item["involved_factor_ids"]]
        factor_claims = [claim for claim in data["claims"] if claim.get("factor_id") == factor_id]
        evidence_ids = sorted({evidence_id for claim in factor_claims for evidence_id in claim.get("evidence_ids", [])})
        if role_in_attribution == "baseline":
            status = "baseline_reference"
            conclusion = "该因素是本次比较的基线路线，不作为待证明的独立贡献因素。"
        elif established_by:
            status = "direct_increment_supported"
            conclusion = "现有比较在已锁定的条件下单独考察了该因素，可支持所列范围内的增量判断。"
        elif conditional_by:
            status = "conditional_increment_supported"
            conclusion = "现有比较单独考察了该因素，但比较条件尚未完全锁定，只能形成有条件的增量判断。"
        elif nonpositive_by:
            status = "no_positive_increment_observed"
            conclusion = "现有比较单独考察了该因素，但没有观察到正向改善，因此不支持正向独立增量。"
        elif descriptive_by:
            status = "isolated_effect_observed"
            conclusion = "现有比较单独记录了该因素相关变化，但该指标仅用于描述，不能据此认定正向独立增量。"
        elif unknown_by:
            status = "increment_not_confirmed_due_to_comparability"
            conclusion = "比较虽单独考察了该因素且结果方向为改善，但可比性尚未确认，不能据此支持独立增量。"
        elif involved_in or evidence_ids:
            status = "participation_supported_increment_not_isolated"
            conclusion = "现有材料支持该因素参与，但独立增量尚未在方向正确且可比条件充分的比较中得到确认。"
        else:
            status = "not_established"
            conclusion = "现有结构化材料尚未建立该因素与观察结果的可核验联系。"
        results.append({
            "factor_id": factor_id,
            "factor_name": factor["name"],
            "factor_type": factor.get("type", "other"),
            "role": factor.get("role", ""),
            "status": status,
            "conclusion": conclusion,
            "isolated_by_comparison_ids": isolated_by,
            "established_by_comparison_ids": established_by,
            "conditional_by_comparison_ids": conditional_by,
            "unknown_by_comparison_ids": unknown_by,
            "nonpositive_by_comparison_ids": nonpositive_by,
            "descriptive_by_comparison_ids": descriptive_by,
            "involved_in_comparison_ids": involved_in,
            "evidence_ids": evidence_ids,
            "evaluate_independent_increment": factor.get("evaluate_independent_increment", False),
            "role_in_attribution": role_in_attribution,
        })
    return results


def _unresolved_items(data: dict[str, Any], factor_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unresolved: list[dict[str, Any]] = []
    for finding in data.get("search_findings", []):
        unresolved.append({
            "id": finding["id"],
            "category": _SEARCH_CATEGORIES[finding["status"]],
            "object": data["target"]["name"],
            "known_fact": finding.get("project_statement", ""),
            "external_finding": finding.get("statement", ""),
            "unresolved_question": finding.get("question", ""),
            "reason": finding.get("reason", ""),
            "related_claim_ids": finding.get("related_claim_ids", []),
            "evidence_ids": finding.get("evidence_ids", []),
        })

    for factor in factor_results:
        if factor["status"] not in {
            "participation_supported_increment_not_isolated",
            "conditional_increment_supported",
            "increment_not_confirmed_due_to_comparability",
        }:
            continue
        if not factor["evaluate_independent_increment"]:
            continue
        item_id = f"UNRESOLVED-{factor['factor_id']}"
        if any(item["id"] == item_id for item in unresolved):
            continue
        factor_claim_ids = {
            claim["id"] for claim in data["claims"] if claim.get("factor_id") == factor["factor_id"]
        }
        if any(factor_claim_ids & set(item.get("related_claim_ids", [])) for item in unresolved):
            continue
        if factor["status"] == "conditional_increment_supported":
            reason = "比较条件仅部分可比，尚不足以形成无条件的独立增量判断。"
        elif factor["status"] == "increment_not_confirmed_due_to_comparability":
            reason = "比较的同条件基础尚未确认，即使结果方向为改善也不能归因于该因素。"
        else:
            reason = "现有比较同时包含多个因素，尚未分离该因素的独立贡献。"
        unresolved.append({
            "id": item_id,
            "category": "需要专业判断",
            "object": data["target"]["name"],
            "known_fact": f"现有材料支持{factor['factor_name']}参与。",
            "external_finding": "",
            "unresolved_question": f"在固定其他因素后，现有比较是否足以证明{factor['factor_name']}带来了独立增量？",
            "reason": reason,
            "related_claim_ids": [],
            "evidence_ids": factor["evidence_ids"],
        })

    for item in data.get("additional_unresolved_items", []):
        require_keys(item, ["id", "category", "unresolved_question", "reason"], "additional unresolved item")
        if item["category"] not in set(_SEARCH_CATEGORIES.values()):
            raise ValueError(f"unsupported unresolved category: {item['category']}")
        unresolved.append({
            "object": data["target"]["name"],
            "known_fact": "",
            "external_finding": "",
            "related_claim_ids": [],
            "evidence_ids": [],
            **item,
        })
    return unresolved


def run_attribution(input_path: str | Path, output_dir: str | Path) -> dict[str, Any]:
    """Generate bounded contribution attribution from structured evidence and Search findings."""
    data = read_json(input_path)
    _validate(data)
    comparisons = [_calculate_comparison(item) for item in data["comparisons"]]
    factor_results = _factor_results(data, comparisons)
    unresolved = _unresolved_items(data, factor_results)
    direct = [item["factor_name"] for item in factor_results if item["status"] == "direct_increment_supported"]
    conditional = [item["factor_name"] for item in factor_results if item["status"] == "conditional_increment_supported"]
    unconfirmed = [item["factor_name"] for item in factor_results if item["status"] == "increment_not_confirmed_due_to_comparability"]
    participating = [item["factor_name"] for item in factor_results if item["status"] == "participation_supported_increment_not_isolated" and item["role_in_attribution"] != "baseline"]
    conclusion_parts: list[str] = []
    if direct:
        conclusion_parts.append("在已锁定比较条件下支持增量的因素：" + "、".join(direct))
    if conditional:
        conclusion_parts.append("比较条件尚未完全锁定的增量因素：" + "、".join(conditional))
    if unconfirmed:
        conclusion_parts.append("因可比性不足而不能确认增量的因素：" + "、".join(unconfirmed))
    if participating:
        conclusion_parts.append("已确认参与但尚未分离独立增量的因素：" + "、".join(participating))
    if not conclusion_parts:
        conclusion_parts.append("现有结构化证据尚不足以形成因素级增量判断")

    result = {
        "schema_version": "dca-attribution-result/v1",
        "status": "completed",
        "project": data["project"],
        "target": data["target"],
        "factor_results": factor_results,
        "comparison_results": comparisons,
        "claims": data["claims"],
        "evidence_index": data["evidence"],
        "summary": "；".join(conclusion_parts) + "。",
        "boundary": "本结果基于已提供的结构化项目证据、比较基线和外部Search发现，只形成辅助归因判断；因素未被隔离、结果未改善或可比性不足时，均不得表述为正向独立净贡献。",
        "input_sha256": file_sha256(input_path),
    }
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    write_json(output / "contribution_result.json", result)
    write_json(output / "unresolved_items.json", {
        "schema_version": "dca-unresolved-items/v1",
        "project": data["project"],
        "target": data["target"],
        "items": unresolved,
        "input_sha256": result["input_sha256"],
    })
    write_csv(output / "contribution_result.csv", factor_results, [
        "factor_id", "factor_name", "factor_type", "role", "role_in_attribution",
        "evaluate_independent_increment", "status", "conclusion",
        "isolated_by_comparison_ids", "established_by_comparison_ids",
        "conditional_by_comparison_ids", "unknown_by_comparison_ids",
        "nonpositive_by_comparison_ids", "descriptive_by_comparison_ids",
        "involved_in_comparison_ids", "evidence_ids",
    ])
    write_csv(output / "unresolved_items.csv", unresolved, [
        "id", "category", "object", "known_fact", "external_finding", "unresolved_question",
        "reason", "related_claim_ids", "evidence_ids",
    ])
    render_attribution_report(output / "AI贡献归因结果.html", result)
    render_unresolved_report(output / "未解决事项与矛盾冲突.html", data["project"], data["target"], unresolved)
    manifest = {
        "schema_version": "dca-attribution-run/v1",
        "status": "completed",
        "input_sha256": result["input_sha256"],
        "factor_count": len(factor_results),
        "comparison_count": len(comparisons),
        "unresolved_count": len(unresolved),
        "outputs": [
            "contribution_result.json", "contribution_result.csv", "AI贡献归因结果.html",
            "unresolved_items.json", "unresolved_items.csv", "未解决事项与矛盾冲突.html",
        ],
    }
    write_json(output / "run_manifest.json", manifest)
    return manifest
