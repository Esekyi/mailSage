"""Added email campaign for job and tracking

Revision ID: 918c4ba4378c
Revises: 49acea4097e0
Create Date: 2025-01-04 04:50:57.377406

"""
from alembic import op
import sqlalchemy as sa
from app.utils.db import JSONBType


# revision identifiers, used by Alembic.
revision = '918c4ba4378c'
down_revision = '49acea4097e0'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('email_campaigns',
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=True),
    sa.Column('template_id', sa.Integer(), nullable=True),
    sa.Column('smtp_config_id', sa.Integer(), nullable=True),
    sa.Column('schedule_type', sa.String(length=20), nullable=True),
    sa.Column('scheduled_at', sa.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('meta_data', JSONBType(), nullable=True),
    sa.Column('tags', sa.ARRAY(sa.String()), nullable=True),
    sa.Column('tracking_enabled', sa.Boolean(), nullable=True),
    sa.Column('tracking_id', sa.String(length=36), nullable=True),
    sa.Column('total_recipients', sa.Integer(), nullable=True),
    sa.Column('emails_sent', sa.Integer(), nullable=True),
    sa.Column('emails_delivered', sa.Integer(), nullable=True),
    sa.Column('emails_failed', sa.Integer(), nullable=True),
    sa.Column('unique_opens', sa.Integer(), nullable=True),
    sa.Column('unique_clicks', sa.Integer(), nullable=True),
    sa.Column('started_at', sa.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('completed_at', sa.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('created_by', sa.Integer(), nullable=True),
    sa.Column('updated_by', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['smtp_config_id'], ['smtp_configurations.id'], ),
    sa.ForeignKeyConstraint(['template_id'], ['templates.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tracking_id')
    )
    with op.batch_alter_table('email_campaigns', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_email_campaigns_status'), ['status'], unique=False)
        batch_op.create_index(batch_op.f('ix_email_campaigns_user_id'), ['user_id'], unique=False)

    op.create_table('campaign_links',
    sa.Column('campaign_id', sa.Integer(), nullable=False),
    sa.Column('original_url', sa.String(length=2048), nullable=False),
    sa.Column('tracking_id', sa.String(length=36), nullable=True),
    sa.Column('click_count', sa.Integer(), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['campaign_id'], ['email_campaigns.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('tracking_id')
    )
    with op.batch_alter_table('campaign_links', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_campaign_links_campaign_id'), ['campaign_id'], unique=False)

    op.create_table('campaign_events',
    sa.Column('campaign_id', sa.Integer(), nullable=False),
    sa.Column('job_id', sa.Integer(), nullable=False),
    sa.Column('delivery_id', sa.Integer(), nullable=False),
    sa.Column('event_type', sa.String(length=20), nullable=False),
    sa.Column('recipient', sa.String(length=255), nullable=False),
    sa.Column('user_agent', sa.String(length=512), nullable=True),
    sa.Column('ip_address', sa.String(length=45), nullable=True),
    sa.Column('link_id', sa.Integer(), nullable=True),
    sa.Column('event_data', JSONBType(), nullable=True),
    sa.Column('occurred_at', sa.TIMESTAMP(timezone=True), nullable=True),
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['campaign_id'], ['email_campaigns.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['delivery_id'], ['email_deliveries.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['job_id'], ['email_jobs.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['link_id'], ['campaign_links.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('campaign_events', schema=None) as batch_op:
        batch_op.create_index('idx_campaign_event_type', ['campaign_id', 'event_type'], unique=False)
        batch_op.create_index('idx_campaign_recipient', ['campaign_id', 'recipient'], unique=False)
        batch_op.create_index(batch_op.f('ix_campaign_events_campaign_id'), ['campaign_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_campaign_events_delivery_id'), ['delivery_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_campaign_events_event_type'), ['event_type'], unique=False)
        batch_op.create_index(batch_op.f('ix_campaign_events_job_id'), ['job_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_campaign_events_recipient'), ['recipient'], unique=False)

    with op.batch_alter_table('email_deliveries', schema=None) as batch_op:
        batch_op.add_column(sa.Column('variables', JSONBType(), nullable=True))
        batch_op.add_column(sa.Column('unsubscribed_at', sa.TIMESTAMP(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('complained_at', sa.TIMESTAMP(timezone=True), nullable=True))
        batch_op.add_column(sa.Column('meta_data', JSONBType(), nullable=True))
        batch_op.add_column(sa.Column('headers', JSONBType(), nullable=True))
        batch_op.alter_column('tracking_id',
               existing_type=sa.VARCHAR(length=36),
               nullable=True)

    with op.batch_alter_table('email_jobs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('campaign_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('tracking_id', sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column('tracking_enabled', sa.Boolean(), nullable=True))
        batch_op.add_column(sa.Column('open_count', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('last_processed_at', sa.TIMESTAMP(timezone=True), nullable=True))
        batch_op.create_index(batch_op.f('ix_email_jobs_campaign_id'), ['campaign_id'], unique=False)
        batch_op.create_unique_constraint(None, ['tracking_id'])
        batch_op.create_foreign_key(None, 'email_campaigns', ['campaign_id'], ['id'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('email_jobs', schema=None) as batch_op:
        batch_op.drop_constraint(None, type_='foreignkey')
        batch_op.drop_constraint(None, type_='unique')
        batch_op.drop_index(batch_op.f('ix_email_jobs_campaign_id'))
        batch_op.drop_column('last_processed_at')
        batch_op.drop_column('open_count')
        batch_op.drop_column('tracking_enabled')
        batch_op.drop_column('tracking_id')
        batch_op.drop_column('campaign_id')

    with op.batch_alter_table('email_deliveries', schema=None) as batch_op:
        batch_op.alter_column('tracking_id',
               existing_type=sa.VARCHAR(length=36),
               nullable=False)
        batch_op.drop_column('headers')
        batch_op.drop_column('meta_data')
        batch_op.drop_column('complained_at')
        batch_op.drop_column('unsubscribed_at')
        batch_op.drop_column('variables')

    with op.batch_alter_table('campaign_events', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_campaign_events_recipient'))
        batch_op.drop_index(batch_op.f('ix_campaign_events_job_id'))
        batch_op.drop_index(batch_op.f('ix_campaign_events_event_type'))
        batch_op.drop_index(batch_op.f('ix_campaign_events_delivery_id'))
        batch_op.drop_index(batch_op.f('ix_campaign_events_campaign_id'))
        batch_op.drop_index('idx_campaign_recipient')
        batch_op.drop_index('idx_campaign_event_type')

    op.drop_table('campaign_events')
    with op.batch_alter_table('campaign_links', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_campaign_links_campaign_id'))

    op.drop_table('campaign_links')
    with op.batch_alter_table('email_campaigns', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_email_campaigns_user_id'))
        batch_op.drop_index(batch_op.f('ix_email_campaigns_status'))

    op.drop_table('email_campaigns')
    # ### end Alembic commands ###