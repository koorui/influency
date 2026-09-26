"""Retire report fingerprints; keep report content and ordinary revisions."""
from alembic import op
import sqlalchemy as sa

revision = '0011'
down_revision = '0010'


def upgrade():
    columns = {c['name'] for c in sa.inspect(op.get_bind()).get_columns('evaluation_results')}
    if 'source_fingerprint' in columns:
        op.drop_column('evaluation_results', 'source_fingerprint')


def downgrade():
    raise RuntimeError('Report fingerprints were retired; restore a backup to roll back.')
