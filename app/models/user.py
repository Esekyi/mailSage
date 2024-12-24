from .base import BaseModel, SoftDeleteMixin, AuditMixin
from datetime import datetime, timezone
from app.extensions import db
from sqlalchemy.sql.sqltypes import TIMESTAMP
from .smtp import SMTPConfiguration


class User(BaseModel, SoftDeleteMixin, AuditMixin):
    __tablename__ = 'users'

    name = db.Column(db.String(255), nullable=False)

    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(512), nullable=False)
    is_active = db.Column(db.Boolean, default=True, index=True)
    role = db.Column(db.String(20), default='free', index=True)

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
