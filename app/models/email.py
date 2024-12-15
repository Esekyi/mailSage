from .base import BaseModel, AuditMixin
from app.extensions import db


class EmailJob(BaseModel, AuditMixin):
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
    subject = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default=STATUS_PENDING, index=True)

    # Metrics
    recipient_count = db.Column(db.Integer, default=0)
    success_count = db.Column(db.Integer, default=0)
    failure_count = db.Column(db.Integer, default=0)

    # Relationships
    deliveries = db.relationship(
        'EmailDelivery', backref='job', lazy='dynamic')


class EmailDelivery(BaseModel):
    __tablename__ = 'email_deliveries'

    job_id = db.Column(db.Integer, db.ForeignKey(
        'email_jobs.id', ondelete='CASCADE'),
        nullable=False, index=True)
    recipient = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default='pending', index=True)
    tracking_id = db.Column(db.String(36), unique=True, nullable=False)

    # Tracking
    opened_at = db.Column(db.DateTime, nullable=True)
    clicked_at = db.Column(db.DateTime, nullable=True)
    error_message = db.Column(db.Text, nullable=True)
