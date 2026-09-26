"""Unified evaluation contract with backward-compatible v2 report structure.
This module validates structure and reference integrity,
not the scientific truth of an evaluation. Requires pydantic >= 2.7.
"""
import json
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

STANDARD = json.loads((Path(__file__).resolve().parents[1]/'references/grading-standard-20260925.json').read_text(encoding='utf-8'))
RUBRIC_VERSION = 'unified-double-layer-impact.v1'
GRADING_VERSION = STANDARD['version']
LEVELS = [STANDARD['levels'][f'L{i}']['name'] for i in range(1,7)]
CARD_FIELDS = {'outcome_name', 'outcome_type', 'description', 'problem_solved', 'participating_units', 'core_members', 'related_outputs', 'key_metrics', 'baseline', 'ai_role', 'claimed_application', 'support_materials'}


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class ProjectContext(Strict):
    status: Literal['resolved', 'ambiguous', 'missing']
    project_name: str | None
    project_id: str | None
    source: str | None


class Candidate(Strict):
    name: str
    scope: str
    evidence_ids: list[str]


class Resolution(Strict):
    user_query: str
    canonical_name: str | None
    aliases: list[str]
    resolution_confidence: Literal['high', 'medium', 'low']
    candidate_outcomes: list[Candidate]
    scope_note: str
    source_refs: list[str]


class CardField(Strict):
    name: Literal['outcome_name', 'outcome_type', 'description', 'problem_solved', 'participating_units', 'core_members', 'related_outputs', 'key_metrics', 'baseline', 'ai_role', 'claimed_application', 'support_materials']
    value: str
    status: Literal['confirmed', 'partial', 'missing']
    evidence_ids: list[str]


class Evidence(Strict):
    id: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=255)
    kind: Literal['project', 'external']
    material_id: str | None
    source: str = Field(min_length=1, max_length=500)
    locator: str = Field(min_length=1, max_length=200)
    quote: str = Field(min_length=1, max_length=10000)
    url: str | None
    date: str | None
    supports: str
    does_not_prove: str
    verification: Literal['project_statement', 'verified', 'not_verified']


class Claim(Strict):
    text: str
    evidence_ids: list[str]
    status: Literal['supported_by_project_material', 'partially_supported', 'wording_only', 'conflict', 'missing']


class Judgment(Strict):
    topic: str
    project_claim: str
    assessment: str
    project_evidence_ids: list[str]
    evaluation_evidence_ids: list[str]


class Dimension(Strict):
    id: Literal['D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7']
    grade: Literal['G1', 'G2', 'G3', 'G4', 'G5'] | None
    conclusion: str
    evidence_ids: list[str]
    gaps: list[str]


class Reason(Strict):
    text: str = Field(min_length=1, max_length=3000)
    kind: Literal['support', 'boundary']
    evidence_ids: list[str]


class Upgrade(Strict):
    target_level: int = Field(ge=2, le=6)
    level_name: str
    need: str
    proof_materials: list[str]


class NextTask(Strict):
    title: str
    summary: str
    body: str


class NextTasks(Strict):
    project_material: NextTask | None
    expert_review: NextTask | None


class Attribution(Strict):
    ai_role: str
    baseline: str
    confirmed_increment: str
    confounders: list[str]
    evidence_ids: list[str]
    gaps: list[str]


