"""empty message

Revision ID: 1745ece37148
Revises: 2629566c113c
Create Date: 2019-08-21 11:11:07.034850

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '1745ece37148'
down_revision = '2629566c113c'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('balance_histories',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('date_created', sa.DateTime(), nullable=True),
    sa.Column('date_modified', sa.DateTime(), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('balance', sa.Numeric(precision=14, scale=7), nullable=False),
    sa.Column('shares', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('balance_histories')
    # ### end Alembic commands ###
