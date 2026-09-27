"""Unified evaluation contract with backward-compatible v2 report structure.
This module validates structure and reference integrity,
not the scientific truth of an evaluation. Requires pydantic >= 2.7.
"""
import json
import copy
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator

STANDARD = json.loads((Path(__file__).resolve().parents[1]/'references/grading-standard-20260925.json').read_text(encoding='utf-8'))
RUBRIC_VERSION = 'unified-double-layer-impact.v1'
GRADING_VERSION = STANDARD['version']
LEVELS = [STANDARD['levels'][f'L{i}']['name'] for i in range(1,7)]
CARD_FIELDS = {'outcome_name', 'outcome_type', 'description', 'problem_solved', 'participating_units', 'core_members', 'related_outputs', 'key_metrics', 'baseline', 'ai_role', 'claimed_application', 'support_materials'}


def normalize_level_labels(value):
    """Accept an exact numbered label, without changing any grade or interpretation."""
    value=copy.deepcopy(value)
    corrections=[]
    fields=[('level_name',value,value.get('current_level'))]
    fields += [(key+'.level_name',value[key],value[key].get('target_level'))
               for key in ('upgrade_plus_1','upgrade_plus_2') if isinstance(value.get(key),dict)]
    for field,record,level in fields:
        if type(level) is not int or not 1<=level<=6:continue
        expected=LEVELS[level-1]
        original=record.get('level_name')
        if original in (f'L{level} {expected}',f'L{level}{expected}'):
            record['level_name']=expected
            corrections.append({'field':field,'original':original,'normalized':expected})
    topic_aliases={'成果价值与基本有效性':'成果价值与先进性','AI与项目新增贡献':'AI与项目贡献','实际影响与对象边界':'实际影响'}
    if value.get('schema_version')=='outcome-evaluation.v3':
        for index,judgment in enumerate(value.get('key_judgments',[])):
            original=judgment.get('topic')
            if original in topic_aliases:
                judgment['topic']=topic_aliases[original]
                corrections.append({'field':f'key_judgments.{index}.topic','original':original,'normalized':judgment['topic']})
    return value,corrections


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
    assessment_state: Literal['assessed','insufficient_evidence','not_applicable','conflict','not_assessed'] | None = None


class Reason(Strict):
    text: str = Field(min_length=1, max_length=3000)
    kind: Literal['support', 'boundary']
    evidence_ids: list[str]


class Upgrade(Strict):
    target_level: int = Field(ge=2, le=6)
    level_name: str = Field(description='纯中文等级名称，不包含L编号',json_schema_extra={'enum':LEVELS})
    need: str
    proof_materials: list[str]


class NextTask(Strict):
    title: str
    summary: str
    body: str
    fact_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class NextTasks(Strict):
    project_material: NextTask | None
    expert_review: NextTask | None
    observation: NextTask | None = None
    maintenance: NextTask | None = None


class Attribution(Strict):
    ai_role: str
    baseline: str
    confirmed_increment: str
    confounders: list[str]
    evidence_ids: list[str]
    gaps: list[str]


class ImpactUse(Strict):
    object_id: str = Field(min_length=1)
    user: str = Field(min_length=1)
    task: str = Field(min_length=1)
    result: str = Field(min_length=1)
    relationship: Literal['internal','collaborator','independent','unknown']
    relationship_basis: str
    evidence_ids: list[str] = Field(min_length=1)
    independence_evidence_ids: list[str]


