"""Remove the material checksum; authentication is unchanged."""
from alembic import op
import sqlalchemy as sa

revision = '0010'
down_revision = '0009'


def upgrade():
    columns = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('materials')}
    if 'sha256' in columns:
        op.drop_column('materials', 'sha256')


def downgrade():
    raise RuntimeError('Material checksums were retired; restore a database backup to roll back.')
