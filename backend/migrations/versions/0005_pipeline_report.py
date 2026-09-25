from alembic import op
import sqlalchemy as sa
revision='0005'
down_revision='0004'

def upgrade():
    op.add_column('evaluation_results',sa.Column('pipeline_id',sa.String(36),nullable=True))
    op.create_foreign_key('fk_result_pipeline','evaluation_results','pipeline_jobs',['pipeline_id'],['id'])
    op.create_unique_constraint('uq_result_pipeline','evaluation_results',['pipeline_id'])

def downgrade():
    op.drop_constraint('uq_result_pipeline','evaluation_results',type_='unique')
    op.drop_constraint('fk_result_pipeline','evaluation_results',type_='foreignkey')
    op.drop_column('evaluation_results','pipeline_id')
