from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import LONGTEXT
revision='0004'
down_revision='0003'

def upgrade():
    op.create_table('pipeline_jobs',
        sa.Column('id',sa.String(36),primary_key=True),
        sa.Column('title',sa.String(200),nullable=False),
        sa.Column('project_id',sa.String(100),nullable=False),
        sa.Column('outcome_id',sa.String(160),nullable=False),
        sa.Column('created_by',sa.String(36),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('status',sa.String(30),nullable=False,index=True),
        sa.Column('error',sa.Text().with_variant(LONGTEXT(),'mysql'),nullable=False),
        sa.Column('revision',sa.Integer(),nullable=False),
        sa.Column('created_at',sa.DateTime(),nullable=False),
        sa.Column('started_at',sa.DateTime()),sa.Column('finished_at',sa.DateTime()))

def downgrade():op.drop_table('pipeline_jobs')
