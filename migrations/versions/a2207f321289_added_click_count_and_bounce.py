"""Added click count and bounce

Revision ID: a2207f321289
Revises: 763593956aef
Create Date: 2024-12-29 03:49:39.627144

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a2207f321289'
down_revision = '763593956aef'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('email_jobs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('bounce_count', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('click_count', sa.Integer(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('email_jobs', schema=None) as batch_op:
        batch_op.drop_column('click_count')
        batch_op.drop_column('bounce_count')

    # ### end Alembic commands ###
