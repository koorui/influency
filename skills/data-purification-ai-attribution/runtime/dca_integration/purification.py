from __future__ import annotations

import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any

from .common import (
    finite_number,
    file_sha256,
    normalized,
    read_csv,
    read_json,
    read_jsonl,
    require_keys,
    stable_id,
    write_json,
    write_jsonl,
)
from .reports import render_purification_report


def _tuple_key(row: dict[str, Any], fields: list[str]) -> tuple[str, ...]:
    return tuple(normalized(row.get(field)) for field in fields)


def _pearson(xs: list[float], ys: list[float]) -> float:
    if len(xs) < 3 or len(xs) != len(ys):
        return 0.0
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    dx = [value - mx for value in xs]
    dy = [value - my for value in ys]
    denominator = math.sqrt(sum(value * value for value in dx) * sum(value * value for value in dy))
    return sum(left * right for left, right in zip(dx, dy)) / denominator if denominator else 0.0


def _hamming(left: list[float | None], right: list[float | None]) -> float:
    pairs = [(a, b) for a, b in zip(left, right) if a is not None and b is not None]
    return sum(a != b for a, b in pairs) / len(pairs) if pairs else 0.0


def _validate_config(config: dict[str, Any]) -> None:
    if config.get("schema_version") != "dca-purification-config/v1":
        raise ValueError("unsupported purification config schema_version")
    require_keys(config, ["dataset"], "purification config")
    dataset = config["dataset"]
    require_keys(dataset, ["id_field", "required_fields", "dedupe_fields"], "dataset config")
    if not isinstance(dataset["required_fields"], list) or not dataset["required_fields"]:
        raise ValueError("dataset.required_fields must be a non-empty array")
    if not isinstance(dataset["dedupe_fields"], list) or not dataset["dedupe_fields"]:
        raise ValueError("dataset.dedupe_fields must be a non-empty array")
    selection = config.get("selection")
    if selection:
        require_keys(selection, ["item_id_field", "model_id_field", "score_field", "target_size"], "selection config")
        if not isinstance(selection["target_size"], int) or isinstance(selection["target_size"], bool) or selection["target_size"] < 1:
            raise ValueError("selection.target_size must be a positive integer")


def _quality_filter(
    records: list[dict[str, Any]],
    config: dict[str, Any],
    references: list[dict[str, Any]],
) -> dict[str, Any]:
    spec = config["dataset"]
    findings: dict[int, list[dict[str, Any]]] = defaultdict(list)

    def add(index: int, code: str, severity: str, action: str, message: str, evidence: dict[str, Any] | None = None) -> None:
        findings[index].append({
            "code": code,
            "severity": severity,
            "recommended_action": action,
            "message": message,
            "evidence": evidence or {},
        })

    for index, row in enumerate(records):
        for field in spec["required_fields"]:
            if field not in row or row[field] in (None, "", []):
                add(index, "required_field_missing", "error", "quarantine", f"Required field {field} is missing", {"field": field})
        for field, expected in spec.get("field_types", {}).items():
            if field not in row:
                continue
            valid = {
                "string": isinstance(row[field], str),
                "array": isinstance(row[field], list),
                "integer": isinstance(row[field], int) and not isinstance(row[field], bool),
                "number": isinstance(row[field], (int, float)) and not isinstance(row[field], bool),
            }.get(expected, True)
            if not valid:
                add(index, "field_type_invalid", "error", "quarantine", f"Field {field} has invalid type", {"field": field, "expected": expected})
        label_field = spec.get("label_field")
        allowed_labels = spec.get("allowed_labels")
        if label_field and allowed_labels and row.get(label_field) not in allowed_labels:
            add(index, "label_not_allowed", "error", "quarantine", "Label is outside the allowed set", {"value": row.get(label_field)})

    similarity_fields = spec.get("similarity_fields", [])
    label_field = spec.get("label_field")
    content_fields = [field for field in similarity_fields if field != label_field]
    if content_fields and label_field:
        groups: dict[tuple[str, ...], list[int]] = defaultdict(list)
        for index, row in enumerate(records):
            if all(row.get(field) not in (None, "", []) for field in content_fields):
                groups[_tuple_key(row, content_fields)].append(index)
        for indices in groups.values():
            labels = {normalized(records[index].get(label_field)) for index in indices}
            if len(indices) > 1 and len(labels) > 1:
                for index in indices:
                    add(index, "label_conflict", "error", "quarantine", "Equivalent content has conflicting labels")

    exact_seen: dict[tuple[str, ...], int] = {}
    for index, row in enumerate(records):
        key = _tuple_key(row, spec["dedupe_fields"])
        if key in exact_seen:
            add(index, "exact_duplicate", "error", "drop", "Exact duplicate", {"matched_source_row": exact_seen[key] + 1})
        else:
            exact_seen[key] = index

    overlap_fields = spec.get("overlap_fields", [])
    if overlap_fields and references:
        reference_keys = {_tuple_key(row, overlap_fields) for row in references}
        for index, row in enumerate(records):
            if _tuple_key(row, overlap_fields) in reference_keys:
                add(index, "reference_exact_overlap", "error", "quarantine", "Record overlaps the configured reference set")

    audit: list[dict[str, Any]] = []
    kept: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    removed: list[dict[str, Any]] = []
    for index, row in enumerate(records):
        row_findings = findings.get(index, [])
        actions = {item["recommended_action"] for item in row_findings}
        action = "drop" if "drop" in actions and "quarantine" not in actions else "quarantine" if "quarantine" in actions else "keep"
        record_id = stable_id(row, "record")
        audit_row = {
            "record_id": record_id,
            "source_row": index + 1,
            "source_id": row.get(spec["id_field"], ""),
            "action": action,
            "reason_codes": sorted({item["code"] for item in row_findings}),
            "findings": row_findings,
        }
        audit.append(audit_row)
        output_row = {**row, "_purification": {"record_id": record_id, "action": action, "reason_codes": audit_row["reason_codes"]}}
        {"keep": kept, "quarantine": quarantined, "drop": removed}[action].append(output_row)
    return {"audit": audit, "kept": kept, "quarantined": quarantined, "removed": removed}


