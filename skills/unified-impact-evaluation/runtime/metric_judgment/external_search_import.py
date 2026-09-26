from __future__ import annotations

import csv
import io
import shutil
import subprocess
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any


ARCHIVES = {
    "P01": {
        "file": "力学研究.rar",
        "claims": "*/search_validation/claims_summary.csv",
        "index": "*/search_validation/evidence_index.csv",
        "manifest": "*/search_validation/evidence_manifest.csv",
        "project_manifest": "*/search_validation/project_source_manifest.csv",
        "report": "*/search_validation/search验证报告.md",
    },
    "P02": {
        "file": "有机化学.rar",
        "claims": "*/search_validation/claim_verification.csv",
        "index": "",
        "manifest": "",
        "project_manifest": "",
        "report": "*/search_validation/search_validation_report.md",
    },
}


P01_CLAIM_SOURCE_MAP = {
    "SV-01": ["E14", "E14A"],
    "SV-02": ["E01", "E02", "E03", "E04", "E05"],
    "SV-03": ["E06", "E07", "E08", "E32"],
    "SV-04": ["E09", "E10", "E11", "E12", "E13", "E31"],
    "SV-05": ["E15", "E16", "E17", "E18"],
    "SV-06": ["E19"],
    "SV-07": ["E19"],
    "SV-08": ["E19"],
    "SV-09": ["E20", "E21", "E22"],
    "SV-10": ["E20", "E21", "E22", "E23"],
    "SV-11": ["E24"],
    "SV-12": ["E25", "E26", "E27"],
    "SV-13": ["E25", "E26", "E27"],
    "SV-14": ["E28"],
    "SV-15": ["E29", "E30"],
}


def load_external_search_group(
    reference_root: str | Path,
    project_id: str,
    evidence_root: str | Path | None = None,
) -> dict[str, Any]:
    if evidence_root is not None:
        project_external = Path(evidence_root).resolve() / project_id / "外部Search"
        packages = sorted(
            (path for path in project_external.glob("Search验证综合评估_*") if path.is_dir()),
            key=lambda path: path.name,
            reverse=True,
        )
        if packages:
            return _load_repository_cached(str(packages[0]), project_id)
    return _load_cached(str(Path(reference_root).resolve()), project_id)


