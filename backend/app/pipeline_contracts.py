"""Handoffs preserve identities and provenance; analysis is never relabelled as evidence."""
from typing import Literal
from pydantic import Field, model_validator
from .schema import StrictModel
from .skill_loader import contract


class Factor(StrictModel):
    id: str
    name: str
    type: str
    role: str
    role_in_attribution: Literal['baseline','contributor','target']
    evaluate_independent_increment: bool


class Measurement(StrictModel):
    label: str
    value: float = Field(allow_inf_nan=False)
    unit: str


class Comparison(StrictModel):
    id: str
    name: str
    baseline: Measurement
    observed: Measurement
    direction: Literal['lower_is_better','higher_is_better','descriptive_only']
    comparability_status: Literal['established','partial','unknown']
    evidence_ids: list[str]
    involved_factor_ids: list[str]
    isolated_factor_ids: list[str]
    notes: str
    comparison_kind: Literal['threshold_check','performance_change','external_benchmark','causal_increment','unspecified'] = 'unspecified'
    baseline_evidence_ids: list[str] = Field(default_factory=list)
    observed_evidence_ids: list[str] = Field(default_factory=list)
    control_evidence_ids: list[str] = Field(default_factory=list)
    controlled_conditions: str = ''

    @model_validator(mode='after')
    def attribution_boundary(self):
        if not self.evidence_ids:
            raise ValueError('比较必须引用基线与观测值的原文依据')
        if not set(self.isolated_factor_ids).issubset(self.involved_factor_ids):
            raise ValueError('隔离因素必须属于本次比较因素')
        if len(set(self.isolated_factor_ids))>1:
            raise ValueError('一个对照不能同时证明多个因素各自的独立贡献；请拆分独立对照或保留组合效果')
        if self.comparability_status=='established' and self.baseline.unit.strip()!=self.observed.unit.strip():
            raise ValueError('比较两侧单位不一致，请核实换算依据')
        if not set(self.baseline_evidence_ids+self.observed_evidence_ids+self.control_evidence_ids).issubset(self.evidence_ids):
            raise ValueError('基线、观测和对照依据须属于本项比较证据')
        return self


class PreparedClaim(StrictModel):
    id: str
    text: str
    factor_id: str | None
    evidence_ids: list[str]


class AttributionMeasurement(Measurement):
    """DCA v1 permits omitted display labels and units."""
    model_config = {'extra': 'allow'}
    label: str = ''
    unit: str = ''


class AttributionComparison(Comparison):
    """Validate handoffs without imposing the model-generation schema on DCA v1."""
    model_config = {'extra': 'allow'}
    baseline: AttributionMeasurement
    observed: AttributionMeasurement
    notes: str = ''

    @model_validator(mode='after')
    def attribution_boundary(self):
        # Missing units stay unknown, as in the DCA engine; never invent a unit.
        if not self.evidence_ids:
            raise ValueError('比较必须引用基线与观测值的原文依据')
        if not set(self.isolated_factor_ids).issubset(self.involved_factor_ids):
            raise ValueError('隔离因素必须属于本次比较因素')
        if len(set(self.isolated_factor_ids))>1:
            raise ValueError('一个对照不能同时证明多个因素各自的独立贡献')
        if self.comparability_status=='established' and self.baseline.unit.strip() and self.observed.unit.strip() and self.baseline.unit.strip()!=self.observed.unit.strip():
            raise ValueError('比较两侧单位不一致，请核实换算依据')
        if not set(self.baseline_evidence_ids+self.observed_evidence_ids+self.control_evidence_ids).issubset(self.evidence_ids):
            raise ValueError('比较两侧及对照引用不属于比较证据')
        return self


class IntakeEvidence(StrictModel):
    id: str
    material_id: str
    locator: str
    quote: str


class IntakeCandidate(StrictModel):
    name: str
    scope: str
    evidence_ids: list[str]


