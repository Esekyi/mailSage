from .base import BaseModel, AuditMixin
from app.extensions import db
from sqlalchemy.sql.sqltypes import TIMESTAMP
from app.utils.db import JSONBType
from datetime import datetime, timezone, timedelta
from sqlalchemy import func

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
    bounce_count = db.Column(db.Integer, default=0)
    click_count = db.Column(db.Integer, default=0)

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

    @classmethod
    def get_user_statistics(cls, user_id: int, start_date=None, end_date=None):
        """Get comprehensive email statistics for a user."""
        query = cls.query.filter_by(user_id=user_id)

        if start_date:
            query = query.filter(cls.created_at >= start_date)
        if end_date:
            query = query.filter(cls.created_at <= end_date)

        stats = {
            'total_jobs': query.count(),
            'total_emails': db.session.query(func.sum(cls.recipient_count)).filter(cls.user_id == user_id).scalar() or 0,
            'successful_emails': db.session.query(func.sum(cls.success_count)).filter(cls.user_id == user_id).scalar() or 0,
            'failed_emails': db.session.query(func.sum(cls.failure_count)).filter(cls.user_id == user_id).scalar() or 0,
            'pending_jobs': query.filter_by(status='pending').count(),
            'completed_jobs': query.filter_by(status='completed').count(),
            'failed_jobs': query.filter_by(status='failed').count()
        }

        # Calculate success rate
        if stats['total_emails'] > 0:
            stats['success_rate'] = (
                stats['successful_emails'] / stats['total_emails']) * 100
        else:
            stats['success_rate'] = 0

        return stats

    @classmethod
    def get_daily_statistics(cls, user_id: int, days: int = 30):
        """Get daily email statistics for the last N days."""
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)

        # Query to get daily counts stats
        daily_stats = db.session.query(
            func.date_trunc('day', cls.created_at).label('date'),
            func.count(cls.id).label('total_jobs'),
            func.sum(cls.recipient_count).label('total_emails'),
            func.sum(cls.success_count).label('successful_emails'),
            func.sum(cls.failure_count).label('failed_emails')
        ).filter(
            cls.user_id == user_id,
            cls.created_at >= start_date,
            cls.created_at <= end_date
        ).group_by(
            func.date_trunc('day', cls.created_at)
        ).order_by(
            func.date_trunc('day', cls.created_at)
        ).all()

        return [{
            'date': stats.date.strftime('%Y-%m-%d'),
            'total_jobs': stats.total_jobs,
            'total_emails': stats.total_emails or 0,
            'successful_emails': stats.successful_emails or 0,
            'failed_emails': stats.failed_emails or 0,
            'success_rate': ((stats.successful_emails or 0) / (stats.total_emails or 1)) * 100
        } for stats in daily_stats]

    @classmethod
    def get_smtp_performance(cls, user_id: int):
        """Get performance statistics per SMTP configuration."""
        return db.session.query(
            cls.smtp_config_id,
            func.count(cls.id).label('total_jobs'),
            func.sum(cls.recipient_count).label('total_emails'),
            func.sum(cls.success_count).label('successful_emails'),
            func.sum(cls.failure_count).label('failed_emails'),
            func.avg(
                (cls.success_count * 100.0) / cls.recipient_count
            ).label('success_rate')
        ).filter(
            cls.user_id == user_id,
            cls.smtp_config_id.isnot(None)
        ).group_by(
            cls.smtp_config_id
        ).all()


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

    @classmethod
    def get_engagement_metrics(cls, job_id: int):
        """Get engagement metrics for a specific email job."""
        total_delivered = cls.query.filter_by(
            job_id=job_id,
            status='sent'
        ).count()

        if total_delivered == 0:
            return {
                'open_rate': 0,
                'click_rate': 0,
                'total_opens': 0,
                'total_clicks': 0,
                'total_delivered': 0
            }

        total_opens = cls.query.filter_by(
            cls.job_id == job_id,
            cls.opened_at.isnot(None)
        ).count()

        total_clicks = cls.query.filter_by(
            cls.job_id == job_id,
            cls.clicked_at.isnot(None)
        ).count()

        return {
            'open_rate': (total_opens / total_delivered) * 100,
            'click_rate': (total_clicks / total_delivered) * 100,
            'total_opens': total_opens,
            'total_clicks': total_clicks,
            'total_delivered': total_delivered
        }

    @classmethod
    def get_delivery_time_stats(cls, job_id: int):
        """Get delivery time statistics for a job."""
        deliveries = cls.query.filter_by(job_id=job_id).all()
        delivery_times = []

        for delivery in deliveries:
            if delivery.status == 'sent' and delivery.last_attempt and delivery.created_at:
                delivery_time = (delivery.last_attempt -
                                 delivery.created_at).total_seconds()
                delivery_times.append(delivery_time)

        if not delivery_times:
            return {
                'average_delivery_time': 0,
                'min_delivery_time': 0,
                'max_delivery_time': 0,
                'total_deliveries': 0
            }

        return {
            'average_delivery_time': sum(delivery_times) / len(delivery_times),
            'min_delivery_time': min(delivery_times),
            'max_delivery_time': max(delivery_times),
            'total_deliveries': len(delivery_times)
        }
