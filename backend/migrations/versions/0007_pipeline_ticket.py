from alembic import op
import sqlalchemy as sa
revision='0007'
down_revision='0006'

def upgrade():
    op.add_column('pipeline_jobs',sa.Column('ticket_id',sa.String(36),nullable=True))
    op.create_foreign_key('fk_pipeline_ticket','pipeline_jobs','tickets',['ticket_id'],['id'])

def downgrade():
    op.drop_constraint('fk_pipeline_ticket','pipeline_jobs',type_='foreignkey')
    op.drop_column('pipeline_jobs','ticket_id')
