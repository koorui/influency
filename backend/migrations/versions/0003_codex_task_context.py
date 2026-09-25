from alembic import op
import sqlalchemy as sa
revision='0003'
down_revision='0002'

def upgrade():
    op.add_column('evaluation_tasks',sa.Column('project_context',sa.String(500),nullable=False,server_default=''))
    op.add_column('evaluation_tasks',sa.Column('confirmed_scope',sa.String(200),nullable=False,server_default=''))

def downgrade():
    op.drop_column('evaluation_tasks','confirmed_scope')
    op.drop_column('evaluation_tasks','project_context')
