from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import LONGTEXT

revision = '0002'
down_revision = '0001'


def upgrade():
    texttype = sa.Text().with_variant(LONGTEXT(), 'mysql')
    op.create_table('query_records',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('owner', sa.String(80), nullable=False, index=True),
        sa.Column('result_id', sa.String(36), sa.ForeignKey('evaluation_results.id'), nullable=False),
        sa.Column('result_revision', sa.Integer(), nullable=False),
        sa.Column('project_title', sa.String(200), nullable=False),
        sa.Column('task_type', sa.String(40), nullable=False),
        sa.Column('detail', texttype, nullable=False),
        sa.Column('prompt_version', sa.String(40), nullable=False),
        sa.Column('prompt', texttype, nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False))


def downgrade():
    op.drop_table('query_records')