class EvaluationObject(StrictModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    kind: str
    version: str
    relation_to_primary: Literal['primary','method','product','component','prior_basis']
    evidence_ids: list[str] = Field(min_length=1)


class UseRecord(StrictModel):
    object_id: str
    phase: Literal['validation','real_task']
    user: str
    task: str
    result: str
    relationship: Literal['internal','collaborator','independent','unknown']
    relationship_basis: str
    event_date: str | None
    evidence_ids: list[str] = Field(min_length=1)


class WuIntake(StrictModel):
    status: Literal['ready','needs_scope_confirmation','insufficient_project_context','insufficient_validation_evidence']
    project_name: str | None
    canonical_name: str | None
    confidence: Literal['high','medium','low']
    candidates: list[IntakeCandidate]
    outcome_card: list[contract.CardField]
    evidence: list[IntakeEvidence]
    factors: list[Factor]
    comparisons: list[Comparison]
    claims: list[PreparedClaim]
    gaps: list[str]
    evaluation_objects: list[EvaluationObject] = Field(default_factory=list)
    primary_object_id: str | None = None
    use_records: list[UseRecord] = Field(default_factory=list)

    @model_validator(mode='after')
    def integrity(self):
        ids={e.id for e in self.evidence}
        if len(ids)!=len(self.evidence):raise ValueError('成果定位证据编号重复')
        if {f.name for f in self.outcome_card}!=contract.CARD_FIELDS or len(self.outcome_card)!=12:
            raise ValueError('成果定位必须保留12个卡片字段')
        for item in [*self.candidates,*self.outcome_card,*self.comparisons,*self.claims]:
            if not set(item.evidence_ids).issubset(ids):raise ValueError('成果定位引用不存在的证据')
        if self.status=='ready' and (not self.project_name or not self.canonical_name or len(self.candidates)!=1):
            raise ValueError('进入评价需要明确项目和唯一成果')
        factors={f.id for f in self.factors}
        if len(factors)!=len(self.factors):raise ValueError('贡献因素编号重复')
        if len({c.id for c in self.comparisons})!=len(self.comparisons) or len({c.id for c in self.claims})!=len(self.claims):
            raise ValueError('比较或声明编号重复')
        if any(set(c.involved_factor_ids+c.isolated_factor_ids)-factors for c in self.comparisons):
            raise ValueError('比较引用不存在的贡献因素')
        if any(c.factor_id and c.factor_id not in factors for c in self.claims):
            raise ValueError('声明引用不存在的贡献因素')
        objects={o.id for o in self.evaluation_objects}
        if len(objects)!=len(self.evaluation_objects):raise ValueError('评价对象编号重复')
        if self.evaluation_objects:
            primary=[o for o in self.evaluation_objects if o.relation_to_primary=='primary']
            if len(primary)!=1 or primary[0].id!=self.primary_object_id:
                raise ValueError('必须明确唯一主评价对象，关联方法和产品分别记录')
        elif self.primary_object_id or self.use_records:
            raise ValueError('使用事实必须对应已定义的评价对象')
        if any(set(o.evidence_ids)-ids for o in [*self.evaluation_objects,*self.use_records]):
            raise ValueError('评价对象或使用事实引用不存在的证据')
        if any(u.object_id not in objects for u in self.use_records):raise ValueError('使用事实引用未知对象')
        return self


class ScopedEvidence(StrictModel):
    id: str = Field(min_length=1,max_length=160)
    project_id: str = Field(min_length=1,max_length=100)
    outcome_id: str = Field(min_length=1,max_length=160)
    source_type: Literal['project','search']
    locator: str = Field(min_length=1)
    text: str = Field(min_length=1)
    url: str | None = None


class CurrentWuIntake(WuIntake):
    @model_validator(mode='after')
    def object_required_for_new_run(self):
        if self.status in ('ready','insufficient_validation_evidence') and (not self.evaluation_objects or not self.primary_object_id):
            raise ValueError('新建卡须明确主评价对象及关联对象边界')
        return self


class ReplayFinding(StrictModel):
    id: str
    status: Literal['conflicts','not_found','needs_expert']
    statement: str
    reason: str
    related_claim_ids: list[str]
    evidence_ids: list[str]


class SearchReplay(StrictModel):
    schema_version: Literal['search-replay.v1']
    project_id: str
    outcome_id: str
    mode: Literal['historical_replay','live_search']
    original_run_id: str = Field(min_length=1)
    original_completed_at: str = Field(min_length=1)
    source_label: str = Field(min_length=1)
    evidence: list[ScopedEvidence]
    findings: list[ReplayFinding]

    @model_validator(mode='after')
    def scoped(self):
        ids=[e.id for e in self.evidence]
        if len(ids)!=len(set(ids)):raise ValueError('Search证据ID重复')
        if len({f.id for f in self.findings})!=len(self.findings):raise ValueError('Search发现ID重复')
        for e in self.evidence:
            if e.project_id!=self.project_id or e.outcome_id!=self.outcome_id or e.source_type!='search':
                raise ValueError('Search回放只能包含同项目、同成果的检索证据')
        # A finding may refer to a project claim's original evidence. Validate
        # those IDs only after joining the frozen project's evidence below.
        return self


class AttributionPreparation(StrictModel):
    """These are source-backed extracted inputs, not previous evaluator conclusions."""
    schema_version: Literal['attribution-preparation.v1']
    project_id: str
    project_name: str
    outcome_id: str
    outcome_name: str
    evidence: list[ScopedEvidence]
    factors: list[dict]
    comparisons: list[dict]
    claims: list[dict]

    @model_validator(mode='after')
    def scoped(self):
        ids=[e.id for e in self.evidence]
        if len(ids)!=len(set(ids)):raise ValueError('项目证据ID重复')
        for e in self.evidence:
            if e.project_id!=self.project_id or e.outcome_id!=self.outcome_id or e.source_type!='project':
                raise ValueError('归因准备材料必须是同项目同成果的项目证据')
        return self


def attribution_input(preparation: AttributionPreparation,replay: SearchReplay):
    if (preparation.project_id,preparation.outcome_id)!=(replay.project_id,replay.outcome_id):
        raise ValueError('Search回放与当前归因对象不一致')
    # Validate this boundary for direct/replayed inputs as well as model intake.
    for value in preparation.comparisons:
        AttributionComparison.model_validate(value)
    evidence=[*preparation.evidence,*replay.evidence]
    ids=[e.id for e in evidence]
    if len(set(ids))!=len(ids):raise ValueError('项目与Search证据ID冲突，不能覆盖')
    claim_ids={c.get('id') for c in preparation.claims}
    if any(not set(f.related_claim_ids).issubset(claim_ids) for f in replay.findings):
        raise ValueError('Search发现关联的声明不存在')
    if any(not set(f.evidence_ids).issubset(ids) for f in replay.findings):
        raise ValueError('Search发现引用不在当前成果证据集合中')
    return {
        'schema_version':'dca-attribution-input/v1',
        'project':{'id':preparation.project_id,'name':preparation.project_name},
        'target':{'id':preparation.outcome_id,'name':preparation.outcome_name},
        'evidence':[{'id':e.id,'source_type':e.source_type,'locator':e.locator,'text':e.text} for e in evidence],
        'factors':preparation.factors,'comparisons':preparation.comparisons,'claims':preparation.claims,
        'search_findings':[f.model_dump() for f in replay.findings],
    }