@lru_cache(maxsize=8)
def _load_repository_cached(package_dir: str, project_id: str) -> dict[str, Any]:
    package = Path(package_dir)
    if project_id == "P01":
        claims_path = package / "01_SOTA与对比指标验证" / "claims_summary.csv"
        index_path = package / "01_SOTA与对比指标验证" / "evidence_index.csv"
        report_path = package / "01_SOTA与对比指标验证" / "SOTA验证报告.md"
    elif project_id == "P02":
        claims_path = package / "01_SOTA与对比指标验证" / "claim_verification.csv"
        index_path = None
        report_path = package / "01_SOTA与对比指标验证" / "SOTA验证报告.md"
    elif project_id == "P06":
        return _load_p06_repository(package)
    else:
        return _empty(project_id, "该项目暂无统一外部 Search 目录。")
    if not claims_path.is_file():
        return _empty(project_id, f"统一外部 Search 目录缺少声明表：{claims_path}")
    try:
        claim_rows = _read_csv_path(claims_path)
        index_rows = _read_csv_path(index_path) if index_path and index_path.is_file() else []
        repository_members = _list_repository_members(package)
        repository_tables = _load_repository_tables(package)
    except (OSError, UnicodeError, csv.Error) as exc:
        return _empty(project_id, f"统一外部 Search 目录读取失败：{type(exc).__name__}: {exc}")
    claims = [_normalize_claim(project_id, row, package) for row in claim_rows]
    evidence_index = [_normalize_index(project_id, row, package) for row in index_rows]
    source_records = _build_source_records(project_id, claims, evidence_index, package)
    source_by_id = {str(row.get("source_id")): row for row in source_records}
    for claim in claims:
        source_ids = _claim_source_ids(project_id, claim, source_records)
        attached = [source_by_id[source_id] for source_id in source_ids if source_id in source_by_id]
        claim["source_record_ids"] = source_ids
        claim["source_records"] = attached
        claim["primary_urls"] = list(dict.fromkeys([
            *(claim.get("primary_urls") or []),
            *(str(row.get("url") or "") for row in attached if row.get("url")),
        ]))
        claim["local_evidence"] = list(dict.fromkeys([
            *(claim.get("local_evidence") or []),
            *(str(row.get("local_member") or "") for row in attached if row.get("local_member")),
            *(str(row.get("screenshot_member") or "") for row in attached if row.get("screenshot_member")),
        ]))
    verdict_counts = Counter(str(row.get("verdict") or "未标注") for row in claims)
    return {
        "schema_version": "external-search-group.v3",
        "project_id": project_id,
        "status": "loaded",
        "provider": "统一评价依据/外部Search",
        "repository_root": str(package),
        "archive_file": "",
        "archive_size": sum(path.stat().st_size for path in package.rglob("*") if path.is_file()),
        "cutoff": "2026-08-26",
        "claim_count": len(claims),
        "evidence_index_count": len(evidence_index),
        "source_record_count": len(source_records),
        "archive_member_count": len(repository_members),
        "archive_inventory": _archive_inventory(repository_members),
        "outcome_source_counts": _outcome_source_counts(claims),
        "verdict_counts": dict(verdict_counts),
        "claims": claims,
        "evidence_index": evidence_index,
        "source_records": source_records,
        "sources": [*[_claim_as_source(row) for row in claims], *source_records],
        "archive_members": repository_members,
        "repository_table_count": len(repository_tables),
        "repository_row_count": sum(int(row.get("row_count") or 0) for row in repository_tables),
        "repository_tables": repository_tables,
        "repository_module_counts": _repository_module_counts(repository_tables),
        "report_member": str(report_path.relative_to(package)),
        "note": "已从工作台统一评价依据目录加载；目录同时保留模块报告、表格和原始证据。",
    }


