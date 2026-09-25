import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, JSON, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.dialects.mysql import LONGTEXT
from .db import Base

Text = Text().with_variant(LONGTEXT(), 'mysql')


def uid():
    return str(uuid.uuid4())


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = 'users'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    username: Mapped[str] = mapped_column(String(80), unique=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    role: Mapped[str] = mapped_column(String(20), default='user')


class Ticket(Base):
    __tablename__ = 'tickets'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner: Mapped[str] = mapped_column(String(80), index=True)
    query: Mapped[str] = mapped_column(String(200))
    normalized_query: Mapped[str] = mapped_column(String(200), index=True)
    active_key: Mapped[str | None] = mapped_column(String(64), unique=True)
    status: Mapped[str] = mapped_column(String(30), default='pending')
    result_id: Mapped[str | None] = mapped_column(String(36))
    note: Mapped[str] = mapped_column(Text, default='')
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Material(Base):
    __tablename__ = 'materials'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    filename: Mapped[str] = mapped_column(String(255))
    purpose: Mapped[str] = mapped_column(String(24),default='project')
    storage_key: Mapped[str] = mapped_column(String(80), unique=True)
    sha256: Mapped[str] = mapped_column(String(64))
    size: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    uploaded_by: Mapped[str] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class OutcomeSubmission(Base):
    __tablename__ = 'outcome_submissions'
    __table_args__ = (UniqueConstraint('created_by', 'request_key', name='uq_submission_request'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    ticket_id: Mapped[str] = mapped_column(ForeignKey('tickets.id'), unique=True)
    created_by: Mapped[str] = mapped_column(ForeignKey('users.id'))
    request_key: Mapped[str] = mapped_column(String(36))
    payload: Mapped[dict] = mapped_column(JSON)
    material_ids: Mapped[list] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Task(Base):
    __tablename__ = 'evaluation_tasks'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    title: Mapped[str] = mapped_column(String(200))
    keywords: Mapped[list] = mapped_column(JSON)
    material_ids: Mapped[list] = mapped_column(JSON)
    ticket_id: Mapped[str | None] = mapped_column(ForeignKey('tickets.id'))
    adapter: Mapped[str] = mapped_column(String(40))
    skill_version: Mapped[str] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(100), default='mock-deterministic')
    project_context: Mapped[str] = mapped_column(String(500),default='')
    confirmed_scope: Mapped[str] = mapped_column(String(200),default='')
    status: Mapped[str] = mapped_column(String(30), default='queued', index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str] = mapped_column(Text, default='')
    raw_output: Mapped[str] = mapped_column(Text, default='')
    created_by: Mapped[str] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)


class Result(Base):
    __tablename__ = 'evaluation_results'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    task_id: Mapped[str | None] = mapped_column(ForeignKey('evaluation_tasks.id'), unique=True)
    pipeline_id: Mapped[str | None] = mapped_column(ForeignKey('pipeline_jobs.id'), unique=True)
    source_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    search_text: Mapped[str] = mapped_column(Text)
    payload: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default='draft', index=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    reviewed_by: Mapped[str | None] = mapped_column(ForeignKey('users.id'))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)
    published_at: Mapped[datetime | None] = mapped_column(DateTime)


class ResultVersion(Base):
    __tablename__ = 'result_versions'
    __table_args__ = (UniqueConstraint('result_id', 'revision'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    result_id: Mapped[str] = mapped_column(ForeignKey('evaluation_results.id'))
    revision: Mapped[int] = mapped_column(Integer)
    payload: Mapped[dict] = mapped_column(JSON)
    editor: Mapped[str] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class Audit(Base):
    __tablename__ = 'audit_logs'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    actor: Mapped[str] = mapped_column(String(80))
    action: Mapped[str] = mapped_column(String(80))
    target: Mapped[str] = mapped_column(String(36))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class QueryRecord(Base):
    __tablename__ = 'query_records'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner: Mapped[str] = mapped_column(String(80), index=True)
    result_id: Mapped[str] = mapped_column(ForeignKey('evaluation_results.id'))
    result_revision: Mapped[int] = mapped_column(Integer)
    project_title: Mapped[str] = mapped_column(String(200))
    task_type: Mapped[str] = mapped_column(String(40))
    detail: Mapped[str] = mapped_column(Text)
    prompt_version: Mapped[str] = mapped_column(String(40))
    prompt: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=now)


class PipelineJob(Base):
    __tablename__='pipeline_jobs'
    id: Mapped[str] = mapped_column(String(36),primary_key=True,default=uid)
    title: Mapped[str] = mapped_column(String(200))
    project_id: Mapped[str] = mapped_column(String(100))
    outcome_id: Mapped[str] = mapped_column(String(160))
    ticket_id: Mapped[str | None] = mapped_column(ForeignKey('tickets.id'), nullable=True)
    created_by: Mapped[str] = mapped_column(ForeignKey('users.id'))
    status: Mapped[str] = mapped_column(String(30),default='queued',index=True)
    error: Mapped[str] = mapped_column(Text,default='')
    revision: Mapped[int] = mapped_column(Integer,default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime,default=now)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)
