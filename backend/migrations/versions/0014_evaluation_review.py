"""Add report-version-bound review records; do not reinterpret historical formal."""
from alembic import op
import sqlalchemy as sa

revision='0014'
down_revision='0013'
branch_labels=None
depends_on=None


def upgrade():
    op.create_table('evaluation_review_assignments',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('result_id',sa.String(36),sa.ForeignKey('evaluation_results.id'),nullable=False,index=True),
        sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('assigned_by',sa.String(36),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('active',sa.Integer,nullable=False),sa.Column('created_at',sa.DateTime,nullable=False),
        sa.UniqueConstraint('result_id','user_id'))
    op.create_table('evaluation_review_decisions',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('result_id',sa.String(36),sa.ForeignKey('evaluation_results.id'),nullable=False,index=True),
        sa.Column('result_revision',sa.Integer,nullable=False),
        sa.Column('user_id',sa.String(36),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('fact_id',sa.String(80),nullable=False),sa.Column('verdict',sa.String(30),nullable=False),
        sa.Column('reason',sa.Text,nullable=False),sa.Column('evidence_ids',sa.JSON,nullable=False),
        sa.Column('created_at',sa.DateTime,nullable=False))
    op.create_table('evaluation_followup_tasks',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('result_id',sa.String(36),sa.ForeignKey('evaluation_results.id'),nullable=False,index=True),
        sa.Column('result_revision',sa.Integer,nullable=False),sa.Column('source_key',sa.String(80),nullable=False),
        sa.Column('title',sa.String(200),nullable=False),sa.Column('kind',sa.String(30),nullable=False),
        sa.Column('body',sa.Text,nullable=False),sa.Column('status',sa.String(30),nullable=False),
        sa.Column('revision',sa.Integer,nullable=False),
        sa.Column('owner_id',sa.String(36),sa.ForeignKey('users.id'),nullable=True),
        sa.Column('deadline',sa.String(10),nullable=True),sa.Column('resolution_refs',sa.JSON,nullable=False),
        sa.Column('edited_by',sa.String(36),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('updated_at',sa.DateTime,nullable=False),
        sa.UniqueConstraint('result_id','result_revision','source_key'))


def downgrade():
    raise RuntimeError('保留专家与任务记录；回退程序可忽略新增表，不能删除已提交的复核历史。')