def _load_p06_repository(package: Path) -> dict[str, Any]:
    table = package / "04_综合结论" / "综合判断总表.csv"
    index_table = package / "04_综合结论" / "证据总索引.csv"
    if not table.is_file():
        return _empty("P06", f"统一外部 Search 目录缺少综合判断总表：{table}")
    if not index_table.is_file():
        return _empty("P06", f"统一外部 Search 目录缺少证据总索引：{index_table}")
    rows = _read_csv_path(table)
    index_rows = _read_csv_path(index_table)
    members = _list_repository_members(package)
    repository_tables = _load_repository_tables(package)
    source_records = [_normalize_p06_source(row, package) for row in index_rows]
    source_by_evidence_id = {
        str(row.get("evidence_id") or ""): row for row in source_records
    }
    claims = []
    outcome_claim_map = {
        "OC-P06-01": {"CLM-001", "CLM-002", "CLM-003"},
        "OC-P06-02": {"CLM-004", "CLM-005", "CLM-006", "CLM-007", "CLM-008", "CLM-009", "CLM-010"},
        "OC-P06-03": {"CLM-011", "CLM-012", "CLM-013", "CLM-014", "CLM-Y1-004"},
    }
    for row in rows:
        claim_id = row.get("声明ID", "")
        claim = {
            "claim_id": claim_id,
            "source_id": f"EXT-P06-{claim_id}",
            "project_location": row.get("对应阶段ID", ""),
            "domain": row.get("项目成果", ""),
            "project_claim": row.get("原始项目声明", ""),
            "project_conditions": "",
            "review_cutoff": row.get("评审基准日", ""),
            "public_original": row.get("项目前既有成果结论", ""),
            "current_strong_result": row.get("SOTA核验结论", ""),
            "key_difference": row.get("项目期新增判断", ""),
            "verdict": row.get("综合判断", ""),
            "reproduction_estimate": row.get("外部使用结论", ""),
            "external_use_assessment": row.get("外部使用结论", ""),
            "confidence": row.get("综合判断置信度", ""),
            "primary_urls": [],
            "core_evidence_ids": [value for value in row.get("核心证据ID", "").split(";") if value],
            "local_evidence": [],
            "required_evidence": row.get("待核材料", ""),
            "source_record_ids": [],
            "source_records": [],
            "related_metric_ids": ["D1", "D2", "D5"],
            "related_outcome_ids": [
                outcome_id for outcome_id, claim_ids in outcome_claim_map.items()
                if claim_id in claim_ids
            ],
            "archive_file": str(package),
        }
        attached = [
            source_by_evidence_id[evidence_id]
            for evidence_id in claim["core_evidence_ids"]
            if evidence_id in source_by_evidence_id
        ]
        claim["source_record_ids"] = [str(source["source_id"]) for source in attached]
        claim["source_records"] = attached
        claim["primary_urls"] = list(dict.fromkeys(
            str(source.get("url") or "") for source in attached if source.get("url")
        ))
        claim["local_evidence"] = list(dict.fromkeys(
            str(source.get("local_member") or "") for source in attached if source.get("local_member")
        ))
        for source in attached:
            _append_unique(source["related_claim_ids"], claim_id)
        claims.append(claim)
    verdict_counts = Counter(str(row.get("verdict") or "未标注") for row in claims)
    return {
        "schema_version": "external-search-group.v3",
        "project_id": "P06",
        "status": "loaded",
        "provider": "统一评价依据/外部Search",
        "repository_root": str(package),
        "archive_file": "",
        "archive_size": sum(path.stat().st_size for path in package.rglob("*") if path.is_file()),
        "cutoff": "2026-08-26",
        "claim_count": len(claims),
        "evidence_index_count": len(source_records),
        "source_record_count": len(source_records),
        "archive_member_count": len(members),
        "archive_inventory": _archive_inventory(members),
        "outcome_source_counts": _outcome_source_counts(claims),
        "verdict_counts": dict(verdict_counts),
        "claims": claims,
        "evidence_index": source_records,
        "source_records": source_records,
        "sources": [*[_claim_as_source(row) for row in claims], *source_records],
        "archive_members": members,
        "repository_table_count": len(repository_tables),
        "repository_row_count": sum(int(row.get("row_count") or 0) for row in repository_tables),
        "repository_tables": repository_tables,
        "repository_module_counts": _repository_module_counts(repository_tables),
        "report_member": "04_综合结论/综合Search验证报告.md",
        "note": "已加载修改意见6提供的完整综合外部 Search 包。",
    }


def _normalize_p06_source(row: dict[str, str], package: Path) -> dict[str, Any]:
    evidence_id = str(row.get("证据ID") or "")
    return {
        "source_id": f"EXT-P06-{evidence_id}",
        "evidence_id": evidence_id,
        "topic": str(row.get("所属模块") or ""),
        "title": str(row.get("来源标题") or evidence_id),
        "source_type": str(row.get("证据类型") or ""),
        "provider": str(row.get("来源机构") or "统一评价依据/外部Search"),
        "url": str(row.get("原始URL") or ""),
        "local_member": str(row.get("本地相对路径") or ""),
        "screenshot_member": "",
        "locator": str(row.get("主要用途") or ""),
        "event_date": str(row.get("事件日期") or ""),
        "first_public_date": str(row.get("首次公开日期") or ""),
        "time_window_status": str(row.get("是否处于有效时间窗口") or ""),
        "access_limit": str(row.get("访问限制") or ""),
        "related_claim_ids": [],
        "related_outcome_ids": [],
        "source_channel": "external_search_primary_source",
        "archive_file": str(package),
    }


def _read_csv_path(path: Path) -> list[dict[str, str]]:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError:
        text = path.read_text(encoding="gb18030")
    return [dict(row) for row in csv.DictReader(io.StringIO(text))]


def _list_repository_members(package: Path) -> list[dict[str, Any]]:
    rows = []
    for path in package.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(package).as_posix()
        rows.append({
            "archive_member": relative,
            "relative_path": relative,
            "extension": path.suffix.lower() or "[no_ext]",
            "category": _member_category(relative),
        })
    return rows