class Assessment(Strict):
    schema_version: Literal['wu-outcome-v2.1']
    rubric_id: Literal['unified-double-layer-impact.v1', 'wu-v2-six-levels']
    input_mode: Literal['name_only', 'name_plus_materials', 'structured_form']
    project_context: ProjectContext
    outcome_resolution: Resolution
    outcome_card: list[CardField]
    evaluation_status: Literal['formal', 'preliminary', 'insufficient_project_context', 'needs_scope_confirmation']
    summary: str = Field(min_length=1, max_length=10000)
    current_level: int | None = Field(ge=1, le=6)
    level_name: str | None
    level_reasons: list[Reason] = Field(min_length=1, max_length=3)
    boundary_gap: str
    key_judgments: list[Judgment] = Field(min_length=1)
    upgrade_plus_1: Upgrade | None
    upgrade_plus_2: Upgrade | None
    next_tasks: NextTasks
    evidence_index: list[Evidence]
    claims: list[Claim]
    dimensions: list[Dimension]
    ai_attribution: Attribution
    external_search_status: Literal['completed', 'not_verified']

    @model_validator(mode='after')
    def integrity(self):
        evidence = {e.id: e for e in self.evidence_index}
        if len(evidence) != len(self.evidence_index):
            raise ValueError('证据编号重复')
        if len(self.outcome_card) != 12 or {f.name for f in self.outcome_card} != CARD_FIELDS:
            raise ValueError('成果卡必须包含12个固定字段，缺失内容标记 missing')
        if len(self.dimensions) != 7 or {d.id for d in self.dimensions} != {f'D{i}' for i in range(1,8)}:
            raise ValueError('必须保留 D1–D7，无法判断的等级为 null')
        groups = [self.outcome_resolution.source_refs, self.ai_attribution.evidence_ids]
        groups += [x.evidence_ids for x in [*self.outcome_card, *self.outcome_resolution.candidate_outcomes, *self.claims, *self.dimensions, *self.level_reasons]]
        groups += [ids for x in self.key_judgments for ids in [x.project_evidence_ids, x.evaluation_evidence_ids]]
        if any(not set(ids).issubset(evidence) for ids in groups):
            raise ValueError('发现不存在的证据引用')
        for ev in self.evidence_index:
            if ev.kind == 'project' and (not ev.material_id or ev.verification != 'project_statement'):
                raise ValueError('项目材料必须绑定 material_id，不能冒充外部核验')
            if ev.kind == 'external' and (not ev.url or not ev.url.startswith(('https://','http://')) or ev.material_id):
                raise ValueError('外部证据必须有 HTTP(S) 链接且不可假冒上传材料')
        for field in self.outcome_card:
            if field.status != 'missing' and (not field.evidence_ids or any(evidence[i].kind != 'project' for i in field.evidence_ids)):
                raise ValueError('成果卡已填写字段必须来自项目材料')
        for judgment in self.key_judgments:
            if any(evidence[i].kind != 'project' for i in judgment.project_evidence_ids):
                raise ValueError('项目方主张的证据类型不匹配')
        for reason in self.level_reasons:
            if reason.kind == 'support' and not reason.evidence_ids:
                raise ValueError('正向理由必须引用证据')
        for dimension in self.dimensions:
            if dimension.grade and not dimension.evidence_ids and not (dimension.grade=='G1' and dimension.gaps):
                raise ValueError('G2及以上须引用证据；G1缺少引文时须说明本轮证据边界')
        if self.current_level is not None:
            if self.evaluation_status != 'formal' or self.level_name != LEVELS[self.current_level-1]:
                raise ValueError('只有 formal 状态可给出正式等级，名称须匹配吴老师v2口径')
        if self.evaluation_status == 'formal':
            resolution = self.outcome_resolution
            if self.current_level is None or self.project_context.status != 'resolved' or not self.project_context.project_name:
                raise ValueError('正式评价必须明确项目和等级')
            if not resolution.canonical_name or len(resolution.candidate_outcomes) != 1:
                raise ValueError('正式评价必须定位唯一成果')
            if not resolution.source_refs or not any(e.kind == 'project' for e in self.evidence_index):
                raise ValueError('正式评价必须有项目原始依据')
            if len(self.level_reasons) < 2:
                raise ValueError('正式评价至少需要两条理由')
            if self.current_level >= 3 and not any(e.kind=='external' and e.verification=='verified' for e in self.evidence_index):
                raise ValueError('L3及以上需要独立外部证据')
        for offset, upgrade in [(1,self.upgrade_plus_1),(2,self.upgrade_plus_2)]:
            target = self.current_level + offset if self.current_level else None
            if target and target <= 6:
                if not upgrade or upgrade.target_level != target or upgrade.level_name != LEVELS[target-1]:
                    raise ValueError('升级路径必须对应当前等级加1或加2')
            elif upgrade:
                raise ValueError('未分级或超过L6时升级项须为null')
        return self


def validate_materials(assessment: Assessment, materials: list[dict], confirmed_scope: str = ''):
    import re
    texts = {m['id']: re.sub(r'\s+', '', m['text']) for m in materials}
    for ev in assessment.evidence_index:
        if ev.kind == 'project':
            if ev.material_id not in texts or re.sub(r'\s+', '', ev.quote) not in texts[ev.material_id]:
                raise ValueError(f'证据 {ev.id} 的原文不在绑定材料中')
    if assessment.evaluation_status == 'formal':
        r = assessment.outcome_resolution
        if r.resolution_confidence != 'high' and confirmed_scope.strip() != r.canonical_name:
            raise ValueError('中低置信成果须由管理员确认范围后重新评价')
        if r.resolution_confidence == 'high':
            locations = {(e.material_id,e.locator,e.quote) for e in assessment.evidence_index if e.kind=='project' and e.id in r.source_refs}
            if len(locations) < 2 and confirmed_scope.strip() != r.canonical_name:
                raise ValueError('自动确认需要至少两处项目原始依据')


def validate_completed_assessment(assessment):
    if assessment.evaluation_status!='formal' or assessment.current_level is None:
        raise ValueError('完成评价须按现有证据给出明确L级，证据局限写入判断边界')
    if any(d.grade is None for d in assessment.dimensions):
        raise ValueError('完成评价须给出全部七维G级，不能以待核验代替结论')


class FinalDimension(Dimension):
    grade: Literal['G1','G2','G3','G4','G5']


class FinalAssessment(Assessment):
    evaluation_status: Literal['formal']
    current_level: int = Field(ge=1,le=6)
    level_name: str
    dimensions: list[FinalDimension]


def cli_schema():
    schema = Assessment.model_json_schema()
    def strict(node):
        if isinstance(node,dict):
            node.pop('default',None)
            if node.get('type')=='object':
                node['additionalProperties']=False
                node['required']=list(node.get('properties',{}))
            for value in node.values(): strict(value)
        elif isinstance(node,list):
            for value in node: strict(value)
    strict(schema)
    return schema
