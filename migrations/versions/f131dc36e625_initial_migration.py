"""Initial migration

Revision ID: f131dc36e625
Revises:
Create Date: 2024-12-15 02:55:06.824138

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'f131dc36e625'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    # Add PostgreSQL extensions first
    op.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm')
    op.execute('CREATE EXTENSION IF NOT EXISTS btree_gin')
    op.execute('CREATE EXTENSION IF NOT EXISTS unaccent')

    op.create_table('audit_logs',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('model_name', sa.String(length=50), nullable=False),
    sa.Column('record_id', sa.Integer(), nullable=False),
    sa.Column('operation', sa.String(length=10), nullable=False),
    sa.Column('changes', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('audit_logs', schema=None) as batch_op:
        batch_op.create_index('idx_audit_model_record', ['model_name', 'record_id'], unique=False)

    op.create_table('api_keys',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('key_hash', sa.String(length=128), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=True),
    sa.Column('permissions', sa.JSON(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('last_used_at', sa.DateTime(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('key_hash')
    )
    with op.batch_alter_table('api_keys', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_api_keys_is_active'), ['is_active'], unique=False)
        batch_op.create_index(batch_op.f('ix_api_keys_user_id'), ['user_id'], unique=False)

    op.create_table('templates',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('html_content', sa.Text(), nullable=False),
    sa.Column('variables', sa.JSON(), nullable=True),
    sa.Column('version', sa.Integer(), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=True),
    sa.Column('search_vector', postgresql.TSVECTOR(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('deleted_at', sa.DateTime(), nullable=True),
    sa.Column('deleted_by', sa.Integer(), nullable=True),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('templates', schema=None) as batch_op:
        batch_op.create_index('idx_template_search', ['search_vector'], unique=False, postgresql_using='gin')
        batch_op.create_index(batch_op.f('ix_templates_is_active'), ['is_active'], unique=False)
        batch_op.create_index(batch_op.f('ix_templates_user_id'), ['user_id'], unique=False)

    op.create_table('email_jobs',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('template_id', sa.Integer(), nullable=True),
    sa.Column('subject', sa.String(length=255), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=True),
    sa.Column('recipient_count', sa.Integer(), nullable=True),
    sa.Column('success_count', sa.Integer(), nullable=True),
    sa.Column('failure_count', sa.Integer(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['template_id'], ['templates.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('email_jobs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_email_jobs_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_email_jobs_user_id'), ['user_id'], unique=False)

    op.create_table('email_deliveries',
    sa.Column('job_id', sa.Integer(), nullable=False),
    sa.Column('recipient', sa.String(length=255), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=True),
    sa.Column('tracking_id', sa.String(length=36), nullable=False),
    sa.Column('opened_at', sa.DateTime(), nullable=True),
    sa.Column('clicked_at', sa.DateTime(), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['job_id'], ['email_jobs.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tracking_id')
    )
    with op.batch_alter_table('email_deliveries', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_email_deliveries_job_id'), ['job_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_email_deliveries_status'), ['status'], unique=False)

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('smtp_config', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('deleted_by', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('created_by', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('updated_by', sa.Integer(), nullable=True))
        batch_op.create_index(batch_op.f('ix_users_is_active'), ['is_active'], unique=False)
        batch_op.create_index(batch_op.f('ix_users_role'), ['role'], unique=False)
        batch_op.drop_column('_smtp_config')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('_smtp_config', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=True))
        batch_op.drop_index(batch_op.f('ix_users_role'))
        batch_op.drop_index(batch_op.f('ix_users_is_active'))
        batch_op.drop_column('updated_by')
        batch_op.drop_column('created_by')
        batch_op.drop_column('deleted_by')
        batch_op.drop_column('smtp_config')

    with op.batch_alter_table('email_deliveries', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_email_deliveries_status'))
        batch_op.drop_index(batch_op.f('ix_email_deliveries_job_id'))

    op.drop_table('email_deliveries')
    with op.batch_alter_table('email_jobs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_email_jobs_user_id'))
        batch_op.drop_index(batch_op.f('ix_email_jobs_status'))

    op.drop_table('email_jobs')
    with op.batch_alter_table('templates', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_templates_user_id'))
        batch_op.drop_index(batch_op.f('ix_templates_is_active'))
        batch_op.drop_index('idx_template_search', postgresql_using='gin')

    op.drop_table('templates')
    with op.batch_alter_table('api_keys', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_api_keys_user_id'))
        batch_op.drop_index(batch_op.f('ix_api_keys_is_active'))

    op.drop_table('api_keys')
    with op.batch_alter_table('audit_logs', schema=None) as batch_op:
        batch_op.drop_index('idx_audit_model_record')

    op.drop_table('audit_logs')
    # ### end Alembic commands ###