def _load_repository_tables(package: Path) -> list[dict[str, Any]]:
    tables = []
    for index, path in enumerate(sorted(package.rglob("*.csv")), start=1):
        relative = path.relative_to(package).as_posix()
        module = relative.split("/", 1)[0]
        try:
            rows = _read_csv_path(path)
            columns = list(rows[0].keys()) if rows else []
            status = "loaded"
            error = ""
        except (OSError, UnicodeError, csv.Error) as exc:
            rows = []
            columns = []
            status = "read_error"
            error = f"{type(exc).__name__}: {exc}"
        tables.append({
            "table_id": f"TABLE-{index:03d}",
            "module": module,
            "relative_path": relative,
            "table_name": path.stem,
            "role": _repository_table_role(relative),
            "status": status,
            "error": error,
            "row_count": len(rows),
            "column_count": len(columns),
            "columns": columns,
            "rows": rows,
        })
    return tables


def _repository_table_role(relative: str) -> str:
    value = relative.lower().split("/", 1)[-1]
    labels = (
        (("媒体", "新闻", "自媒体"), "media"),
        (("内部自报", "自报应用", "自报部署"), "internal_reported_use"),
        (("外部使用", "部署表", "成果使用", "summary_table"), "use_and_deployment"),
        (("外部评价", "引用表", "citing_summary"), "external_evaluation_and_citation"),
        (("阴性检索", "误命中", "排除清单", "exclusions"), "negative_search_and_exclusions"),
        (("既有成果", "成果追溯", "复用判断", "成员论文", "成员专利"), "prior_results_trace"),
        (("sota", "指标", "claim_verification", "claims_summary"), "sota_and_metric_validation"),
        (("检索日志", "search_log"), "search_log"),
        (("证据", "sources", "index"), "evidence_and_source_index"),
        (("综合判断",), "integrated_judgment"),
        (("项目材料", "时间窗口", "声明抽取"), "project_input_and_boundary"),
    )
    for keywords, role in labels:
        if any(keyword in value for keyword in keywords):
            return role
    return "supporting_table"


