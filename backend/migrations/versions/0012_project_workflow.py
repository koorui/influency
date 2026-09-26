"""Project boundaries, code-based membership and workflow material selection."""
from alembic import op
import sqlalchemy as sa
revision = '0012'
down_revision = '0011'


def upgrade():
    op.create_table('projects', sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False, unique=True),
        sa.Column('code', sa.String(100), nullable=False, unique=True),
        sa.Column('access_prefix', sa.String(12), nullable=False, unique=True),
        sa.Column('access_secret', sa.String(300), nullable=False),
        sa.Column('access_version', sa.Integer(), nullable=False),
        sa.Column('evaluation_config', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False))
    op.create_table('project_members', sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('project_id', sa.String(36), sa.ForeignKey('projects.id'), nullable=False, index=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('access_version', sa.Integer(), nullable=False), sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('project_id', 'user_id', name='uq_project_member'))
    op.create_table('project_access_attempts',
        sa.Column('id', sa.String(36), sa.ForeignKey('users.id'), primary_key=True),
        sa.Column('failures', sa.Integer(), nullable=False), sa.Column('locked_until', sa.DateTime()))
    for table, field in [('materials','project_id'), ('tickets','project_id'), ('evaluation_results','project_id'), ('pipeline_jobs','project_ref')]:
        with op.batch_alter_table(table) as batch:
            batch.add_column(sa.Column(field, sa.String(36), nullable=True))
            batch.create_foreign_key('fk_'+table+'_project', 'projects', [field], ['id'])
            batch.create_index('ix_'+table+'_'+field, [field])
    op.add_column('materials', sa.Column('use_in_workflow', sa.Integer(), nullable=False, server_default='0'))


def downgrade():
    raise RuntimeError('Restore the project-system backup to roll back.')
