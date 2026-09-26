import json
import pytest
from app.pipeline_stages import bind_intake_evidence
from app.skill_loader import contract
from test_codex_adapter import fixture_assessment,material


def setup_evidence():
    assessment=contract.Assessment.model_validate(fixture_assessment())
    assessment.evidence_index[0].quote='示例探针（规定条件下）完成光谱验证。'
    intake={'evidence':[{k:getattr(e,k) for k in ('id','material_id','locator','quote')}
                        for e in assessment.evidence_index]}
    materials=material()
    materials[0]['text']='示例探针（规定条件下）完成光谱验证。\n示例探针属于测试项目。'
    return assessment,intake,materials


def test_model_omitted_parentheses_are_restored_from_frozen_source(tmp_path):
    assessment,intake,materials=setup_evidence()
    assessment.evidence_index[0].quote='示例探针完成光谱验证。'
    assessment.evidence_index[0].locator='模型改写的位置'
    with pytest.raises(ValueError,match='原文'):contract.validate_materials(assessment,materials)
    bound=bind_intake_evidence(assessment,intake,materials,tmp_path)
    assert bound.evidence_index[0].quote==intake['evidence'][0]['quote']
    assert bound.evidence_index[0].locator=='第1段'
    assert assessment.evidence_index[0].quote=='示例探针完成光谱验证。'
    assert bound.level_reasons==assessment.level_reasons
    journal=json.loads((tmp_path/'project-evidence-binding.json').read_text(encoding='utf-8'))
    assert {c['field'] for c in journal['corrections']}=={'quote','locator'}
    assert (tmp_path/'assessment.json').is_file()


@pytest.mark.parametrize('fault',['unknown_id','wrong_material','invalid_original'])
def test_invalid_source_identity_or_original_still_fails(tmp_path,fault):
    assessment,intake,materials=setup_evidence()
    if fault=='unknown_id':intake['evidence'][0]['id']='other'
    elif fault=='wrong_material':assessment.evidence_index[0].material_id='other'
    else:intake['evidence'][0]['quote']='不在任何原始材料中的内容'
    with pytest.raises(ValueError):bind_intake_evidence(assessment,intake,materials,tmp_path)
    assert not (tmp_path/'assessment.json').exists()


def test_external_evidence_is_not_relabelled_as_project_material(tmp_path):
    assessment,intake,materials=setup_evidence()
    external=contract.Evidence(id='X1',title='外部页面',kind='external',material_id=None,
        source='外部页面',locator='正文',quote='外部摘录',url='https://example.org/',date=None,
        supports='背景',does_not_prove='项目效果',verification='not_verified')
    assessment.evidence_index.append(external)
    bound=bind_intake_evidence(assessment,intake,materials,tmp_path)
    assert bound.evidence_index[-1]==external
