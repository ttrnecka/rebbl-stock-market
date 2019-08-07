"""empty message

Revision ID: 505fec4376b0
Revises: a8af6725183d
Create Date: 2019-08-07 17:20:33.713597

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '505fec4376b0'
down_revision = 'a8af6725183d'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('orders', sa.Column('result', sa.String(length=255), nullable=True))
    op.add_column('orders', sa.Column('success', sa.Boolean(), nullable=False, server_default=sa.text("'0'")))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('orders', 'success')
    op.drop_column('orders', 'result')
    # ### end Alembic commands ###
