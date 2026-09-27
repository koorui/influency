"""Expert rule delivery, input readiness, and provenance; no model calls."""
import json
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from app.pipeline_model import execute_json_stage,preserve_frozen_card
from app.pipeline_stages import wu_intake_stage
from app.pipeline_store import WaitingForInput
from app.pipeline_v19 import evaluation_handoff, wrapper
from app.skill_loader import SKILL_ROOT, contract
from app.unified_evaluation import combine_evaluations
from test_codex_adapter import fixture_assessment


def test_evaluation_cannot_replace_frozen_card_with_external_background():
    source=fixture_assessment()
    response=json.loads(json.dumps(source))
    response['outcome_card'][0]['value']='评价阶段自行扩大对象'
    response['outcome_card'][0]['evidence_ids']=['external-background']
    before=json.dumps(response)
    bound,changes=preserve_frozen_card(response,{'intake':{'outcome_card':source['outcome_card']}})
    assert bound['outcome_card']==source['outcome_card']
    assert len(changes)==1
    assert json.dumps(response)==before
    assert bound['current_level']==response['current_level']
    assert bound['level_reasons']==response['level_reasons']
    contract.Assessment.model_validate(bound)


def test_numbered_label_normalization_keeps_grade_and_evidence_and_rejects_wrong_name():
    value=fixture_assessment()
    for dimension in value['dimensions']:
        dimension['grade']='G1'
        dimension['gaps']=['本轮材料未建立更高档依据']
    before=json.dumps(value,ensure_ascii=False)
    value['level_name']=f"L{value['current_level']} {value['level_name']}"
    for key in ('upgrade_plus_1','upgrade_plus_2'):
        u=value[key]
        if u:u['level_name']=f"L{u['target_level']} {u['level_name']}"
    normalized,corrections=contract.normalize_level_labels(value)
    assert len(corrections)==3
    assert json.dumps(normalized,ensure_ascii=False)==before
    contract.LegacyFinalAssessment.model_validate(normalized)
    assert value['level_name'].startswith('L')
    value['level_name']='L2 '+contract.LEVELS[0]
    wrong,_=contract.normalize_level_labels(value)
    with pytest.raises(ValueError):contract.LegacyFinalAssessment.model_validate(wrong)


@pytest.mark.parametrize('ready', [False, True])
def test_validation_gap_preserves_card_and_only_blocks_unready_input(tmp_path, monkeypatch, ready):
    fixture = fixture_assessment()
    original = [{k: e[k] for k in ('id', 'material_id', 'locator', 'quote')}
                for e in fixture['evidence_index']]

    def execute(folder, model, payload, instruction, **kwargs):
        return model(status='ready' if ready else 'insufficient_validation_evidence',
                     project_name='测试项目', canonical_name='示例探针', confidence='high',
                     candidates=[{'name': '示例探针', 'scope': '冻结成果', 'evidence_ids': ['P1', 'P2']}],
                     outcome_card=fixture['outcome_card'],
            evaluation_objects=[{'id':'primary','name':'示例探针','kind':'探针','version':'本期','relation_to_primary':'primary','evidence_ids':['P1']}],primary_object_id='primary', evidence=original,
                     factors=[], comparisons=[], claims=[],
                     gaps=['没有外部使用证据'] if ready else ['本轮材料没有提供基本验证结果'])

    monkeypatch.setattr('app.pipeline_stages.execute_json_stage', execute)
    inputs = {'project_id': 'P', 'outcome_id': 'O', 'project_name': '测试项目',
              'title': '示例探针', 'confirmed_scope': '示例探针',
              'materials': [{'id': 'material-1', 'filename': '原始材料.txt',
                             'text': '\n'.join(e['quote'] for e in original)}]}
    if ready:
        result = wu_intake_stage(inputs, {}, tmp_path)
        assert result['intake']['status'] == 'ready'
    else:
        # A located but unvalidated outcome continues as an explicit gap, not a fabricated L1.
        result=wu_intake_stage(inputs, {}, tmp_path)
        assert result['intake']['status']=='insufficient_validation_evidence'
        assert result['intake']['gaps']
    saved = json.loads((tmp_path / 'outcome-intake.json').read_text(encoding='utf-8'))
    assert saved['outcome_card'] == fixture['outcome_card']
    assert saved['evidence'] == original


def test_actual_transport_includes_shared_expert_rules(tmp_path, monkeypatch):
    class Reply(BaseModel):
        message: str

    cfg = SimpleNamespace(codex_max_input_chars=2000000, codex_reasoning_effort='medium',
                          codex_sandbox_mode='read-only', codex_model='test-model', codex_timeout_seconds=5)
    monkeypatch.setattr('app.pipeline_model.settings', lambda: cfg)
    monkeypatch.setattr('app.pipeline_model.codex_command', lambda: ['not-a-real-model'])
    monkeypatch.setattr('app.pipeline_model.configured_model', lambda: 'test-model')
    captured = {}

    class Process:
        returncode = 0

        def __init__(self, args, **kwargs):
            self.folder = kwargs['cwd']

        def communicate(self, prompt, timeout):
            captured['prompt'] = prompt.decode('utf-8')
            (self.folder / 'response.json').write_text('{"message":"ok"}', encoding='utf-8')

    monkeypatch.setattr('app.pipeline_model.subprocess.Popen', Process)
    result = execute_json_stage(tmp_path, Reply, {'title': '示例成果'},
                                'Execute only the requested phase.', inline_input=True)
    assert result.message == 'ok'
    rules = (SKILL_ROOT / 'references/expert-method.md').read_text(encoding='utf-8')
    assert rules in captured['prompt']
    assert (tmp_path / 'skill/references/expert-method.md').read_text(encoding='utf-8') == rules
    wrapper()
    from metric_judgment import indicator_product as product
    for name in ('D_DIMENSION_SYSTEM_PROMPT', 'OUTCOME_SYNTHESIS_SYSTEM_PROMPT', 'PROJECT_SYNTHESIS_SYSTEM_PROMPT'):
        assert rules in getattr(product, name)
    assert product.RUBRIC_VERSION == contract.RUBRIC_VERSION
    assert product.GRADING_VERSION == contract.GRADING_VERSION


@pytest.mark.parametrize('version', [None, 'grading-20260925-1930', contract.GRADING_VERSION])
def test_handoff_preserves_executed_version_and_never_upgrades_old_results(version):
    scope = {'project_id': 'P', 'outcome_id': 'O'}
    metadata = {} if version is None else {'rubric_version': contract.RUBRIC_VERSION, 'grading_standard': version}
    result = {'run': metadata, 'outcomes': [
        {'outcome_id': 'O', 'synthesis': {'impact_level': {'level': 'L1'}},
         'dimensions': [{'dimension_id': f'D{i}', 'grade': {'level': 'G1'}} for i in range(1, 8)]}
    ]}
    before = json.dumps(result)
    dimensions = evaluation_handoff(scope, result)
    assert dimensions['grading_standard'] == version
    assert json.dumps(result) == before
    management = {**scope, 'rubric_version': contract.RUBRIC_VERSION,
                  'grading_standard': contract.GRADING_VERSION,
                  'assessment': {'current_level': 1,
                                 'dimensions': [{'id': f'D{i}', 'grade': 'G1'} for i in range(1, 8)]}}
    combined = combine_evaluations(management, dimensions)
    assert combined['comparison'] == ('consistent' if version == contract.GRADING_VERSION else 'legacy_or_mixed')
    assert combined['grading_standard'] == (version if version == contract.GRADING_VERSION else None)
