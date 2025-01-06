from datetime import datetime, timezone
from app.extensions import db
from app.models.base import BaseModel, AuditMixin
from app.utils.db import JSONBType
from sqlalchemy.sql.sqltypes import TIMESTAMP
import uuid
from app.models import EmailJob


class EmailCampaign(BaseModel, AuditMixin):
    """Model for organizing email campaigns."""
    __tablename__ = 'email_campaigns'

    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'),
                        nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    # draft, active, paused, completed
    status = db.Column(db.String(20), default='draft', index=True)

    # Campaign settings
    template_id = db.Column(db.Integer, db.ForeignKey(
        'templates.id'), nullable=True)
    smtp_config_id = db.Column(db.Integer, db.ForeignKey(
        'smtp_configurations.id'), nullable=True)
    # immediate, scheduled, recurring
    schedule_type = db.Column(db.String(20), default='immediate')
    scheduled_at = db.Column(TIMESTAMP(timezone=True), nullable=True)

    # Campaign metadata
    meta_data = db.Column(JSONBType, default=dict)
    tags = db.Column(db.ARRAY(db.String), nullable=True)

    # Tracking
    tracking_enabled = db.Column(db.Boolean, default=True)
    tracking_id = db.Column(
        db.String(36), default=lambda: str(uuid.uuid4()), unique=True)

    # Statistics
    total_recipients = db.Column(db.Integer, default=0)
    emails_sent = db.Column(db.Integer, default=0)
    emails_delivered = db.Column(db.Integer, default=0)
    emails_failed = db.Column(db.Integer, default=0)
    unique_opens = db.Column(db.Integer, default=0)
    unique_clicks = db.Column(db.Integer, default=0)

    # Campaign timeframe
    started_at = db.Column(TIMESTAMP(timezone=True), nullable=True)
    completed_at = db.Column(TIMESTAMP(timezone=True), nullable=True)

    # Relationships
    jobs = db.relationship(
        'EmailJob', back_populates='campaign', lazy='dynamic')
    links = db.relationship('CampaignLink', backref='campaign', lazy='dynamic')
    events = db.relationship(
        'CampaignEvent', backref='campaign', lazy='dynamic')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.tracking_id:
            self.tracking_id = str(uuid.uuid4())

    def update_stats(self):
        """Update campaign statistics from associated jobs and events."""
        stats = db.session.query(
            db.func.sum(EmailJob.recipient_count),
            db.func.sum(EmailJob.success_count),
            db.func.sum(EmailJob.failure_count)
        ).filter(
            EmailJob.campaign_id == self.id
        ).first()

        self.total_recipients = stats[0] or 0
        self.emails_sent = stats[1] or 0
        self.emails_failed = stats[2] or 0

        # Update opens and clicks
        self.unique_opens = self.events.filter_by(event_type='open').distinct(
            CampaignEvent.recipient).count()
        self.unique_clicks = self.events.filter_by(event_type='click').distinct(
            CampaignEvent.recipient).count()

        db.session.commit()


class CampaignLink(BaseModel):
    """Model for tracking links in campaign emails."""
    __tablename__ = 'campaign_links'

    campaign_id = db.Column(db.Integer, db.ForeignKey('email_campaigns.id', ondelete='CASCADE'),
                            nullable=False, index=True)
    original_url = db.Column(db.String(2048), nullable=False)
    tracking_id = db.Column(
        db.String(36), default=lambda: str(uuid.uuid4()), unique=True)
    click_count = db.Column(db.Integer, default=0)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.tracking_id:
            self.tracking_id = str(uuid.uuid4())

    def increment_clicks(self):
        """Increment click count for this link."""
        self.click_count += 1
        db.session.commit()


class CampaignEvent(BaseModel):
    """Model for tracking campaign-related events."""
    __tablename__ = 'campaign_events'

    campaign_id = db.Column(db.Integer, db.ForeignKey('email_campaigns.id', ondelete='CASCADE'),
                            nullable=False, index=True)
    job_id = db.Column(db.Integer, db.ForeignKey('email_jobs.id', ondelete='CASCADE'),
                       nullable=False, index=True)
    delivery_id = db.Column(db.Integer, db.ForeignKey('email_deliveries.id', ondelete='CASCADE'),
                            nullable=False, index=True)

    # sent, delivered, opened, clicked
    event_type = db.Column(db.String(20), nullable=False, index=True)
    recipient = db.Column(db.String(255), nullable=False, index=True)
    user_agent = db.Column(db.String(512), nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    link_id = db.Column(db.Integer, db.ForeignKey(
        'campaign_links.id'), nullable=True)

    event_data = db.Column(JSONBType, default=dict)
    occurred_at = db.Column(TIMESTAMP(timezone=True),
                            default=datetime.now(timezone.utc))

    __table_args__ = (
        db.Index('idx_campaign_event_type', 'campaign_id', 'event_type'),
        db.Index('idx_campaign_recipient', 'campaign_id', 'recipient'),
    )


# Update EmailJob model to include campaign relationship
def update_email_job_model():
    """Add campaign-related fields to EmailJob model."""
    from app.models import EmailJob

    EmailJob.campaign_id = db.Column(db.Integer,
                                     db.ForeignKey('email_campaigns.id'),
                                     nullable=True,
                                     index=True)
