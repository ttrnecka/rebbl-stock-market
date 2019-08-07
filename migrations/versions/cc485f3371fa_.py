"""empty message

Revision ID: cc485f3371fa
Revises: 7849e34112a0
Create Date: 2019-08-07 09:52:58.668050

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cc485f3371fa'
down_revision = '7849e34112a0'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('stocks', sa.Column('code', sa.String(length=30), nullable=False))
    op.create_index(op.f('ix_stocks_code'), 'stocks', ['code'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_stocks_code'), table_name='stocks')
    op.drop_column('stocks', 'code')
    # ### end Alembic commands ###
