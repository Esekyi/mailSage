from .base import BaseModel, AuditMixin
from app.extensions import db
from sqlalchemy.sql.sqltypes import TIMESTAMP
from app.utils.db import JSONBType
from datetime import datetime, timezone


class EmailJob(BaseModel, AuditMixin):
    """Model for tracking email sending jobs."""
    __tablename__ = 'email_jobs'

    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'

    user_id = db.Column(db.Integer, db.ForeignKey(
        'users.id', ondelete='CASCADE'),
        nullable=False, index=True)
    template_id = db.Column(db.Integer, db.ForeignKey(
        'templates.id'), nullable=True)
    smtp_config_id = db.Column(db.Integer, db.ForeignKey(
        'smtp_configurations.id', ondelete='SET NULL'), nullable=True)

    subject = db.Column(db.String(255), nullable=False, default='No Subject')
    body = db.Column(db.Text, nullable=False)  # Can be HTML
    # pending, processing, completed, failed
    status = db.Column(db.String(20), default=STATUS_PENDING, index=True)
    # For priority queueing
    priority = db.Column(db.Integer, default=0, index=True)

    # Metrics
    recipient_count = db.Column(db.Integer, default=0)
    success_count = db.Column(db.Integer, default=0)
    failure_count = db.Column(db.Integer, default=0)

    # Store additional job metadata
    meta_data = db.Column(JSONBType, default=dict)
    # For storing error information
    error_details = db.Column(JSONBType, nullable=True)

    # Timestamps
    started_at = db.Column(TIMESTAMP(timezone=True), nullable=True)
    completed_at = db.Column(TIMESTAMP(timezone=True), nullable=True)

    # Relationships
    deliveries = db.relationship(
        'EmailDelivery',
        backref='job',
        lazy='dynamic',
        cascade='all, delete-orphan'
    )
    smtp_config = db.relationship(
        'SMTPConfiguration',
        backref=db.backref('email_jobs', lazy='dynamic')
    )

    __table_args__ = (
        db.Index('idx_job_status_priority', status,
                 priority),  # For efficient job queuing
    )

    def update_counts(self):
        """Update success and failure counts based on deliveries."""
        success = self.deliveries.filter_by(status='sent').count()
        failure = self.deliveries.filter_by(status='failed').count()
        self.success_count = success
        self.failure_count = failure

        # Update status if all deliveries are processed
        if success + failure == self.recipient_count:
            self.status = 'completed'
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

    job_id = db.Column(db.Integer, db.ForeignKey(
        'email_jobs.id', ondelete='CASCADE'),
        nullable=False, index=True)
    recipient = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default='pending',
                       index=True)  # pending, sent, failed

    attempts = db.Column(db.Integer, default=0)
    last_attempt = db.Column(TIMESTAMP(timezone=True), nullable=True)
    error_message = db.Column(db.Text, nullable=True)

    # Tracking
    tracking_id = db.Column(db.String(36), unique=True, nullable=False)
    opened_at = db.Column(TIMESTAMP(timezone=True), nullable=True)
    clicked_at = db.Column(TIMESTAMP(timezone=True), nullable=True)

    __table_args__ = (
        db.Index('idx_delivery_tracking', tracking_id),  # For tracking lookups
        db.Index('idx_delivery_status', job_id, status),  # For status queries
    )

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
