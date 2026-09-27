"""Use an explicit append order; MySQL timestamps may have second precision."""
from alembic import op
import sqlalchemy as sa

revision='0015'
down_revision='0014'
branch_labels=None
depends_on=None


def upgrade():
    op.add_column('evaluation_review_decisions',sa.Column('sequence',sa.Integer,nullable=False,server_default='0'))
    table=sa.table('evaluation_review_decisions',sa.column('id'),sa.column('result_id'),sa.column('result_revision'),sa.column('created_at'),sa.column('sequence'))
    db=op.get_bind();counts={}
    for row in db.execute(sa.select(table.c.id,table.c.result_id,table.c.result_revision).order_by(table.c.created_at,table.c.id)).all():
        key=(row.result_id,row.result_revision);counts[key]=counts.get(key,0)+1
        db.execute(table.update().where(table.c.id==row.id).values(sequence=counts[key]))
    with op.batch_alter_table('evaluation_review_decisions') as batch:
        batch.create_unique_constraint('uq_review_sequence',['result_id','result_revision','sequence'])


def downgrade():
    raise RuntimeError('保留复核顺序；程序回退不删除已经记录的审阅信息。')
