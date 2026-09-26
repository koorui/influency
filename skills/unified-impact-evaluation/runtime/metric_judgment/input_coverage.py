"""Count the material actually supplied to each outcome/dimension analysis."""
from __future__ import annotations

import json
from collections import Counter
from .prepared_evidence import evidence_key


CHANNELS = [
    ('professional_materials', '专业材料片段'),
    ('external_search', '外部核验声明'),
    ('supplemental_materials', '外部补充材料'),
    ('ai_components', '人工智能组件材料'),
    ('ai_attribution', '人工智能归因记录'),
    ('project_facts', '项目事实与使用记录'),
    ('internal_search', '内部检索正式材料'),
    ('core_problems', '核心问题原始材料'),
    ('problem_links', '已确认的核心问题对应'),
]


def _identity(row, *keys):
    if not isinstance(row, dict):
        return str(row)
    return next((str(row[key]) for key in keys if row.get(key)),
                json.dumps(row, sort_keys=True, ensure_ascii=False))


def packet_material_ids(packet):
    ai = packet.get('ai_contribution') or {}
    return {
        'professional_materials': {evidence_key(item) for binding in packet.get('professional_metrics') or []
                                   for item in (binding.get('metric') or {}).get('evidence_preview') or []},
        'external_search': {_identity(r, 'claim_id') for r in packet.get('external_search') or []},
        'supplemental_materials': {_identity(r, 'record_id') for r in packet.get('supplemental_materials') or []},
        'ai_components': {_identity(r, 'component_id') for r in ai.get('components') or []},
        'ai_attribution': {_identity(r, 'contribution_id') for r in ai.get('attribution_records') or []},
        'project_facts': {_identity(r, 'claim_id', 'evidence_id', 'baseline_id', 'id') for r in packet.get('project_facts') or []},
        'internal_search': {_identity(r, 'source_id', 'record_id', 'id') for r in packet.get('internal_search') or []},
        'core_problems': {_identity(r, 'problem_id') for r in packet.get('step1_core_problems') or []},
        'problem_links': {str(r) for r in packet.get('step3_problem_links') or []},
    }


def dimension_input_coverage(outcome_packets):
    rows = []
    for number in range(1, 8):
        did = f'D{number}'
        ids = {key: set() for key, _ in CHANNELS}
        outcomes = []
        supplemental_roles = {}
        for oid, packet in outcome_packets.items():
            dimension = (packet.get('dimensions') or {}).get(did) or {}
            found = packet_material_ids(dimension)
            counts = {key: len(values) for key, values in found.items()}
            for key in ids:
                ids[key].update(found[key])
            for record in dimension.get('supplemental_materials') or []:
                if record.get('material_role'):
                    supplemental_roles[record['record_id']] = record['material_role']
            # Project-wide problem cards alone do not establish an outcome-specific input.
            has_material = any(count for key, count in counts.items() if key != 'core_problems')
            outcomes.append({'outcome_id': oid, 'has_material': has_material, 'channel_counts': counts})
        counts = {key: len(values) for key, values in ids.items()}
        rows.append({
            'dimension_id': did,
            'outcome_count': len(outcomes),
            'outcomes_with_material': sum(row['has_material'] for row in outcomes),
            'channels': [{'channel_id': key, 'name': name, 'record_count': counts[key],
                          'applicable': (did == 'D1' if key in {'core_problems', 'problem_links'} else
                                         did in {'D1', 'D2', 'D5'} if key in {'ai_components', 'ai_attribution', 'project_facts'} else True)}
                         for key, name in CHANNELS],
            'outcomes': outcomes,
            'supplemental_roles': dict(Counter(supplemental_roles.values())),
            # Backward-compatible aliases now refer strictly to actual input packets.
            'professional_material_count': counts['professional_materials'],
            'outcome_external_claim_count': counts['external_search'],
            'supplemental_material_count': counts['supplemental_materials'],
            'note': '按实际提供给模型的成果、维度材料统计。同一记录在本维度多个成果中出现时合并计数；'
                    '专业材料按相同出处的相同片段去重。不同类别、不同维度可能共用来源，不相加作为独立证据总数。'
                    '已有材料表示可以分析，不表示证据充分、判断成立或专家已确认。',
        })
    return rows
