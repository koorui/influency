from alembic import op
import sqlalchemy as sa

revision = '0006'
down_revision = '0005'


def upgrade():
    op.create_table('outcome_submissions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('ticket_id', sa.String(36), sa.ForeignKey('tickets.id'), nullable=False, unique=True),
        sa.Column('created_by', sa.String(36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('request_key', sa.String(36), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('material_ids', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('created_by', 'request_key', name='uq_submission_request'))


def downgrade():
    op.drop_table('outcome_submissions')
