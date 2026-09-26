"""Assemble delivered evidence without generating or validating evaluation claims."""
from __future__ import annotations

import copy
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import urlencode


def _text(value: Any) -> str:
    if isinstance(value, list):
        return "；".join(_text(item) for item in value if item)
    return str(value or "")


def evidence_key(item: dict) -> tuple:
    """Only collapse identical passages at identical locations, never similar claims."""
    source = item.get("source_ref") or {}
    if not isinstance(source, dict):
        source = {"locator": source}
    location = tuple(_text(source.get(key)).replace("\\", "/") for key in
                     ("locator", "page", "sheet", "cell_range"))
    passage = " ".join(_text(source.get("quote") or item.get("summary")).split())
    if any(location) and passage:
        return (*location, passage)
    return ("unlocated", _text(item.get("evidence_id")), passage)


def professional_groups(bindings: list[dict]) -> list[dict]:
    groups: dict[tuple, dict] = {}
    for binding in bindings:
        metric = binding.get("metric") or {}
        key = (binding.get("branch_id"), metric.get("metric_name") or metric.get("metric_id"))
        group = groups.setdefault(key, {
            "name": key[1], "branch_id": key[0], "dimension_id": binding.get("dimension_id"),
            "origins": [], "evidence": [], "outcome_ids": [], "missing_evidence": [],
            "review_boundary": binding.get('review_boundary') or '',
        })
        group["origins"].append({key: copy.deepcopy(metric.get(key)) for key in
                                 ("metric_id", "source_layer", "criterion", "benchmark")})
        for field, values in (("outcome_ids", binding.get("outcome_ids") or []),
                              ("missing_evidence", metric.get("missing_evidence") or [])):
            for value in values:
                if value not in group[field]:
                    group[field].append(value)
        for item in [*(metric.get("evidence_preview") or []), *(metric.get('excluded_evidence') or [])]:
            match = next((row for row in group["evidence"] if evidence_key(row) == evidence_key(item)), None)
            if match is None:
                match = copy.deepcopy(item)
                match["original_evidence_ids"] = []
                match["original_metric_ids"] = []
                group["evidence"].append(match)
            elif item.get('review_status') == '相关材料，待核验':
                match['review_status'] = item['review_status']
                match['review_note'] = item.get('review_note') or ''
            for field, value in (("original_evidence_ids", item.get("evidence_id")),
                                 ("original_metric_ids", metric.get("metric_id"))):
                if value and value not in match[field]:
                    match[field].append(value)
    return list(groups.values())


