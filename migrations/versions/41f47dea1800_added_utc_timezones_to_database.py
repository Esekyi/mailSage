"""Added UTC timezones to database.

Revision ID: 41f47dea1800
Revises: 344c8add8f16
Create Date: 2024-12-31 08:38:24.562067

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '41f47dea1800'
down_revision = '344c8add8f16'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('api_keys', schema=None) as batch_op:
        batch_op.alter_column('created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False)
        batch_op.alter_column('updated_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False)

    with op.batch_alter_table('email_deliveries', schema=None) as batch_op:
        batch_op.alter_column('created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False)
        batch_op.alter_column('updated_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False)

    with op.batch_alter_table('email_jobs', schema=None) as batch_op:
        batch_op.alter_column('created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False)
        batch_op.alter_column('updated_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False)

    with op.batch_alter_table('smtp_configurations', schema=None) as batch_op:
        batch_op.alter_column('created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False)
        batch_op.alter_column('updated_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False)

    with op.batch_alter_table('template_stats', schema=None) as batch_op:
        batch_op.alter_column('created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False)
        batch_op.alter_column('updated_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False)

    with op.batch_alter_table('templates', schema=None) as batch_op:
        batch_op.alter_column('created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False)
        batch_op.alter_column('updated_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False)

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False)
        batch_op.alter_column('updated_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False)

    with op.batch_alter_table('webhooks', schema=None) as batch_op:
        batch_op.alter_column('created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False)
        batch_op.alter_column('updated_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=False)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('webhooks', schema=None) as batch_op:
        batch_op.alter_column('updated_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=True)
        batch_op.alter_column('created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=True)

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('updated_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=True)
        batch_op.alter_column('created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=True)

    with op.batch_alter_table('templates', schema=None) as batch_op:
        batch_op.alter_column('updated_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=True)
        batch_op.alter_column('created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=True)

    with op.batch_alter_table('template_stats', schema=None) as batch_op:
        batch_op.alter_column('updated_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=True)
        batch_op.alter_column('created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=True)

    with op.batch_alter_table('smtp_configurations', schema=None) as batch_op:
        batch_op.alter_column('updated_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=True)
        batch_op.alter_column('created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=True)

    with op.batch_alter_table('email_jobs', schema=None) as batch_op:
        batch_op.alter_column('updated_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=True)
        batch_op.alter_column('created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=True)

    with op.batch_alter_table('email_deliveries', schema=None) as batch_op:
        batch_op.alter_column('updated_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=True)
        batch_op.alter_column('created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=True)

    with op.batch_alter_table('api_keys', schema=None) as batch_op:
        batch_op.alter_column('updated_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=True)
        batch_op.alter_column('created_at',
               existing_type=postgresql.TIMESTAMP(timezone=True),
               nullable=True)

    # ### end Alembic commands ###
