from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra='forbid')


class MaterialPurposeInput(StrictModel):
    purpose: Literal['project','reference','instruction']


class Evidence(StrictModel):
    id: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=255)
    source: str = Field(min_length=1, max_length=500)
    excerpt: str = Field(max_length=10000)
    material_id: str | None = None
    locator: str = Field(default='', max_length=200)
    kind: Literal['project', 'external'] = 'project'
    url: str | None = None
    supports: str = ''
    does_not_prove: str = ''
    verification: str = 'project_statement'
    date: str | None = None


class Dimension(StrictModel):
    topic: str = Field(min_length=1, max_length=200)
    claim: str = Field(max_length=10000)
    assessment: str = Field(max_length=10000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=100)
    project_evidence_ids: list[str] = Field(default_factory=list, max_length=100)


class FollowUp(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    detail: str = Field(max_length=10000)
    kind: Literal['material', 'expert', 'improvement','maintenance'] = 'material'
    body: str = ''
    fact_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)


class Upgrade(StrictModel):
    target_level: int = Field(ge=2, le=6)
    level_name: str
    need: str
    proof_materials: list[str]


class Evaluation(StrictModel):
    review_window: str = Field(default='',max_length=2000)
    schema_version: Literal['1.0'] = '1.0'
    title: str = Field(min_length=1, max_length=200)
    keywords: list[str] = Field(min_length=1, max_length=30)
    category: str = Field(default='科研成果', max_length=100)
    summary: str = Field(min_length=1, max_length=10000)
    level: int | None = Field(default=None, ge=1, le=6)
    level_name: str = Field(max_length=100)
    reasons: list[str] = Field(min_length=1, max_length=30)
    dimensions: list[Dimension] = Field(min_length=1, max_length=50)
    evidence: list[Evidence] = Field(default_factory=list, max_length=200)
    follow_ups: list[FollowUp] = Field(default_factory=list, max_length=50)
    is_demo: bool = False
    evaluation_status: Literal['formal','preliminary','insufficient_project_context','needs_scope_confirmation','system_preliminary'] = 'preliminary'
    rubric_id: str = ''
    reason_evidence_refs: list[list[str]] = Field(default_factory=list)
    boundary_gap: str = ''
    upgrades: list[Upgrade] = Field(default_factory=list)
    project_name: str = ''
    candidates: list[str] = Field(default_factory=list)
    fact_ledger: dict | None = None
    attainment_fact_ids: list[str] = Field(default_factory=list)
    boundary_fact_ids: list[str] = Field(default_factory=list)
    dimension_audit: list[dict] = Field(default_factory=list)
    history_context: dict = Field(default_factory=dict)
    rule_version: str | None = None
    evaluation_cutoff: str | None = None
    adjudication_status: Literal['system_preliminary'] = 'system_preliminary'


    @model_validator(mode='after')
    def references_exist(self):
        ids = [x.id for x in self.evidence]
        if len(ids) != len(set(ids)):
            raise ValueError('证据编号不能重复')
        for row in self.dimensions:
            if not set(row.evidence_ids + row.project_evidence_ids).issubset(ids):
                raise ValueError('指标引用了不存在的证据编号')
        if any(not k.strip() or len(k) > 100 for k in self.keywords):
            raise ValueError('关键词不能为空或超过100字')
        if any(not set(refs).issubset(ids) for refs in self.reason_evidence_refs):
            raise ValueError('等级理由引用不存在的证据')
        if self.reason_evidence_refs and len(self.reason_evidence_refs) != len(self.reasons):
            raise ValueError('理由和证据索引必须逐项对应')
        if self.rubric_id and self.level and self.evaluation_status not in ('formal','system_preliminary'):
            raise ValueError('未完成正式评价时不可填写等级')
        if any(e.url and not e.url.startswith(('http://','https://')) for e in self.evidence):
            raise ValueError('证据链接必须是HTTP(S)地址')
        return self


class Credentials(StrictModel):
    username: str = Field(min_length=3, max_length=80, pattern=r'^[a-zA-Z0-9_\-]+$')
    password: str = Field(min_length=6, max_length=128)


class SearchInput(StrictModel):
    query: str = Field(min_length=1, max_length=200)


class FixedSearchInput(StrictModel):
    project_id: UUID
    task_type: Literal['成果影响力评价', '技术先进性核验', '外部应用证据核验']
    detail: str = Field(default='', max_length=300)

    @model_validator(mode='after')
    def valid_detail(self):
        if any(ord(c) < 32 and c not in '\n\r\t' for c in self.detail):
            raise ValueError('补充说明不能包含不可见控制字符')
        self.detail = self.detail.strip()
        return self


class TaskInput(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    keywords: list[str] = Field(min_length=1, max_length=30)
    material_ids: list[str] = Field(min_length=1, max_length=201)
    ticket_id: str | None = None
    adapter: Literal['mock','codex'] | None = None
    project_context: str = Field(default='',max_length=500)
    confirmed_scope: str = Field(default='',max_length=200)


class ResultEdit(StrictModel):
    revision: int
    payload: Evaluation


class RevisionInput(StrictModel):
    revision: int
