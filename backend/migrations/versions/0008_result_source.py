from alembic import op
import sqlalchemy as sa
revision='0008'
down_revision='0007'

def upgrade():
    op.add_column('evaluation_results',sa.Column('source_fingerprint',sa.String(64),nullable=True))

def downgrade():
    op.drop_column('evaluation_results','source_fingerprint')
