from .base import BaseModel, AuditMixin
from app.extensions import db
from sqlalchemy.sql.sqltypes import TIMESTAMP
from app.utils.db import JSONBType
from datetime import datetime, timezone, timedelta
from sqlalchemy import func
import uuid

class EmailJob(BaseModel, AuditMixin):
    """Model for tracking email sending jobs."""
    __tablename__ = 'email_jobs'

    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'
    STATUS_PAUSED = 'paused'

    user_id = db.Column(db.Integer, db.ForeignKey(
        'users.id', ondelete='CASCADE'),
        nullable=False, index=True)
    template_id = db.Column(db.Integer, db.ForeignKey(
        'templates.id'), nullable=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('email_campaigns.id'),
                            nullable=True, index=True)
    smtp_config_id = db.Column(db.Integer, db.ForeignKey(
        'smtp_configurations.id', ondelete='SET NULL'), nullable=True)

    # Job details
    subject = db.Column(db.String(255), nullable=False, default='No Subject')
    body = db.Column(db.Text, nullable=False)  # Only for non-templated emails
    status = db.Column(db.String(20), default=STATUS_PENDING, index=True)
    # For priority queueing
    priority = db.Column(db.Integer, default=0, index=True)

    # Tracking
    tracking_id = db.Column(
        db.String(36), default=lambda: str(uuid.uuid4()), unique=True)
    tracking_enabled = db.Column(db.Boolean, default=True)

    # Statistics
    recipient_count = db.Column(db.Integer, default=0)
    success_count = db.Column(db.Integer, default=0)
    failure_count = db.Column(db.Integer, default=0)
    bounce_count = db.Column(db.Integer, default=0)
    open_count = db.Column(db.Integer, default=0)
    click_count = db.Column(db.Integer, default=0)

    # Store additional job metadata
    meta_data = db.Column(JSONBType, default=dict)
    error_details = db.Column(JSONBType, nullable=True)

    # Timestamps
    started_at = db.Column(TIMESTAMP(timezone=True), nullable=True)
    completed_at = db.Column(TIMESTAMP(timezone=True), nullable=True)
    last_processed_at = db.Column(TIMESTAMP(timezone=True), nullable=True)

    # Relationships
    deliveries = db.relationship(
        'EmailDelivery',
        backref='job',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    campaign = db.relationship('EmailCampaign', back_populates='jobs')
    smtp_config = db.relationship(
        'SMTPConfiguration',
        backref=db.backref('email_jobs', lazy='dynamic')
    )

    __table_args__ = (
        db.Index('idx_job_status_priority', status,
                 priority),  # For efficient job queuing
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.tracking_id:
            self.tracking_id = str(uuid.uuid4())

    def update_counts(self):
        """Update success and failure counts based on deliveries."""
        success = self.deliveries.filter_by(status='sent').count()
        failure = self.deliveries.filter_by(status='failed').count()
        self.success_count = success
        self.failure_count = failure

        # Update status if all deliveries are processed
        if success + failure == self.recipient_count:
            self.status = self.STATUS_COMPLETED
            self.completed_at = datetime.now(timezone.utc)

    def to_dict(self):
        """Convert job to dictionary."""
        return {
            'id': self.id,
            'status': self.status,
            'subject': self.subject,
            'recipient_count': self.recipient_count,
            'success_count': self.success_count,
            'failure_count': self.failure_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'smtp_config_id': self.smtp_config_id
        }


class EmailDelivery(BaseModel):
    """Model for tracking individual email deliveries within a job."""
    __tablename__ = 'email_deliveries'

    STATUS_PENDING = 'pending'
    STATUS_SENT = 'sent'
    STATUS_DELIVERED = 'delivered'
    STATUS_FAILED = 'failed'
    STATUS_BOUNCED = 'bounced'
    STATUS_COMPLAINED = 'complained'

    job_id = db.Column(db.Integer, db.ForeignKey(
        'email_jobs.id', ondelete='CASCADE'),
        nullable=False, index=True)
    recipient = db.Column(db.String(255), nullable=False)
    variables = db.Column(JSONBType, nullable=True)
    status = db.Column(db.String(20), default=STATUS_PENDING,
                       index=True)  # pending, sent, failed

    attempts = db.Column(db.Integer, default=0)
    last_attempt = db.Column(TIMESTAMP(timezone=True), nullable=True)
    error_message = db.Column(db.Text, nullable=True)

    # Tracking
    tracking_id = db.Column(
        db.String(36), default=lambda: str(uuid.uuid4()), unique=True)
    opened_at = db.Column(TIMESTAMP(timezone=True), nullable=True)
    clicked_at = db.Column(TIMESTAMP(timezone=True), nullable=True)
    unsubscribed_at = db.Column(TIMESTAMP(timezone=True), nullable=True)
    complained_at = db.Column(TIMESTAMP(timezone=True), nullable=True)

    # Additional metadata
    meta_data = db.Column(JSONBType, default=dict)
    headers = db.Column(JSONBType, nullable=True)  # Store email headers

    # Events relationship
    events = db.relationship(
        'CampaignEvent', backref='delivery', lazy='dynamic')

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.tracking_id:
            self.tracking_id = str(uuid.uuid4())

    __table_args__ = (
        db.Index('idx_delivery_tracking', tracking_id),  # For tracking lookups
        db.Index('idx_delivery_status', job_id, status),  # For status queries
    )

    def record_open(self, user_agent: str = None, ip_address: str = None):
        """Record an email open event."""
        from app.models.campaign import CampaignEvent
        if not self.opened_at:  # Only record first open
            self.opened_at = datetime.now(timezone.utc)

            # Create event if part of a campaign
            if self.job.campaign_id:
                event = CampaignEvent(
                    campaign_id=self.job.campaign_id,
                    job_id=self.job_id,
                    delivery_id=self.id,
                    event_type='open',
                    recipient=self.recipient,
                    user_agent=user_agent,
                    ip_address=ip_address
                )
                db.session.add(event)

            # Update counters
            self.job.open_count += 1
            db.session.commit()

    def record_click(self, link_id: int, user_agent: str = None, ip_address: str = None):
        """Record a link click event."""
        from app.models.campaign import CampaignEvent
        self.clicked_at = datetime.now(timezone.utc)

        # Create event if part of a campaign
        if self.job.campaign_id:
            event = CampaignEvent(
                campaign_id=self.job.campaign_id,
                job_id=self.job_id,
                delivery_id=self.id,
                event_type='click',
                recipient=self.recipient,
                user_agent=user_agent,
                ip_address=ip_address,
                link_id=link_id
            )
            db.session.add(event)

        # Update counters
        self.job.click_count += 1
        db.session.commit()

    def to_dict(self):
        """Convert delivery to dictionary."""
        return {
            'id': self.id,
            'recipient': self.recipient,
            'status': self.status,
            'attempts': self.attempts,
            'last_attempt': self.last_attempt.isoformat() if self.last_attempt else None,
            'error_message': self.error_message,
            'tracking_id': self.tracking_id,
            'opened_at': self.opened_at.isoformat() if self.opened_at else None,
            'clicked_at': self.clicked_at.isoformat() if self.clicked_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
