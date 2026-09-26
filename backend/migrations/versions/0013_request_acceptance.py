"""Explicit administrator receipt and applicant report acceptance."""
from alembic import op
import sqlalchemy as sa

revision = '0013'
down_revision = '0012'


def upgrade():
    with op.batch_alter_table('tickets') as batch:
        batch.add_column(sa.Column('received_by', sa.String(36), nullable=True))
        batch.add_column(sa.Column('received_at', sa.DateTime(), nullable=True))
        batch.add_column(sa.Column('accepted_at', sa.DateTime(), nullable=True))
        batch.create_foreign_key('fk_ticket_receiver', 'users', ['received_by'], ['id'])


def downgrade():
    with op.batch_alter_table('tickets') as batch:
        batch.drop_constraint('fk_ticket_receiver', type_='foreignkey')
        for name in ('received_by', 'received_at', 'accepted_at'):
            batch.drop_column(name)