def _select_benchmark(
    kept: list[dict[str, Any]],
    responses: list[dict[str, str]],
    split: dict[str, Any],
    selection: dict[str, Any],
) -> dict[str, Any]:
    require_keys(selection, ["item_id_field", "model_id_field", "score_field", "target_size"], "selection config")
    item_id_field = selection["item_id_field"]
    model_id_field = selection["model_id_field"]
    response_item_field = selection.get("response_item_id_field", item_id_field)
    score_field = selection["score_field"]
    item_ids: list[str] = []
    for index, row in enumerate(kept, 1):
        if item_id_field not in row or str(row[item_id_field]).strip() == "":
            raise ValueError(f"kept record {index} is missing selection item ID field {item_id_field}")
        item_ids.append(str(row[item_id_field]))
    if len(item_ids) != len(set(item_ids)):
        duplicates = sorted({item_id for item_id in item_ids if item_ids.count(item_id) > 1})
        raise ValueError(f"selection item IDs must be unique: {duplicates}")
    kept_by_id = {item_id: row for item_id, row in zip(item_ids, kept)}
    require_keys(split, ["train_models"], "model split")
    train_models = [str(value) for value in split["train_models"]]
    validation_models = [str(value) for value in split.get("validation_models", [])]
    if not train_models:
        raise ValueError("train_models must be a non-empty array")
    if len(train_models) != len(set(train_models)) or len(validation_models) != len(set(validation_models)):
        raise ValueError("model IDs must be unique within each split")
    if set(train_models) & set(validation_models):
        raise ValueError("train_models and validation_models must not overlap")

    response_map: dict[str, dict[str, float]] = defaultdict(dict)
    seen_responses: set[tuple[str, str]] = set()
    for index, row in enumerate(responses, 2):
        missing = [field for field in (response_item_field, model_id_field, score_field) if field not in row or row[field] == ""]
        if missing:
            raise ValueError(f"responses.csv row {index} missing fields: {', '.join(missing)}")
        item_id = str(row[response_item_field])
        model_id = str(row[model_id_field])
        pair = (item_id, model_id)
        if pair in seen_responses:
            raise ValueError(f"duplicate response for item/model pair: {pair}")
        seen_responses.add(pair)
        if item_id in kept_by_id:
            response_map[item_id][model_id] = finite_number(row[score_field], f"responses.csv row {index} score")

    metrics: list[dict[str, Any]] = []
    for item_id, item in kept_by_id.items():
        values = [response_map[item_id].get(model) for model in train_models]
        pairs: list[tuple[float, float]] = []
        for value, model in zip(values, train_models):
            other_values = [scores[model] for other_id, scores in response_map.items() if other_id != item_id and model in scores]
            if value is not None and other_values:
                pairs.append((value, sum(other_values)))
        xs = [left for left, _ in pairs]
        ys = [right for _, right in pairs]
        variance = statistics.pvariance(xs) if len(xs) > 1 else 0.0
        discrimination = _pearson(xs, ys)
        eligible = (
            len(xs) >= int(selection.get("min_responses", 3))
            and variance >= float(selection.get("min_variance", 0.0))
            and discrimination >= float(selection.get("min_discrimination", -1.0))
        )
        metrics.append({
            "item_id": item_id,
            "group": str(item.get(selection.get("group_field", "group"), "ungrouped")),
            "response_count": len(xs),
            "accuracy": round(statistics.fmean(xs), 8) if xs else 0.0,
            "variance": round(variance, 8),
            "discrimination": round(discrimination, 8),
            "eligible": eligible,
            "response_vector": values,
        })

    eligible = [row for row in metrics if row["eligible"]]
    target_size = int(selection["target_size"])
    if len(eligible) < target_size:
        raise ValueError(f"selection requires {target_size} eligible items but only {len(eligible)} are available")
    selected: list[dict[str, Any]] = []
    reasons: dict[str, dict[str, Any]] = {}
    if selection.get("ensure_group_coverage", True):
        groups = sorted({row["group"] for row in eligible})
        if len(groups) > target_size:
            raise ValueError(
                f"group coverage requires at least {len(groups)} selected items, exceeding target_size {target_size}"
            )
        for group in groups:
            candidates = [row for row in eligible if row["group"] == group]
            all_in_group = [row for row in metrics if row["group"] == group]
            representative = min(
                candidates,
                key=lambda candidate: (
                    sum(_hamming(candidate["response_vector"], other["response_vector"]) for other in all_in_group),
                    -candidate["discrimination"],
                    candidate["item_id"],
                ),
            )
            selected.append(representative)
            reasons[representative["item_id"]] = {"type": "group_coverage_representative", "group": group}

    def total_distance(medoids: list[dict[str, Any]]) -> float:
        if not medoids:
            return float("inf")
        return sum(min(_hamming(item["response_vector"], medoid["response_vector"]) for medoid in medoids) for item in metrics)

    while len(selected) < target_size:
        remaining = [row for row in eligible if row not in selected]
        if not remaining:
            break
        before = total_distance(selected)
        candidate = min(remaining, key=lambda row: (total_distance(selected + [row]), -row["discrimination"], row["item_id"]))
        selected.append(candidate)
        reasons[candidate["item_id"]] = {"type": "behavioral_representative", "distance_reduction": round(before - total_distance(selected), 8) if math.isfinite(before) else None}

    selected_rows: list[dict[str, Any]] = []
    for rank, metric in enumerate(selected[:target_size], 1):
        selected_rows.append({
            **kept_by_id[metric["item_id"]],
            "_selection": {
                "rank": rank,
                "response_count": metric["response_count"],
                "accuracy": metric["accuracy"],
                "variance": metric["variance"],
                "discrimination": metric["discrimination"],
                "reason": reasons[metric["item_id"]],
            },
        })
    return {
        "selected": selected_rows,
        "eligible_count": len(eligible),
        "metrics": [{key: value for key, value in row.items() if key != "response_vector"} for row in metrics],
        "split": {"train_models": train_models, "validation_models": validation_models},
    }


