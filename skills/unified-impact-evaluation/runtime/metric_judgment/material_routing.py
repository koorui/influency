"""Explicit, content-checked routing of the delivered professional materials."""
from __future__ import annotations

import copy
import json
from pathlib import Path
from .active_indicators import replacement_for, RETIRED

REVIEW = json.loads(Path(__file__).with_name('material_routing_review.json').read_text(encoding='utf-8'))
CURRENT_BRANCH_LIMITS = {
    'D6.1':'核查具体成果在内部流程的实际接入，计划和接口可用不能代替任务输入输出。',
    'D6.2':'核查多环节或外部流程的真实协同；不得一概排除内部协作，不将流程作用转记给产物。',
    'D6.3':'核查持续运行周期、重复任务和维护记录；这是更高成熟度条件，不作为G2/G3的共同门槛。',
}


def reviewed_route(metric: dict) -> dict:
    mid = str(metric.get('metric_id') or '')
    pid = str(metric.get('project_id') or '')
    rows = [REVIEW['metrics'].get(pid, {}).get(mid)] if pid else [values[mid] for values in REVIEW['metrics'].values() if mid in values]
    row = rows[0] if len(rows) == 1 and rows[0] else {}
    if row and metric.get('metric_name') and row['name'] != metric['metric_name']:
        row = {}
    if row and 'criterion' in metric and metric['criterion'] != row.get('criterion'):
        row = {}
    branch = row.get('branch_id') or ''
    if not pid and row:
        pid = next((key for key, values in REVIEW['metrics'].items() if values.get(mid) == row), '')
    current = replacement_for(pid, mid) if row else None
    retired_reason = RETIRED.get(pid, {}).get(mid) if row else None
    if retired_reason:
        branch = ''
    elif current:
        branch = current['branch_id']
    return {
        'branch_id': branch, 'dimension_id': branch.split('.')[0] if branch else '',
        'routing_kind': 'reviewed_material_rule' if row else 'unassigned_requires_review',
        'routing_basis': retired_reason or (f"当前指标：{current['name']}。" if current else '') + (row.get('reason') or '没有经核对的对应关系，保留待分配材料；不按关键词或指标轴自动分配。'),
        'boundary': retired_reason or CURRENT_BRANCH_LIMITS.get(branch) or REVIEW['branch_limits'].get(branch) or '需先核对材料对象和评价问题。',
        'matched_terms': [], 'review': row,
    }


def review_materials(metric: dict, route: dict) -> tuple[list[dict], list[dict]]:
    accepted, excluded = [], []
    for item in metric.get('evidence_preview') or []:
        expected = next((row for row in route['review'].get('evidence', [])
                         if row['evidence_id'] == item.get('evidence_id')
                         and row['summary'] == item.get('summary')
                         and row['source_ref'] == (item.get('source_ref') or {})), None)
        eligible = bool(expected and expected['eligible'] and route['branch_id'])
        value = copy.deepcopy(item)
        value['review_status'] = '相关材料，待核验' if eligible else '暂不用于该分支'
        value['review_note'] = expected['reason'] if expected else '材料内容已变化或尚未审查，需重新核对对应关系。'
        if not route['branch_id'] and expected:
            value['review_note'] = route['routing_basis']
        (accepted if eligible else excluded).append(value)
    return accepted, excluded


def explicit_project_facts(rows: list[dict], card: dict) -> list[dict]:
    """Legacy achievement IDs and keyword hits are not frozen outcome links."""
    targets = {card.get('outcome_id'), *(card.get('child_outcome_ids') or [])}
    accepted = []
    for row in rows:
        declared = set(row.get('outcome_ids') or []) | set(row.get('related_outcome_ids') or [])
        if declared.intersection(targets):
            accepted.append(copy.deepcopy(row))
    return accepted
