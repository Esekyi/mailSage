"""Add JSON types fro sqlite and postgres

Revision ID: 7928c5e70b79
Revises: d0c1794da997
Create Date: 2024-12-17 16:29:26.139626

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision = '7928c5e70b79'
down_revision = 'd0c1794da997'
branch_labels = None
depends_on = None


# Custom JSON type for the migration
class JSONBType(sa.types.TypeDecorator):
    impl = sa.JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            return dialect.type_descriptor(JSONB())
        else:
            return dialect.type_descriptor(sa.JSON())


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('api_keys', schema=None) as batch_op:
        batch_op.alter_column('permissions',
               existing_type=postgresql.JSON(astext_type=sa.Text()),
               type_=JSONBType,
               existing_nullable=True)

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('smtp_config',
               existing_type=postgresql.JSON(astext_type=sa.Text()),
               type_=JSONBType,
               existing_nullable=True)

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.alter_column('smtp_config',
               existing_type=JSONBType,
               type_=postgresql.JSON(astext_type=sa.Text()),
               existing_nullable=True)

    with op.batch_alter_table('api_keys', schema=None) as batch_op:
        batch_op.alter_column('permissions',
               existing_type=JSONBType,
               type_=postgresql.JSON(astext_type=sa.Text()),
               existing_nullable=True)

    # ### end Alembic commands ###