def _repository_module_counts(tables: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for table in tables:
        module = str(table.get("module") or "其他")
        bucket = counts.setdefault(module, {"table_count": 0, "row_count": 0})
        bucket["table_count"] += 1
        bucket["row_count"] += int(table.get("row_count") or 0)
    return counts


@lru_cache(maxsize=8)
def _load_cached(reference_root: str, project_id: str) -> dict[str, Any]:
    spec = ARCHIVES.get(project_id)
    if not spec:
        return _empty(project_id, "该项目暂无修改意见3外部Search包。")
    archive = Path(reference_root) / spec["file"]
    if not archive.is_file():
        return _empty(project_id, f"未找到外部Search包：{archive}")
    try:
        claim_rows = _read_csv_member(archive, spec["claims"])
        index_rows = _read_csv_member(archive, spec["index"]) if spec["index"] else []
        manifest_rows = _read_csv_member(archive, spec["manifest"]) if spec.get("manifest") else []
        project_manifest_rows = _read_csv_member(archive, spec["project_manifest"]) if spec.get("project_manifest") else []
        archive_members = _list_search_members(archive)
    except (OSError, subprocess.SubprocessError, UnicodeError, csv.Error) as exc:
        return _empty(project_id, f"外部Search包读取失败：{type(exc).__name__}: {exc}")
    claims = [_normalize_claim(project_id, row, archive) for row in claim_rows]
    evidence_index = [_normalize_index(project_id, row, archive) for row in index_rows]
    source_records = _build_source_records(project_id, claims, evidence_index, archive)
    source_by_id = {str(row.get("source_id")): row for row in source_records}
    for claim in claims:
        source_ids = _claim_source_ids(project_id, claim, source_records)
        attached = [source_by_id[source_id] for source_id in source_ids if source_id in source_by_id]
        claim["source_record_ids"] = source_ids
        claim["source_records"] = attached
        claim["primary_urls"] = list(dict.fromkeys([
            *(claim.get("primary_urls") or []),
            *(str(row.get("url") or "") for row in attached if row.get("url")),
        ]))
        claim["local_evidence"] = list(dict.fromkeys([
            *(claim.get("local_evidence") or []),
            *(str(row.get("local_member") or "") for row in attached if row.get("local_member")),
            *(str(row.get("screenshot_member") or "") for row in attached if row.get("screenshot_member")),
        ]))
    verdict_counts: dict[str, int] = {}
    for row in claims:
        verdict = str(row.get("verdict") or "未标注")
        verdict_counts[verdict] = verdict_counts.get(verdict, 0) + 1
    claim_sources = [_claim_as_source(row) for row in claims]
    inventory = _archive_inventory(archive_members)
    outcome_source_counts = _outcome_source_counts(claims)
    return {
        "schema_version": "external-search-group.v2",
        "project_id": project_id,
        "status": "loaded",
        "provider": "修改意见3外部Search组",
        "archive_file": str(archive),
        "archive_size": archive.stat().st_size,
        "cutoff": "2026-08-05" if project_id == "P01" else "2026-08-04",
        "claim_count": len(claims),
        "evidence_index_count": len(evidence_index),
        "source_record_count": len(source_records),
        "archive_member_count": len(archive_members),
        "archive_inventory": inventory,
        "outcome_source_counts": outcome_source_counts,
        "verdict_counts": verdict_counts,
        "claims": claims,
        "evidence_index": evidence_index,
        "source_records": source_records,
        "sources": [*claim_sources, *source_records],
        "evidence_manifest": manifest_rows,
        "project_source_manifest": project_manifest_rows,
        "archive_members": archive_members,
        "report_member": spec["report"],
        "note": "这些结论评估公开材料能否支持项目声明；它们是评价输入，不自动成为最终创新或影响力结论。",
    }


def _read_csv_member(archive: Path, pattern: str) -> list[dict[str, str]]:
    tar = shutil.which("tar")
    if not tar:
        raise OSError("系统未提供 tar，无法读取 RAR 索引。")
    completed = subprocess.run(
        [tar, "-xOf", str(archive), pattern],
        check=True,
        capture_output=True,
        timeout=120,
    )
    try:
        text = completed.stdout.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = completed.stdout.decode("gb18030")
    return [dict(row) for row in csv.DictReader(io.StringIO(text))]


def _list_search_members(archive: Path) -> list[dict[str, Any]]:
    tar = shutil.which("tar")
    if not tar:
        raise OSError("系统未提供 tar，无法读取压缩包目录。")
    completed = subprocess.run([tar, "-tf", str(archive)], check=True, capture_output=True, timeout=120)
    try:
        text = completed.stdout.decode("utf-8")
    except UnicodeDecodeError:
        text = completed.stdout.decode("gb18030", errors="replace")
    rows = []
    for raw_name in text.splitlines():
        marker = "/search_validation/"
        if marker not in raw_name:
            continue
        relative = raw_name.split(marker, 1)[1].strip("/")
        if not relative or raw_name.endswith("/"):
            continue
        suffix = Path(relative).suffix.lower() or "[no_ext]"
        rows.append({
            "archive_member": raw_name,
            "relative_path": relative,
            "extension": suffix,
            "category": _member_category(relative),
        })
    return rows


def _normalize_claim(project_id: str, row: dict[str, str], archive: Path) -> dict[str, Any]:
    if project_id == "P01":
        claim_id = row.get("ID", "")
        domain = row.get("领域", "")
        normalized = {
            "claim_id": claim_id,
            "project_location": row.get("项目位置", ""),
            "domain": domain,
            "project_claim": row.get("项目声明", ""),
            "project_conditions": row.get("项目数值或基线", ""),
            "public_original": row.get("公开原始水平", ""),
            "current_strong_result": row.get("截至2026-08-05找到的公开最好值", ""),
            "key_difference": row.get("数据集与口径差异", ""),
            "verdict": row.get("结论", ""),
            "reproduction_estimate": row.get("重算或实际指标估计", ""),
            "confidence": "",
            "primary_urls": [],
            "local_evidence": [],
            "required_evidence": row.get("需要补证", ""),
        }
    else:
        claim_id = row.get("claim_id", "")
        domain = row.get("domain", "")
        normalized = {
            "claim_id": claim_id,
            "project_location": row.get("pdf_pages", ""),
            "domain": domain,
            "project_claim": row.get("project_claim", ""),
            "project_conditions": row.get("project_conditions", ""),
            "public_original": row.get("public_original", ""),
            "current_strong_result": row.get("current_strong_result", ""),
            "key_difference": row.get("key_difference", ""),
            "verdict": row.get("verdict", ""),
            "reproduction_estimate": row.get("reproduction_estimate", ""),
            "confidence": row.get("confidence", ""),
            "primary_urls": [value for value in row.get("primary_urls", "").split(";") if value],
            "local_evidence": [value for value in row.get("local_evidence", "").split(";") if value],
            "required_evidence": "",
        }
    normalized.update(
        {
            "source_id": f"EXT-{project_id}-{claim_id}",
            "archive_file": str(archive),
            "related_metric_ids": _related_metrics(project_id, claim_id, domain),
            "related_outcome_ids": _related_outcomes(project_id, claim_id),
        }
    )
    return normalized


def _normalize_index(project_id: str, row: dict[str, str], archive: Path) -> dict[str, Any]:
    return {
        "source_id": f"EXT-{project_id}-{row.get('SourceID', '')}",
        "topic": row.get("主题", ""),
        "title": row.get("来源名称", ""),
        "archive_file": str(archive),
        "local_member": row.get("本地原文", ""),
        "screenshot_member": row.get("关键截图", ""),
        "url": row.get("原始URL", ""),
        "locator": row.get("关键位置/用途", ""),
        "related_claim_ids": [],
        "related_outcome_ids": [],
    }


def _build_source_records(
    project_id: str,
    claims: list[dict[str, Any]],
    evidence_index: list[dict[str, Any]],
    archive: Path,
) -> list[dict[str, Any]]:
    if project_id == "P01":
        inverse: dict[str, list[str]] = {}
        for claim_id, source_ids in P01_CLAIM_SOURCE_MAP.items():
            for source_id in source_ids:
                inverse.setdefault(source_id, []).append(claim_id)
        rows = []
        for source in evidence_index:
            short_id = str(source.get("source_id") or "").removeprefix("EXT-P01-")
            claim_ids = inverse.get(short_id, [])
            outcome_ids = list(dict.fromkeys(
                outcome_id
                for claim_id in claim_ids
                for outcome_id in _related_outcomes(project_id, claim_id)
            ))
            source.update({
                "source_channel": "external_search_primary_source",
                "provider": "修改意见3外部Search组",
                "archive_file": str(archive),
                "related_claim_ids": claim_ids,
                "related_outcome_ids": outcome_ids,
            })
            rows.append(source)
        return rows

    unique: dict[str, dict[str, Any]] = {}
    for claim in claims:
        claim_id = str(claim.get("claim_id") or "")
        outcome_ids = list(claim.get("related_outcome_ids") or [])
        for url in claim.get("primary_urls") or []:
            key = f"url:{url}"
            row = unique.setdefault(key, {
                "source_id": f"EXT-{project_id}-SRC-{len(unique) + 1:03d}",
                "title": _source_title(url),
                "url": url,
                "local_member": "",
                "screenshot_member": "",
                "source_channel": "external_search_primary_source",
                "provider": "修改意见3外部Search组",
                "archive_file": str(archive),
                "related_claim_ids": [],
                "related_outcome_ids": [],
            })
            _append_unique(row["related_claim_ids"], claim_id)
            for outcome_id in outcome_ids:
                _append_unique(row["related_outcome_ids"], outcome_id)
        for member in claim.get("local_evidence") or []:
            key = f"local:{member}"
            row = unique.setdefault(key, {
                "source_id": f"EXT-{project_id}-SRC-{len(unique) + 1:03d}",
                "title": Path(member).name,
                "url": "",
                "local_member": member,
                "screenshot_member": member if Path(member).suffix.lower() in {".png", ".jpg", ".jpeg"} else "",
                "source_channel": "external_search_local_evidence",
                "provider": "修改意见3外部Search组",
                "archive_file": str(archive),
                "related_claim_ids": [],
                "related_outcome_ids": [],
            })
            _append_unique(row["related_claim_ids"], claim_id)
            for outcome_id in outcome_ids:
                _append_unique(row["related_outcome_ids"], outcome_id)
    return list(unique.values())


def _claim_source_ids(
    project_id: str, claim: dict[str, Any], source_records: list[dict[str, Any]]
) -> list[str]:
    claim_id = str(claim.get("claim_id") or "")
    return [
        str(row.get("source_id"))
        for row in source_records
        if claim_id in {str(value) for value in row.get("related_claim_ids") or []}
    ]


def _archive_inventory(members: list[dict[str, Any]]) -> dict[str, Any]:
    extensions = Counter(str(row.get("extension") or "[no_ext]") for row in members)
    categories = Counter(str(row.get("category") or "other") for row in members)
    return {
        "file_type_counts": dict(sorted(extensions.items())),
        "category_counts": dict(sorted(categories.items())),
        "search_material_count": sum(row.get("category") == "external_evidence" for row in members),
        "project_material_count": sum(row.get("category") == "project_evidence" for row in members),
        "report_and_index_count": sum(row.get("category") == "report_or_index" for row in members),
    }


def _member_category(relative: str) -> str:
    normalized = relative.replace("\\", "/")
    if "/evidence/project/" in f"/{normalized}" or "/screenshots/project_" in f"/{normalized}":
        return "project_evidence"
    if "/evidence/" in f"/{normalized}" or "/screenshots/" in f"/{normalized}":
        return "external_evidence"
    if normalized.endswith((".csv", ".md", ".txt")):
        return "report_or_index"
    return "other"


def _outcome_source_counts(claims: list[dict[str, Any]]) -> dict[str, int]:
    buckets: dict[str, set[str]] = {}
    for claim in claims:
        for outcome_id in claim.get("related_outcome_ids") or []:
            buckets.setdefault(str(outcome_id), set()).update(
                str(value) for value in claim.get("source_record_ids") or []
            )
    return {key: len(value) for key, value in buckets.items()}


def _source_title(value: str) -> str:
    clean = value.split("?", 1)[0].rstrip("/")
    return clean.rsplit("/", 1)[-1] or value


def _append_unique(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)


def _claim_as_source(claim: dict[str, Any]) -> dict[str, Any]:
    content = "\n".join(
        [
            f"项目声明：{claim.get('project_claim', '')}",
            f"公开原始水平：{claim.get('public_original', '')}",
            f"当前公开强结果：{claim.get('current_strong_result', '')}",
            f"口径差异：{claim.get('key_difference', '')}",
            f"Search组判定：{claim.get('verdict', '')}",
            f"重算/复现判断：{claim.get('reproduction_estimate', '')}",
        ]
    )
    urls = claim.get("primary_urls") or []
    related = list(claim.get("related_metric_ids") or [])
    return {
        "source_id": claim.get("source_id"),
        "source_metric_id": related[0] if related else "",
        "related_metric_ids": related,
        "related_outcome_ids": claim.get("related_outcome_ids", []),
        "source_channel": "external_search_group",
        "provider": "修改意见3外部Search组",
        "title": f"{claim.get('claim_id')} · {claim.get('domain')}",
        "url": urls[0] if urls else "",
        "content": content,
        "verdict": claim.get("verdict"),
        "claim_id": claim.get("claim_id"),
        "archive_file": claim.get("archive_file"),
        "local_evidence": claim.get("local_evidence", []),
    }


def _related_metrics(project_id: str, claim_id: str, domain: str) -> list[str]:
    if project_id == 'P02':
        exact = {
            'C01': ['D1','D2','D5','L4_P02_07'],
            'C02': ['D1','D2','L2F_new_reaction','L2F_wet_validation'],
            'C03': ['D1','D2','D5','L2F_prediction_loop','L3_15_wet_loop','L4_P02_07'],
            'C04': ['D1','D2','L2F_new_reaction','L2F_yield_selectivity'],
            'C05': ['D1','D2','L2F_new_reaction','L2F_yield_selectivity'],
            'C06': ['D1','D2','L2F_new_reaction'],
            'C07': ['D1','D2','L2F_new_reaction'],
            'C08': ['D1','D2','L2F_new_reaction'],
            'C09': ['D1','D2','L4_P02_02'],
            'C10': ['D1','D2','L4_P02_03'],
            'C11': ['D1','D2','L3_15_reaction_accuracy','L4_P02_03'],
            'C12': ['D1','D2','L3_15_reaction_accuracy','L4_P02_03'],
            **{f'C{i}': ['D1','D2','L4_P02_06'] for i in range(13,19)},
            'C19': ['D1','D2','D5','L4_P02_04','L4_P02_05','L4_P02_07'],
            'C20': ['D1','D2','D5','L4_P02_07'],
        }
        return exact.get(claim_id, [])
    if project_id == "P01":
        exact = {
            'SV-01':['L2E_sim_accuracy','L3_14_complex_prediction'],
            'SV-02':['L2E_sim_accuracy','L3_14_complex_prediction','L4_P01_01'],
            'SV-03':['L2E_sim_accuracy','L3_14_complex_prediction'],
            'SV-04':['L2E_sim_accuracy','L3_14_complex_prediction'],
            'SV-05':['L2E_sim_accuracy','L3_14_extreme_accuracy'],
            'SV-06':['L2E_sim_accuracy','L2E_efficiency'],
            'SV-07':['L2E_sim_accuracy','L3_14_extreme_accuracy'],
            'SV-08':['L3_14_extreme_accuracy'],
            'SV-09':['L2E_efficiency','L3_14_efficiency'],
            'SV-10':['L2E_efficiency','L3_14_efficiency'],
            'SV-11':['L2E_efficiency','L3_14_efficiency'],
            'SV-12':[],
            'SV-13':['L2E_sim_accuracy','L3_14_complex_prediction'],
            'SV-14':['L2E_efficiency','L3_14_efficiency'],
            'SV-15':['L2E_sim_accuracy','L3_14_extreme_accuracy'],
        }
        return ['D1','D2',*exact[claim_id]] if claim_id in exact else []
    base = ["D1", "D2"]
    number = int(claim_id[1:]) if claim_id.startswith("C") and claim_id[1:].isdigit() else 0
    if 2 <= number <= 8:
        return base + ["L2F_new_reaction", "L2F_wet_validation", "L4_P02_07"]
    if 9 <= number <= 12:
        return base + ["L3_15_reaction_accuracy", "L4_P02_02", "L4_P02_03"]
    if 13 <= number <= 18:
        return base + ["L4_P02_01", "L4_P02_06"]
    if number == 19:
        return base + ["D5", "L3_15_wet_loop", "L4_P02_04", "L4_P02_05", "L4_P02_07"]
    return base + ["D5", "L4_P02_07"]


def _related_outcomes(project_id: str, claim_id: str) -> list[str]:
    if project_id == "P01":
        groups = {
            "OC-P01-01": {"SV-01", "SV-02", "SV-03", "SV-11"},
            "OC-P01-02": {"SV-06", "SV-07", "SV-08", "SV-09", "SV-10", "SV-14"},
            "OC-P01-03": {"SV-04", "SV-05", "SV-12", "SV-13", "SV-15"},
        }
    else:
        groups = {
            "OC-P02-01": {"C02", "C03", "C04", "C05", "C06", "C07", "C08", "C10", "C11", "C12"},
            "OC-P02-02": {"C09", "C13", "C14", "C15", "C16", "C17", "C18"},
            "OC-P02-03": {"C01", "C03", "C04", "C19", "C20"},
        }
    return [outcome_id for outcome_id, claim_ids in groups.items() if claim_id in claim_ids]


def _empty(project_id: str, note: str) -> dict[str, Any]:
    return {
        "schema_version": "external-search-group.v1",
        "project_id": project_id,
        "status": "not_available",
        "provider": "修改意见3外部Search组",
        "claim_count": 0,
        "evidence_index_count": 0,
        "verdict_counts": {},
        "claims": [],
        "evidence_index": [],
        "sources": [],
        "note": note,
    }


__all__ = ["load_external_search_group"]
