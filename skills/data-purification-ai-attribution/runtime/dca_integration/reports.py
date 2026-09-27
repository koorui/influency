from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any


_STYLE = """
body{margin:0;background:#f4f6f5;color:#18272a;font-family:'Microsoft YaHei UI','Microsoft YaHei',sans-serif;letter-spacing:0}
main{max-width:1080px;margin:auto;padding:34px 24px 54px}header{border-bottom:3px solid #0b7661;padding-bottom:18px;margin-bottom:22px}
.kicker{color:#0b7661;font-weight:700;font-size:13px}h1{font-size:28px;margin:7px 0 5px}h2{font-size:18px;margin:24px 0 10px}
.muted{color:#637477}.panel{background:#fff;border:1px solid #d9e1df;padding:17px;margin:12px 0}.boundary{border-left:4px solid #b65e22;background:#fff8ef;padding:13px 15px;line-height:1.7}
table{width:100%;border-collapse:collapse;background:#fff;font-size:13px}th,td{padding:10px;border:1px solid #d9e1df;text-align:left;vertical-align:top}th{background:#eaf3f0}.empty{color:#637477;padding:20px;background:#fff;border:1px solid #d9e1df}
"""


def _esc(value: Any) -> str:
    if isinstance(value, (list, dict)):
        value = json.dumps(value, ensure_ascii=False)
    return html.escape(str(value if value is not None else ""))


def _status_label(value: str) -> str:
    return {
        "direct_increment_supported": "直接增量有证据",
        "conditional_increment_supported": "有条件支持增量",
        "participation_supported_increment_not_isolated": "已确认参与，独立增量未分离",
        "baseline_reference": "比较基线",
        "no_positive_increment_observed": "未观察到正向增量",
        "isolated_effect_observed": "仅观察到描述性变化",
        "increment_not_confirmed_due_to_comparability": "可比性不足，增量未确认",
        "not_established": "尚未建立",
        "conflicting_comparisons": "对照结果方向不一致",
    }.get(value, value)


def _comparability_label(value: str) -> str:
    return {"established": "条件已锁定", "partial": "部分可比", "unknown": "尚未确认"}.get(value, value)


def _effect_label(value: str) -> str:
    return {"improved": "改善", "no_change": "无变化", "worsened": "变差", "descriptive": "仅描述", "threshold_met": "达到门槛", "threshold_not_met": "未达门槛", "threshold_unresolved": "达标条件待核"}.get(value, value)


def _selection_reason_label(reason: Any) -> str:
    if not isinstance(reason, dict):
        return str(reason or "")
    reason_type = reason.get("type")
    if reason_type == "group_coverage_representative":
        return f"覆盖分组：{reason.get('group', '')}"
    if reason_type == "behavioral_representative":
        reduction = reason.get("distance_reduction")
        suffix = f"，总体距离降低 {reduction}" if reduction is not None else ""
        return f"补充行为代表性{suffix}"
    return json.dumps(reason, ensure_ascii=False)


def _page(title: str, kicker: str, body: str) -> str:
    return f"""<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{_esc(title)}</title><style>{_STYLE}</style></head><body><main><header><div class='kicker'>{_esc(kicker)}</div><h1>{_esc(title)}</h1></header>{body}</main></body></html>"""


def render_purification_report(path: Path, summary: dict[str, Any], selection: dict[str, Any] | None) -> None:
    counts = summary["counts"]
    rows = "".join(f"<tr><th>{_esc(label)}</th><td>{_esc(value)}</td></tr>" for label, value in [
        ("输入记录", counts["input"]), ("保留", counts["kept"]), ("隔离", counts["quarantined"]),
        ("移除", counts["removed"]), ("合格候选", counts["eligible"]), ("最终选样", counts["selected"]),
    ] if value is not None)
    selected = ""
    if selection:
        selected_rows = "".join(
            f"<tr><td>{_esc(row.get('id', row.get('_purification', {}).get('record_id', '')))}</td><td>{_esc(row['_selection']['rank'])}</td><td>{_esc(row['_selection']['discrimination'])}</td><td>{_esc(_selection_reason_label(row['_selection']['reason']))}</td></tr>"
            for row in selection["selected"]
        )
        selected = f"<h2>高区分度选样</h2><table><thead><tr><th>样本</th><th>序号</th><th>区分度</th><th>选择依据</th></tr></thead><tbody>{selected_rows}</tbody></table>"
    body = f"<div class='panel'><p>本报告由本次输入重新计算生成。</p><table>{rows}</table></div>{selected}<div class='boundary'>该输出用于记录数据质量处置和选样结果，不直接证明所选样本在所有任务上的科学有效性。</div>"
    path.write_text(_page("数据提纯结果", "DATA PURIFICATION", body), encoding="utf-8")