def build_prepared_evidence(workspace: dict) -> dict:
    adapter = workspace.get("evidence_adapter") or {}
    packets = adapter.get("outcome_packets") or {}
    contribution = workspace.get("contribution_attribution") or {}
    extraction = contribution.get("component_extraction") or {}
    manifest = {row.get("source_id"): row for row in (extraction.get("data") or {}).get("source_manifest") or []}
    records: dict[tuple, dict] = {}
    local_files: dict[str, list[Path]] = {}

    def source(row: Any) -> dict:
        if isinstance(row, str):
            source_id, _, location = row.partition(":")
            # File paths and URLs are locators, not contribution manifest IDs.
            row = {"source_id": source_id, "location": location} if source_id in manifest else {"locator": row}
        row = row if isinstance(row, dict) else {}
        entry = manifest.get(row.get("source_id")) or {}
        ref = row.get("source_ref") or {}
        if isinstance(ref, str):
            ref = {"locator": ref}
        value = {**entry, **ref, **row}
        location = _text(value.get("location_label") or value.get("location") or value.get("locator") or value.get("local_member"))
        local_status = ""
        download_url = ''
        if value.get("local_member") and value.get("archive_file"):
            root = Path(value["archive_file"]).resolve()
            allowed = (Path(__file__).resolve().parents[1] / "评价依据").resolve()
            if root.is_relative_to(allowed) and root.is_dir():
                member = _text(value["local_member"]).replace("\\", "/").lstrip("./")
                direct = (root / member).resolve()
                if direct.is_relative_to(root) and direct.is_file():
                    matches = [direct]
                else:
                    if str(root) not in local_files:
                        local_files[str(root)] = [path for path in root.rglob("*") if path.is_file()]
                    matches = [path for path in local_files[str(root)]
                               if path.relative_to(root).as_posix().casefold().endswith("/" + member.casefold())
                               or path.relative_to(root).as_posix().casefold() == member.casefold()]
                if len(matches) == 1:
                    location = matches[0].relative_to(root).as_posix()
                    local_status = "已找到本地文件；文件存在不代表内容已核验"
                    project_root = allowed / str((workspace.get('project_profile') or {}).get('project_id') or '')
                    if matches[0].is_relative_to(project_root):
                        download_url = '/api/evidence/file?' + urlencode({'project_id':project_root.name,'path':matches[0].relative_to(project_root).as_posix()})
                elif not matches:
                    local_status = "交付目录未找到该本地文件，需补交原件或修正来源路径"
                else:
                    local_status = "存在多个同名路径，需确认具体来源文件"
        for label, key in (("页", "page"), ("工作表", "sheet"), ("单元格", "cell_range")):
            if value.get(key) is not None and value.get(key) != "":
                location += f" · {label} {value[key]}"
        return {
            "source_id": _text(value.get("source_id") or value.get("evidence_id")),
            "title": _text(value.get("file_name") or value.get("title") or entry.get("material_role") or "原始材料"),
            "location": location,
            "url": _text(value.get("url")),
            "quote": _text(value.get("quote") or value.get("evidence_text") or value.get("abstract_excerpt")),
            "event_date": _text(value.get("event_date") or value.get("publication_date") or value.get("year")),
            "time_scope": _text(value.get("time_window_status")),
            "note": _text(value.get("quality_note")),
            "package": _text(value.get("archive_file")),
            "local_status": local_status,
            "download_url": download_url,
        }

    def add(kind: str, identity: str, title: str, statement: Any, sources: list,
            fields: list, gaps: list, outcome_id: str = "", dimension_id: str = "", branch_id: str = "") -> None:
        key = (kind, identity)
        row = records.setdefault(key, {
            "record_id": f"PREP-{len(records)+1:04d}", "original_id": identity,
            "kind": kind, "title": title, "statement": _text(statement),
            "sources": [], "details": [{"label": label, "text": _text(value)} for label, value in fields if value],
            "gaps": list(dict.fromkeys(_text(value) for value in gaps if value)),
            "outcome_ids": [], "dimension_ids": [], "branch_ids": [],
            "status": "已归集，待评价核验",
        })
        for field, value in (("outcome_ids", outcome_id), ("dimension_ids", dimension_id), ("branch_ids", branch_id)):
            if value and value not in row[field]:
                row[field].append(value)
        for original in sources:
            value = source(original)
            if value not in row["sources"]:
                row["sources"].append(value)

    groups = professional_groups(adapter.get("professional_metric_bindings") or [])
    for group in groups:
        for item in group["evidence"]:
            identity = "|".join(item["original_evidence_ids"])
            eligible = item.get('review_status') != '暂不用于该分支'
            for outcome_id in (group["outcome_ids"] if eligible else []) or [""]:
                add("专业指标材料", identity, group["name"], item.get("summary"),
                    [item.get("source_ref") or {}], [("原指标", item["original_metric_ids"]),
                    ('本轮材料审查', item.get('review_status')), ('审查说明', item.get('review_note')),
                    ('使用边界',group.get('review_boundary'))],
                    group["missing_evidence"], outcome_id, group["dimension_id"] if eligible else '', group["branch_id"] if eligible else '')

    external = (workspace.get("available_search") or {}).get("external_group") or {}
    for claim in external.get("claims") or []:
        claim_id = claim.get("claim_id") or ""
        scopes = [(oid, did) for oid, packet in packets.items() for did, dim in packet.get("dimensions", {}).items()
                  if any(row.get("claim_id") == claim_id for row in dim.get("external_search") or [])]
        for oid, did in scopes or [("", d) for d in claim.get('related_metric_ids') or [] if d in {f'D{i}' for i in range(1,8)}] or [("", "")]:
            add("外部核验记录", claim_id, claim.get("domain") or claim_id, claim.get("project_claim"),
                claim.get("source_records") or [], [("项目测试条件", claim.get("project_conditions")),
                ('上游评审截止日（不是事件日期）',claim.get('review_cutoff')),
                ('上游外部使用核验',claim.get('external_use_assessment')),
                ("上游核验所见", claim.get("public_original")), ("公开对照", claim.get("current_strong_result")),
                ("口径差异", claim.get("key_difference")), ("上游核验意见", claim.get("verdict"))],
                [claim.get("required_evidence")], oid, did)

    for component in (extraction.get("data") or {}).get("components") or []:
        cid = component.get("component_id") or ""
        scopes = [(oid, did) for oid, packet in packets.items() for did, dim in packet.get("dimensions", {}).items()
                  if any(row.get("component_id") == cid for row in (dim.get("ai_contribution") or {}).get("components") or [])]
        for oid, did in scopes or [("", "")]:
            add("贡献拆解材料", cid, component.get("component_name") or cid, component.get("specific_role"),
                component.get("source_refs") or [], [("输入", component.get("input")), ("输出", component.get("output")),
                ("作用机制", component.get("mechanism")), ("上游时间说明", component.get("project_period_status")),
                ("归因限制", component.get("interaction_risk"))], component.get("gaps") or [], oid, did)

    for attribution in contribution.get("records") or []:
        cid = attribution.get("contribution_id") or ""
        scopes = [(oid, did) for oid, packet in packets.items() for did, dim in packet.get("dimensions", {}).items()
                  if any(row.get("contribution_id") == cid for row in (dim.get("ai_contribution") or {}).get("attribution_records") or [])]
        for oid, did in scopes or [("", "")]:
            add("归因核验记录", cid, attribution.get("ai_position") or cid, attribution.get("causal_chain"),
                attribution.get("attribution_basis") or [], [("上游归因意见", attribution.get("incremental_judgement")),
                ("对照可比性", attribution.get("baseline_comparability")), ("消融充分性", attribution.get("ablation_sufficiency"))],
                attribution.get("evidence_gaps") or [], oid, did)

    # Legacy project packets can contain keyword matches to neighbouring table rows.
    # Keep them at project level until their object attribution is reviewed.
    material_packets = (workspace.get("project_materials") or {}).get("outcome_packets") or {}
    inventory = (workspace.get("project_materials") or {}).get("project_evidence_inventory")
    for packet in ([inventory] if inventory is not None else material_packets.values()):
        for category in ("achievement_claims", "claim_evidence", "acceptance_baselines", "new_internal_claims"):
            for item in packet.get(category) or []:
                identity = _text(item.get("claim_id") or item.get("evidence_id") or item.get("baseline_id") or item.get("id"))
                if not identity:
                    continue
                add("项目材料与基准", identity,
                    _text(item.get("title") or item.get("indicator_name") or item.get("metric_name") or item.get("claim_text") or identity),
                    item.get("claim_text") or item.get("requirement_text") or item.get('evidence_text') or item.get("quote") or item.get("summary") or item.get("content"),
                    item.get("sources") or [item.get("source") or item], [("材料类别", "上游提取的考核基准，需与任务书核对" if category == "acceptance_baselines" else "项目材料陈述")],
                    ["原材料涉及的成果范围需核对；相邻表格内容不自动归属于同一成果。"])

    for item in (adapter.get('upstream_materials') or {}).get('records') or []:
        for oid in item['outcome_ids'] or ['']:
            for branch in item['branch_ids'] or ['']:
                add('上游补充核验材料', item['record_id'], item['title'], item['statement'], item['sources'],
                    [('提供方',item['provider']),('材料用途',item['scope']),('原有核验表',item['table_name']),
                     ('原文限制',item['limitation']),('归属状态',item['review_status']),
                     ('对应依据',item.get('association_basis')),('材料性质',item.get('material_role')),
                     ('具体分支成果',item.get('subject_child_outcome_ids')),
                     ('保留为参考的原因',item.get('reference_reason')),
                     ('被引论文', (item.get('citation') or {}).get('cited_doi')),
                     ('引用关系核验状态', (item.get('citation') or {}).get('relationship_status')),
                     ('引用主体独立性', (item.get('citation') or {}).get('independence')),
                     ('上游检索截止日（不是事件日期）', (item.get('citation') or {}).get('review_cutoff'))],
                    ['上游核验意见仍须结合所引原文审查，不直接充当评价结论。'], oid, branch.split('.')[0] if branch else '', branch)
    for problem in ((workspace.get('evidence_repository') or {}).get('internal_achievement') or {}).get('core_problems') or []:
        add('核心问题原始材料',problem.get('problem_id') or problem.get('problem_title',''),
            problem.get('problem_title') or '核心问题',problem.get('prior_method_bottleneck'),
            problem.get('sources') or problem.get('source_evidence') or [],
            [('所需改变',problem.get('required_change_after_project')),('提供方','成果组原有材料，非内部检索正式交付')],
            ['问题与主要成果的对应关系尚需上游明确。'],'','D1','D1.1')

    rows = list(records.values())
    for row in rows:
        if any("未找到" in s["local_status"] or "多个" in s["local_status"] for s in row["sources"]):
            row["gaps"].append("部分本地来源文件缺失或路径有歧义，请核对逐条来源的文件状态。")
        if not row["sources"] or not any(s["location"] or s["url"] for s in row["sources"]):
            row["gaps"].append("缺少可定位的原始出处。")
        if not any(s["quote"] for s in row["sources"]):
            row["gaps"].append("尚未提供可直接阅读的原文摘录；现有摘要不能冒充原文。")
        if not any(s["event_date"] or s["time_scope"] for s in row["sources"]):
            row["gaps"].append("事件日期及评价窗口归属待核对；材料收集日期不替代事件日期。")
    gaps = [{"owner": "内部检索组", "item": "内部检索正式交付尚未接入；现有项目材料保留原提供方。"}]
    if (adapter.get("channel_status") or {}).get("internal_search", {}).get("status") == "loaded":
        gaps = []
    if not packets:
        gaps.append({"owner": "成果凝练组", "item": "缺少已确认的主要成果清单，已有材料暂存项目层，尚不能逐成果评价。"})
    for oid, packet in packets.items():
        if not (packet.get("source_card") or {}).get("problem_ids"):
            gaps.append({"owner": "成果凝练组", "outcome_id": oid, "item": "主要成果与核心问题的明确对应关系尚缺，不能推定核心问题已解决。"})
    return {
        "schema_version": "prepared-evidence.v1", "status": "prepared_not_evaluated",
        "material_review": copy.deepcopy(adapter.get('material_review') or {}),
        "upstream_import": copy.deepcopy((adapter.get('upstream_materials') or {}).get('summary') or {}),
        "external_material_status": {
            'claim_count': len((((workspace.get('available_search') or {}).get('external_group') or {}).get('claims') or [])),
            'claims_in_outcome_inputs': len({r.get('claim_id') for p in packets.values() for d in p['dimensions'].values()
                                           for r in d.get('external_search') or []}),
            'project_context_claim_count': len(adapter.get('project_context_external_search') or []),
            'unassigned_claim_count': (adapter.get('external_routing_audit') or {}).get('unrouted_claim_count', 0),
            'supplemental_count': len((adapter.get('upstream_materials') or {}).get('records') or []),
            'supplemental_in_outcome_inputs': len({r['record_id'] for p in packets.values() for d in p['dimensions'].values()
                                                 for r in d.get('supplemental_materials') or []}),
            'reference_reasons': copy.deepcopy((adapter.get('upstream_materials') or {}).get('summary', {}).get('reference_reasons') or {}),
        },
        "policy": "按已有交付归集，保留项目声明、上游核验意见与原文的区别。材料条数不代表证据充分程度；相同出处可服务多个问题，但不能当作多份独立佐证。成果对应关系沿用现有适配结果，仍需逐条核对。",
        "records": rows, "professional_groups": groups, "gaps": gaps,
        "summary": {"record_count": len(rows), "by_kind": dict(Counter(row["kind"] for row in rows)),
                    "with_quote_count": sum(any(s["quote"] for s in row["sources"]) for row in rows),
                    "with_location_count": sum(any(s["location"] or s["url"] for s in row["sources"]) for row in rows),
                    "outcome_count": len(packets)},
    }