class ImpactFact(Strict):
    id: str = Field(min_length=1)
    category: Literal['F1','F2','F3','F4','F5','F6']
    object_id: str = Field(min_length=1)
    fact_text: str = Field(min_length=1)
    assessment_status: Literal['completed','pending','not_applicable']
    state: Literal['verified','possibly_happened_but_unverified','not_found_as_of_cutoff','conflict'] | None
    evidence_ids: list[str]
    counter_evidence_ids: list[str]
    event_date: str | None
    time_basis: str
    search_coverage: str
    needs_expert_confirmation: bool
    notes: str

    @model_validator(mode='after')
    def fact_state(self):
        if (self.assessment_status=='completed') != (self.state is not None):
            raise ValueError('待检查或不适用事实不得标成未发现；完成核验须有状态')
        if self.state=='verified' and (not self.evidence_ids or not self.time_basis.strip()):
            raise ValueError('已核验事实需要原始依据与时间资格说明')
        if self.state=='conflict' and not self.counter_evidence_ids:
            raise ValueError('冲突事实须保留反对依据')
        return self


class ValueJudgment(Strict):
    conclusion: str
    evidence_ids: list[str]
    limitations: list[str]


class ValueAxes(Strict):
    scientific_or_technical_value: ValueJudgment
    project_additionality: ValueJudgment
    ai_contribution: ValueJudgment
    future_potential: ValueJudgment
    management_action: ValueJudgment


class FactLedger(Strict):
    schema_version: Literal['outcome-facts.v1']
    project_id: str
    outcome_id: str
    primary_object_id: str
    evaluation_cutoff: str
    impact_facts: list[ImpactFact]
    claims: list[Claim]
    value_and_attribution: ValueAxes

    @model_validator(mode='after')
    def coverage(self):
        from datetime import date
        date.fromisoformat(self.evaluation_cutoff)
        if len({f.id for f in self.impact_facts})!=len(self.impact_facts):
            raise ValueError('事实编号重复')
        if {f.category for f in self.impact_facts}!={f'F{i}' for i in range(1,7)}:
            raise ValueError('事实账本须说明F1—F6的核验状态')
        if any(f.object_id!=self.primary_object_id for f in self.impact_facts):
            raise ValueError('影响事实不得借用关联对象的作用')
        return self