def run_purification(
    records_path: str | Path,
    config_path: str | Path,
    output_dir: str | Path,
    *,
    references_path: str | Path | None = None,
    responses_path: str | Path | None = None,
    split_path: str | Path | None = None,
) -> dict[str, Any]:
    """Run quality purification and optional high-discrimination selection."""
    config = read_json(config_path)
    _validate_config(config)
    records = read_jsonl(records_path)
    id_field = config["dataset"]["id_field"]
    source_ids = [str(row.get(id_field, "")).strip() for row in records]
    nonempty_ids = [value for value in source_ids if value]
    if len(nonempty_ids) != len(set(nonempty_ids)):
        duplicates = sorted({value for value in nonempty_ids if nonempty_ids.count(value) > 1})
        raise ValueError(f"record IDs must be unique: {duplicates}")
    references = read_jsonl(references_path) if references_path else []
    result = _quality_filter(records, config, references)
    selection_result: dict[str, Any] | None = None
    selection_config = config.get("selection")
    if selection_config:
        if not responses_path or not split_path:
            raise ValueError("responses_path and split_path are required when selection is configured")
        selection_result = _select_benchmark(result["kept"], read_csv(responses_path), read_json(split_path), selection_config)

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    write_jsonl(output / "purified.jsonl", result["kept"])
    write_jsonl(output / "quarantine.jsonl", result["quarantined"])
    write_jsonl(output / "removed.jsonl", result["removed"])
    write_jsonl(output / "audit.jsonl", result["audit"])
    if selection_result is not None:
        write_jsonl(output / "selected_samples.jsonl", selection_result["selected"])
        write_json(output / "selection_report.json", selection_result)

    summary = {
        "schema_version": "dca-purification-result/v1",
        "status": "completed",
        "counts": {
            "input": len(records),
            "kept": len(result["kept"]),
            "quarantined": len(result["quarantined"]),
            "removed": len(result["removed"]),
            "eligible": selection_result["eligible_count"] if selection_result else None,
            "selected": len(selection_result["selected"]) if selection_result else None,
        },
        "input_hashes": {
            "records": file_sha256(records_path),
            "config": file_sha256(config_path),
            "references": file_sha256(references_path) if references_path else None,
            "responses": file_sha256(responses_path) if responses_path else None,
            "split": file_sha256(split_path) if split_path else None,
        },
        "outputs": {
            "purified": "purified.jsonl",
            "quarantine": "quarantine.jsonl",
            "removed": "removed.jsonl",
            "audit": "audit.jsonl",
            "selected_samples": "selected_samples.jsonl" if selection_result else None,
            "selection_report": "selection_report.json" if selection_result else None,
            "report": "数据提纯结果.html",
        },
    }
    write_json(output / "purification_result.json", summary)
    render_purification_report(output / "数据提纯结果.html", summary, selection_result)
    return summary
