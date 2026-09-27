"""Separate acceptance thresholds, observed changes and causal comparisons."""
from .common import finite_number

KINDS = {'threshold_check', 'performance_change', 'external_benchmark', 'causal_increment', 'unspecified'}


def calculate_comparison(comparison):
    baseline = finite_number(comparison['baseline']['value'], 'baseline.value')
    observed = finite_number(comparison['observed']['value'], 'observed.value')
    kind = comparison.get('comparison_kind', 'unspecified')
    direction = comparison['direction']
    units = [str(comparison[side].get('unit', '')).strip() for side in ('baseline', 'observed')]
    comparable = comparison['comparability_status'] == 'established' and bool(units[0]) and units[0] == units[1]
    percent = ratio = None
    effect = 'descriptive'
    limitation = ''
    if kind == 'threshold_check':
        if not comparable or direction == 'descriptive_only':
            effect = 'threshold_unresolved'
            limitation = '阈值方向、双方计量口径或测试条件未明确，不能认定实际达标。'
        else:
            passed = observed >= baseline if direction == 'higher_is_better' else observed <= baseline
            effect = 'threshold_met' if passed else 'threshold_not_met'
            limitation = '相对验收门槛只判断达标，不计算性能提升率或因素贡献率。'
    elif kind == 'unspecified' or not comparable:
        limitation = '比较类型、双方单位或同条件可比性未确立；只保留原始数值，不输出提升率。'
    else:
        if direction != 'descriptive_only':
            delta = observed - baseline if direction == 'higher_is_better' else baseline - observed
            effect = 'improved' if delta > 0 else 'worsened' if delta < 0 else 'no_change'
        if baseline > 0:
            delta = baseline - observed if direction == 'lower_is_better' else observed - baseline
            percent = delta / baseline * 100
            if observed > 0:
                ratio = baseline / observed - 1 if direction == 'lower_is_better' else observed / baseline - 1
        else:
            limitation = '基线非正数，不报告百分比或倍数；数值方向与独立归因分别判断。'
    causal = (kind == 'causal_increment' and comparable and len(comparison['isolated_factor_ids']) == 1
              and bool(comparison.get('controlled_conditions', '').strip())
              and all(comparison.get(k) for k in ('baseline_evidence_ids', 'observed_evidence_ids', 'control_evidence_ids')))
    return {
        'id': comparison['id'], 'name': comparison['name'], 'comparison_kind': kind,
        'baseline_label': comparison['baseline'].get('label', 'baseline'), 'baseline_value': baseline,
        'observed_label': comparison['observed'].get('label', 'observed'), 'observed_value': observed,
        'unit': units[0] if units[0]==units[1] else '', 'baseline_unit':units[0], 'observed_unit':units[1], 'direction': direction,
        'comparability_status': comparison['comparability_status'], 'effect_outcome': effect,
        'absolute_difference': round(observed - baseline, 8) if units[0] and units[0]==units[1] else None,
        'percent_change_from_baseline': round(percent, 8) if percent is not None else None,
        'ratio_change': round(ratio, 8) if ratio is not None else None,
        'causal_eligible': causal, 'calculation_boundary': limitation,
        'involved_factor_ids': comparison['involved_factor_ids'],
        'isolated_factor_ids': comparison['isolated_factor_ids'], 'evidence_ids': comparison['evidence_ids'],
        'baseline_evidence_ids': comparison.get('baseline_evidence_ids', []),
        'observed_evidence_ids': comparison.get('observed_evidence_ids', []),
        'control_evidence_ids': comparison.get('control_evidence_ids', []),
        'notes': comparison.get('notes', ''),
    }