class Assessment(Strict):
    schema_version: Literal['wu-outcome-v2.1','outcome-evaluation.v3']
    rubric_id: Literal['unified-double-layer-impact.v1', 'wu-v2-six-levels']
    input_mode: Literal['name_only', 'name_plus_materials', 'structured_form']
    project_context: ProjectContext
    outcome_resolution: Resolution
    outcome_card: list[CardField]
    evaluation_status: Literal['formal', 'preliminary', 'insufficient_project_context', 'needs_scope_confirmation','system_preliminary']
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
    impact_uses: list[ImpactUse] = Field(default_factory=list)
    fact_ledger: FactLedger | None = None
    attainment_fact_ids: list[str] = Field(default_factory=list)
    boundary_fact_ids: list[str] = Field(default_factory=list)
    stage_references: list[Upgrade] = Field(default_factory=list)

    @model_validator(mode='after')
    def integrity(self):
        modern = self.schema_version == 'outcome-evaluation.v3'
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
        groups += [ids for x in self.impact_uses for ids in (x.evidence_ids,x.independence_evidence_ids)]
        groups += [t.evidence_ids for t in (self.next_tasks.project_material,self.next_tasks.expert_review,self.next_tasks.observation,self.next_tasks.maintenance) if t]
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
            if dimension.grade and not dimension.evidence_ids and not (not modern and dimension.grade=='G1' and dimension.gaps):
                raise ValueError('每个已评定G档均须原始依据；新版缺证应留空G并说明状态' if modern else 'G2及以上须引用证据；G1缺少引文时须说明本轮证据边界')
            if modern and (dimension.assessment_state is None or
                (dimension.assessment_state=='assessed') != (dimension.grade is not None)):
                raise ValueError('已评定维度须有G，其余状态须为空；缺证不等于G1')
        if self.current_level is not None:
            if self.evaluation_status != ('system_preliminary' if modern else 'formal') or self.level_name != LEVELS[self.current_level-1]:
                raise ValueError('等级须与评价状态及当前六级名称匹配')
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
            independent_use=any(u.relationship=='independent' and u.relationship_basis.strip() and u.independence_evidence_ids for u in self.impact_uses)
            if self.current_level >= 3 and not independent_use and not any(e.kind=='external' and e.verification=='verified' for e in self.evidence_index):
                raise ValueError('L3及以上需要独立外部证据')
        if modern:
            self.validate_facts(evidence)
            return self
        for offset, upgrade in [(1,self.upgrade_plus_1),(2,self.upgrade_plus_2)]:
            target = self.current_level + offset if self.current_level else None
            if target and target <= 6:
                if not upgrade or upgrade.target_level != target or upgrade.level_name != LEVELS[target-1]:
                    raise ValueError('升级路径必须对应当前等级加1或加2')
            elif upgrade:
                raise ValueError('未分级或超过L6时升级项须为null')
        return self

    def validate_facts(self, evidence):
        if self.evaluation_status in ('needs_scope_confirmation','insufficient_project_context'):
            if self.current_level is not None or self.level_name is not None or self.fact_ledger is not None or self.stage_references or self.upgrade_plus_1 or self.upgrade_plus_2 or any(d.grade for d in self.dimensions):
                raise ValueError('对象或上下文未定位时须留空等级、事实账本和阶段参考')
            return
        if {j.topic for j in self.key_judgments}!={'成果价值与先进性','AI与项目贡献','实际影响'} or len(self.key_judgments)!=3:
            raise ValueError('新版首页须保留三个关键问题，分项价值在账本中独立记录')
        ledger=self.fact_ledger
        if ledger is None:raise ValueError('新版评价须绑定冻结事实账本')
        facts={f.id:f for f in ledger.impact_facts}
        refs=[f.evidence_ids+f.counter_evidence_ids for f in ledger.impact_facts]
        refs += [c.evidence_ids for c in ledger.claims]
        refs += [v['evidence_ids'] for v in ledger.value_and_attribution.model_dump().values()]
        if any(not set(ids).issubset(evidence) for ids in refs):raise ValueError('事实账本引用未知证据')
        if not set(self.attainment_fact_ids+self.boundary_fact_ids).issubset(facts):raise ValueError('引用未知事实')
        if any(set(t.fact_ids)-facts.keys() for t in (self.next_tasks.project_material,self.next_tasks.expert_review,self.next_tasks.observation,self.next_tasks.maintenance) if t):
            raise ValueError('任务引用未知事实')
        if any(facts[i].state!='verified' for i in self.attainment_fact_ids):raise ValueError('达级依据必须是已核验事实')
        if self.current_level is not None:
            if not any(facts[i].category==f'F{self.current_level}' for i in self.attainment_fact_ids):raise ValueError('建议等级须有相应作用状态的达级事实')
            if len(self.outcome_resolution.candidate_outcomes)!=1:raise ValueError('定级须定位唯一成果')
        if self.current_level and self.current_level>=2 and not self.impact_uses:raise ValueError('L2及以上须有真实使用依据')
        if self.current_level and self.current_level>=3 and not any(u.relationship=='independent' and u.relationship_basis.strip() and u.independence_evidence_ids for u in self.impact_uses):
            raise ValueError('L3及以上须有独立采用及关系依据')
        if self.current_level is None and self.level_name is not None:raise ValueError('未定级时名称也须为空')
        if self.upgrade_plus_1 or self.upgrade_plus_2:raise ValueError('新版不使用固定加一级/两级字段')
        for stage in self.stage_references:
            if self.current_level is None or stage.target_level<=self.current_level or stage.level_name!=LEVELS[stage.target_level-1]:
                raise ValueError('阶段参考须对应更高的有效影响状态')
        if any(u.object_id!=ledger.primary_object_id for u in self.impact_uses):raise ValueError('实际作用链对象错误')
        if self.evaluation_status!='system_preliminary':raise ValueError('模型只能生成系统初判')
        if self.current_level is not None and (self.project_context.status!='resolved' or not self.outcome_resolution.canonical_name):
            raise ValueError('未定位项目及成果时不能定级')


