from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Iterable


def read_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def read_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8-sig") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}: line {line_number} is not valid JSON") from exc
            if not isinstance(value, dict):
                raise ValueError(f"{path}: line {line_number} must be a JSON object")
            rows.append(value)
    return rows


def read_csv(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_json(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: str | Path, rows: Iterable[dict[str, Any]]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_csv(path: str | Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def normalized(value: Any) -> str:
    if isinstance(value, str):
        return " ".join(value.strip().lower().split())
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_id(value: Any, prefix: str) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{prefix}_{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_keys(value: dict[str, Any], keys: Iterable[str], context: str) -> None:
    missing = [key for key in keys if key not in value]
    if missing:
        raise ValueError(f"{context} missing required fields: {', '.join(missing)}")


def require_unique_ids(rows: list[dict[str, Any]], context: str) -> set[str]:
    ids: list[str] = []
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            raise ValueError(f"{context}[{index}] must be an object")
        value = str(row.get("id", "")).strip()
        if not value:
            raise ValueError(f"{context}[{index}] must have a non-empty id")
        ids.append(value)
    if len(ids) != len(set(ids)):
        duplicates = sorted({value for value in ids if ids.count(value) > 1})
        raise ValueError(f"{context} IDs must be unique: {duplicates}")
    return set(ids)


def finite_number(value: Any, context: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{context} must be a finite number")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{context} must be a finite number") from exc
    if not math.isfinite(number):
        raise ValueError(f"{context} must be a finite number")
    return number
