from alembic import op
import sqlalchemy as sa
revision='0009'
down_revision='0008'

def upgrade():
    op.add_column('materials',sa.Column('purpose',sa.String(24),nullable=False,server_default='project'))

def downgrade():
    op.drop_column('materials','purpose')