def validate_materials(assessment: Assessment, materials: list[dict], confirmed_scope: str = ''):
    import re
    texts = {m['id']: re.sub(r'\s+', '', m['text']) for m in materials}
    for ev in assessment.evidence_index:
        if ev.kind == 'project':
            if ev.material_id not in texts or re.sub(r'\s+', '', ev.quote) not in texts[ev.material_id]:
                raise ValueError(f'证据 {ev.id} 的原文不在绑定材料中')
    if assessment.evaluation_status == 'formal' or (assessment.schema_version=='outcome-evaluation.v3' and assessment.current_level is not None):
        r = assessment.outcome_resolution
        if r.resolution_confidence != 'high' and confirmed_scope.strip() != r.canonical_name:
            raise ValueError('中低置信成果须由管理员确认范围后重新评价')
        if r.resolution_confidence == 'high':
            locations = {(e.material_id,re.sub(r'\s+', '', e.quote)) for e in assessment.evidence_index if e.kind=='project' and e.id in r.source_refs}
            if len(locations) < 2 and confirmed_scope.strip() != r.canonical_name:
                raise ValueError('自动确认需要至少两处项目原始依据')


def validate_completed_assessment(assessment):
    if assessment.schema_version=='outcome-evaluation.v3':
        if assessment.evaluation_status!='system_preliminary':raise ValueError('对象或上下文尚未定位，不能作为完成报告交付')
        if any(d.assessment_state in (None,'not_assessed') for d in assessment.dimensions):
            raise ValueError('七维尚未完成审阅')
        return
    if assessment.evaluation_status!='formal' or assessment.current_level is None:
        raise ValueError('完成评价须按现有证据给出明确L级，证据局限写入判断边界')
    if any(d.grade is None for d in assessment.dimensions):
        raise ValueError('完成评价须给出全部七维G级，不能以待核验代替结论')


class LegacyFinalDimension(Dimension):
    grade: Literal['G1','G2','G3','G4','G5']


class LegacyFinalAssessment(Assessment):
    schema_version: Literal['wu-outcome-v2.1']
    evaluation_status: Literal['formal']
    current_level: int = Field(ge=1,le=6)
    dimensions: list[LegacyFinalDimension]

    @model_validator(mode='after')
    def legacy_use_boundary(self):
        if self.current_level>=2 and not self.impact_uses:raise ValueError('L2及以上须有真实使用依据')
        if self.current_level>=3 and not any(u.relationship=='independent' and u.relationship_basis.strip() and u.independence_evidence_ids for u in self.impact_uses):
            raise ValueError('L3及以上须有独立采用及关系依据')
        return self


class FinalDimension(Dimension):
    assessment_state: Literal['assessed','insufficient_evidence','not_applicable','conflict']


class FinalJudgment(Judgment):
    topic: Literal['成果价值与先进性','AI与项目贡献','实际影响']


class CurrentAssessment(Assessment):
    schema_version: Literal['outcome-evaluation.v3']
    evaluation_status: Literal['system_preliminary','needs_scope_confirmation','insufficient_project_context']


class FinalAssessment(CurrentAssessment):
    evaluation_status: Literal['system_preliminary']
    current_level: int | None = Field(ge=1,le=6)
    level_name: str | None
    dimensions: list[FinalDimension]
    key_judgments: list[FinalJudgment]
    fact_ledger: FactLedger

    @model_validator(mode='after')
    def actual_use_boundary(self):
        if self.current_level and self.current_level>=2 and not self.impact_uses:
            raise ValueError('L2及以上须提供主评价对象的使用者、真实任务、结果与证据')
        if self.current_level and self.current_level>=3 and not any(u.relationship=='independent' and u.relationship_basis.strip() and u.independence_evidence_ids for u in self.impact_uses):
            raise ValueError('L3及以上须有实际使用及独立性依据，背景论文不能代替独立采用')
        return self


def cli_schema():
    schema = CurrentAssessment.model_json_schema()
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