def render_attribution_report(path: Path, result: dict[str, Any]) -> None:
    rows = "".join(
        f"<tr><td>{_esc(item['factor_name'])}</td><td>{_esc(item['factor_type'])}</td><td>{_esc(item['role'])}</td><td>{_esc(_status_label(item['status']))}</td><td>{_esc(item['conclusion'])}</td><td>{_esc(item['evidence_ids'])}</td></tr>"
        for item in result["factor_results"]
    )
    comparisons = "".join(
        f"<tr><td>{_esc(item['name'])}</td><td>{_esc(item['baseline_value'])} {_esc(item.get('baseline_unit',item['unit']))}</td><td>{_esc(item['observed_value'])} {_esc(item.get('observed_unit',item['unit']))}</td><td>{_esc(round(item['percent_change_from_baseline'], 2) if item['percent_change_from_baseline'] is not None else '')}</td><td>{_esc(_effect_label(item['effect_outcome']))}<br>{_esc(item.get('calculation_boundary',''))}</td><td>{_esc(_comparability_label(item['comparability_status']))}</td><td>{_esc(item['isolated_factor_ids'])}</td></tr>"
        for item in result["comparison_results"]
    )
    body = f"<div class='panel'><b>{_esc(result['project']['name'])}</b><p>{_esc(result['target']['name'])}</p><p>{_esc(result['summary'])}</p></div><h2>因素级归因</h2><table><thead><tr><th>因素</th><th>类型</th><th>作用</th><th>状态</th><th>判断</th><th>证据</th></tr></thead><tbody>{rows}</tbody></table><h2>比较结果</h2><table><thead><tr><th>比较</th><th>基线</th><th>观察值</th><th>相对变化(%)</th><th>结果方向</th><th>可比性</th><th>被单独考察因素</th></tr></thead><tbody>{comparisons}</tbody></table><div class='boundary'>{_esc(result['boundary'])}</div>"
    path.write_text(_page("AI贡献归因结果", "CONTRIBUTION ATTRIBUTION", body), encoding="utf-8")


def render_unresolved_report(path: Path, project: dict[str, Any], target: dict[str, Any], items: list[dict[str, Any]]) -> None:
    if items:
        rows = "".join(
            f"<tr><td>{_esc(item['category'])}</td><td>{_esc(item['known_fact'])}</td><td>{_esc(item['external_finding'])}</td><td>{_esc(item['unresolved_question'])}</td><td>{_esc(item['reason'])}</td></tr>"
            for item in items
        )
        table = f"<table><thead><tr><th>类别</th><th>已知事实/项目说法</th><th>外部发现</th><th>未决问题</th><th>未决原因</th></tr></thead><tbody>{rows}</tbody></table>"
    else:
        table = "<div class='empty'>本次结构化输入未产生未解决事项。该结果不等于开放世界中不存在其他冲突。</div>"
    body = f"<div class='panel'><b>{_esc(project['name'])}</b><p>{_esc(target['name'])}</p></div>{table}<div class='boundary'>未解决事项只分为“查到但冲突、已检索仍查不到、需要专业判断”三类。需要专业判断的事项应进入后续专家咨询，而不是由本工具自动裁决。</div>"
    path.write_text(_page("未解决事项与矛盾冲突", "UNRESOLVED ITEMS", body), encoding="utf-8")
