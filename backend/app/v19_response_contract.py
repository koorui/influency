"""Typed transport of the original v19 dimension JSON (no grading-rule changes)."""
from typing import Literal
from pydantic import Field
from .schema import StrictModel

class EmptyAnalysis(StrictModel):
    pass

class Branch(StrictModel):
    branch_id: str
    status: Literal['明确成立','部分成立','尚未形成','本轮未体现','不适用']
    conclusion: str
    decisive_source_ids: list[str]

class TimeAssessment(StrictModel):
    prior_baseline: str
    current_window_increment: str
    subsequent_effect: str

class Quantity(StrictModel):
    value: float | str | None
    unit: str
    population: str
    period: str
    status: str
    deduplication: str

class Fact(StrictModel):
    fact: str = Field(min_length=1)
    source_ids: list[str] = Field(min_length=1)
    source_type: str
    supports: str
    does_not_prove: str
    effect: str
    direction: str
    outcome_ids: list[str] = Field(min_length=1)
    time_scope: str
    quantity: Quantity

class EvidenceChain(StrictModel):
    claim: str
    fact: str = Field(min_length=1)
    source_ids: list[str] = Field(min_length=1)
    outcome_ids: list[str] = Field(min_length=1)
    source_type: str
    supports: str
    does_not_prove: str
    effect: str
    direction: str
    time_scope: str
    analysis: str
    reliability: str

class Basis(StrictModel):
    source_id: str
    fact: str

class MetricUse(StrictModel):
    metric_id: str
    role: str

class ConfirmationRequest(StrictModel):
    issue: str
    method: str
    changes_judgment: bool
    professional_dispute: bool
    expected_evidence: str
    affected_judgment: str

class AIAnalysis(StrictModel):
    position: str
    mechanism: str
    observed_change: str
    controls: str
    attributable_extent: str
    confounders: list[str]
    source_ids: list[str]

class Grade(StrictModel):
    level: Literal['G1','G2','G3','G4','G5']
    reason: str
    source_ids: list[str]
    gap_to_next: str

class DimensionReply(StrictModel):
    status: Literal['明确成立','部分成立','尚未形成','本轮未体现','不适用']
    branch_judgments: list[Branch] = Field(min_length=3,max_length=3)
    core_position: str
    conclusion: str
    expert_analysis: str
    time_assessment: TimeAssessment
    evidence_chain: list[EvidenceChain]
    basis: list[Basis]
    counterevidence: list[Basis]
    professional_metric_use: list[MetricUse]
    ai_attribution: str
    missing_inputs: list[str]
    expert_question: str
    evidence_confidence: str
    judgment_confidence: str
    key_facts: list[Fact]
    confirmation_requests: list[ConfirmationRequest]
    ai_analysis: AIAnalysis | EmptyAnalysis
    grade: Grade

class ImpactLevel(StrictModel):
    level: Literal['L1','L2','L3','L4','L5','L6']
    reason: str
    source_ids: list[str]
    gap_to_next: str

class ScopeLevel(ImpactLevel):
    scope: str

class DecisiveEvidence(StrictModel):
    dimension_ids: list[str]
    source_ids: list[str]
    reason: str

class OutcomeReply(StrictModel):
    core_position: str
    innovation_conclusion: str
    influence_conclusion: str
    overall_conclusion: str
    decisive_evidence: list[DecisiveEvidence]
    main_limitations: list[str]
    expert_questions: list[str]
    next_evidence_requests: list[str]
    evidence_confidence: str
    judgment_confidence: str
    classification_reason: str
    evaluated_child_ids: list[str]
    scope_limitations: list[str]
    confirmed: str
    unconfirmed: str
    impact_level: ImpactLevel

class IncludedOutcome(StrictModel):
    outcome_id: str
    reason: str

class PortfolioEntry(StrictModel):
    coverage: str
    depth: str
    concentration: str
    conclusion: str
    included_outcomes: list[IncludedOutcome]
    key_facts: list[Fact]
    confirmation_requests: list[ConfirmationRequest]

class Portfolio(StrictModel):
    D1: PortfolioEntry
    D2: PortfolioEntry
    D3: PortfolioEntry
    D4: PortfolioEntry
    D5: PortfolioEntry
    D6: PortfolioEntry
    D7: PortfolioEntry

class Layer(StrictModel):
    status: Literal['强','较强','初步形成','尚未形成','本轮未体现']
    conclusion: str
    basis: list[str]
    limitations: list[str]

class CollaborationChain(StrictModel):
    provider: str
    consumer: str
    artifact: str
    task: str
    result: str
    source_ids: list[str]
    invocation_source_ids: list[str]
    feedback_source_ids: list[str]
    repeat_source_ids: list[str]

class SystemCollaboration(StrictModel):
    status: Literal['只有设计关系','发生真实输入输出','形成跨课题任务链','形成反馈闭环','持续重复运行','本轮未体现']
    conclusion: str
    evidence: list[str]
    gaps: list[str]
    design_basis: list[str]
    chains: list[CollaborationChain]

class InnovationSummary(StrictModel):
    project_increment: str
    contemporary_comparison: str
    ai_contribution: str

class InfluenceSummary(StrictModel):
    academic_and_reuse: str
    real_application: str
    pujiang_integration: str
    professional_response: str

class ProjectReply(StrictModel):
    dimension_portfolio: Portfolio
    specific_layer: Layer
    global_layer: Layer
    system_collaboration: SystemCollaboration
    overall_judgment: str
    leading_outcomes: list[str]
    overclaimed_outcomes: list[str]
    expert_questions: list[str]
    management_advice: list[str]
    evidence_confidence: str
    judgment_confidence: str
    innovation_summary: InnovationSummary
    influence_summary: InfluenceSummary
    scope_impact_level: ScopeLevel
