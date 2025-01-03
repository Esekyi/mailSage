from .base import BaseModel, SoftDeleteMixin, AuditMixin
from datetime import datetime, timezone
from typing import List, Dict
from app.extensions import db
from sqlalchemy.sql.sqltypes import TIMESTAMP
from .smtp import SMTPConfiguration
from .notification import UserPreferences, Notification
from app.utils.db import JSONBType
from sqlalchemy.ext.hybrid import hybrid_property


class User(BaseModel, SoftDeleteMixin, AuditMixin):
    __tablename__ = 'users'

    # Profile fields
    name = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    company = db.Column(db.String(255), nullable=True)
    job_title = db.Column(db.String(255), nullable=True)
    bio = db.Column(db.Text, nullable=True)

    # Authentication fields
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(512), nullable=False)
    is_active = db.Column(db.Boolean, default=True, index=True)
    role = db.Column(db.String(20), default='free', index=True)

    # Two-factor auth fields
    two_factor_enabled = db.Column(db.Boolean, default=False)
    two_factor_secret = db.Column(db.String(32), nullable=True)
    backup_codes = db.Column(JSONBType, nullable=True)

    # Quota fields
    monthly_quota = db.Column(db.Integer, default=200)
    emails_sent_this_month = db.Column(db.Integer, default=0)
    last_quota_reset = db.Column(
        TIMESTAMP(timezone=True), default=datetime.now(timezone.utc))
    reset_token = db.Column(db.String(128), unique=True, nullable=True)
    reset_token_expires = db.Column(TIMESTAMP(timezone=True), nullable=True)

    refresh_token = db.Column(db.String(512), unique=True, nullable=True)
    refresh_token_expires = db.Column(TIMESTAMP(timezone=True), nullable=True)

    # Email verification fields
    email_verified = db.Column(db.Boolean, default=False, index=True)
    verification_token = db.Column(db.String(128), unique=True, nullable=True)
    verification_token_expires = db.Column(
        TIMESTAMP(timezone=True), nullable=True)

    # Relationships
    templates = db.relationship('Template', backref='user', lazy='dynamic')
    api_keys = db.relationship('APIKey', backref='user', lazy='dynamic')
    email_jobs = db.relationship(
        'EmailJob',
        backref=db.backref('user', lazy=True),
        lazy='dynamic',
        cascade="all, delete-orphan"
    )
    webhooks = db.relationship('Webhook', backref='user', lazy='dynamic')
    smtp_configs = db.relationship(
        'SMTPConfiguration',
        backref=db.backref('user_ref', lazy=True),
        lazy='dynamic',
        cascade="all, delete-orphan"
    )
    notifications = db.relationship('Notification', backref='user', lazy='dynamic',
                                    cascade='all, delete-orphan')
    preferences = db.relationship('UserPreferences', backref='user', uselist=False,
                                  cascade='all, delete-orphan')

    # Properties
    @hybrid_property
    def unread_notifications_count(self) -> int:
        return self.notifications.filter(Notification.read_at.is_(None)).count()

    @hybrid_property
    def has_notifications(self) -> bool:
        return self.unread_notifications_count > 0

    def mark_notifications_as_read(self, notification_ids: List[int] = None):
        """Mark specific or all notifications as read."""
        query = self.notifications.filter(Notification.read_at.is_(None))
        if notification_ids:
            query = query.filter(Notification.id.in_(notification_ids))

        query.update({Notification.read_at: datetime.now(timezone.utc)},
                     synchronize_session=False)
        db.session.commit()

    def add_notification(self, title: str, message: str, type: str,
                         category: str, meta_data: Dict = None) -> Notification:
        """Add a new notification for the user."""
        notification = Notification(
            user_id=self.id,
            title=title,
            message=message,
            type=type,
            category=category,
            meta_data=meta_data or {}
        )
        db.session.add(notification)
        db.session.commit()
        return notification

    def get_preferences(self) -> UserPreferences:
        """Get or create user preferences."""
        if not self.preferences:
            self.preferences = UserPreferences(user_id=self.id)
            db.session.commit()
        return self.preferences

    def get_default_smtp(self) -> SMTPConfiguration:
        """Get the default SMTP configuration."""
        return self.smtp_configs.filter_by(
            is_active=True,
            is_default=True
        ).first()

    def get_active_smtp_configs(self):
        """Get all active SMTP configurations."""
        return self.smtp_configs.filter_by(is_active=True).all()

    @property
    def quota_remaining(self) -> int:
        """Get remaining email quota for the month."""
        return max(0, self.monthly_quota - self.emails_sent_this_month)
