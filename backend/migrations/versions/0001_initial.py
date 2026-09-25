"""Initial schema. Frozen metadata is captured in this migration's SQLAlchemy tables."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import LONGTEXT

revision = '0001'
down_revision = None


def upgrade():
    idcol = lambda: sa.Column('id', sa.String(36), primary_key=True)
    created = lambda: sa.Column('created_at', sa.DateTime(), nullable=False)
    texttype = sa.Text().with_variant(LONGTEXT(), 'mysql')
    op.create_table('users', idcol(), sa.Column('username', sa.String(80), nullable=False, unique=True), sa.Column('password_hash', sa.String(300), nullable=False), sa.Column('role', sa.String(20), nullable=False))
    op.create_table('tickets', idcol(), sa.Column('owner', sa.String(80), nullable=False, index=True), sa.Column('query', sa.String(200), nullable=False), sa.Column('normalized_query', sa.String(200), nullable=False, index=True), sa.Column('active_key', sa.String(64), unique=True), sa.Column('status', sa.String(30), nullable=False), sa.Column('result_id', sa.String(36)), sa.Column('note', texttype, nullable=False), created())
    op.create_table('materials', idcol(), sa.Column('filename', sa.String(255), nullable=False), sa.Column('storage_key', sa.String(80), nullable=False, unique=True), sa.Column('sha256', sa.String(64), nullable=False), sa.Column('size', sa.Integer(), nullable=False), sa.Column('text', texttype, nullable=False), sa.Column('uploaded_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False), created())
    op.create_table('evaluation_tasks', idcol(), sa.Column('title', sa.String(200), nullable=False), sa.Column('keywords', sa.JSON(), nullable=False), sa.Column('material_ids', sa.JSON(), nullable=False), sa.Column('ticket_id', sa.String(36), sa.ForeignKey('tickets.id')), sa.Column('adapter', sa.String(40), nullable=False), sa.Column('skill_version', sa.String(80), nullable=False), sa.Column('model', sa.String(100), nullable=False), sa.Column('status', sa.String(30), nullable=False, index=True), sa.Column('attempts', sa.Integer(), nullable=False), sa.Column('error', texttype, nullable=False), sa.Column('raw_output', texttype, nullable=False), sa.Column('created_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False), created(), sa.Column('started_at', sa.DateTime()), sa.Column('finished_at', sa.DateTime()))
    op.create_table('evaluation_results', idcol(), sa.Column('task_id', sa.String(36), sa.ForeignKey('evaluation_tasks.id'), unique=True), sa.Column('title', sa.String(200), nullable=False, index=True), sa.Column('search_text', texttype, nullable=False), sa.Column('payload', sa.JSON(), nullable=False), sa.Column('status', sa.String(30), nullable=False, index=True), sa.Column('revision', sa.Integer(), nullable=False), sa.Column('reviewed_by', sa.String(36), sa.ForeignKey('users.id')), created(), sa.Column('published_at', sa.DateTime()))
    op.create_table('result_versions', idcol(), sa.Column('result_id', sa.String(36), sa.ForeignKey('evaluation_results.id'), nullable=False), sa.Column('revision', sa.Integer(), nullable=False), sa.Column('payload', sa.JSON(), nullable=False), sa.Column('editor', sa.String(80), nullable=False), created(), sa.UniqueConstraint('result_id', 'revision'))
    op.create_table('audit_logs', idcol(), sa.Column('actor', sa.String(80), nullable=False), sa.Column('action', sa.String(80), nullable=False), sa.Column('target', sa.String(36), nullable=False), created())


def downgrade():
    for table in ['audit_logs', 'result_versions', 'evaluation_results', 'evaluation_tasks', 'materials', 'tickets', 'users']:
        op.drop_table(table)
