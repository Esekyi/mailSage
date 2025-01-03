from app.extensions import db
from app.models.base import BaseModel, AuditMixin
from datetime import datetime, timezone
from sqlalchemy.sql.sqltypes import TIMESTAMP


class SMTPConfiguration(BaseModel, AuditMixin):
    __tablename__ = 'smtp_configurations'

    user_id = db.Column(db.Integer, db.ForeignKey(
        'users.id', ondelete='CASCADE'), nullable=False)
    # Friendly name for this configuration
    name = db.Column(db.String(255), nullable=False)
    is_default = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)

    # SMTP Details (encrypted)
    host = db.Column(db.String(255), nullable=False)
    port = db.Column(db.Integer, nullable=False)
    username = db.Column(db.String(255), nullable=False)
    password = db.Column(db.String(512), nullable=False)  # Encrypted
    use_tls = db.Column(db.Boolean, default=True)
    from_email = db.Column(db.String(255), nullable=True)

    # Usage tracking
    daily_limit = db.Column(db.Integer, default=100)  # Daily sending limit
    emails_sent_today = db.Column(db.Integer, default=0)
    last_reset_date = db.Column(
        TIMESTAMP(timezone=True), default=datetime.now(timezone.utc).date())

    last_used_at = db.Column(TIMESTAMP(timezone=True))
    last_test_at = db.Column(TIMESTAMP(timezone=True))
    failure_count = db.Column(db.Integer, default=0)

    __table_args__ = (
        db.Index('idx_smtp_user_default', user_id, is_default),
        db.Index('idx_smtp_user_active', user_id, is_active),
    )

    def needs_daily_reset(self) -> bool:
        """Check if the daily counter needs to be reset."""
        if not self.last_reset_date:
            return True
        # Convert datetime to date for proper comparison
        last_reset = self.last_reset_date.date()
        current_date = datetime.now(timezone.utc).date()
        return last_reset < current_date  # Only reset if last_reset is before current date

    def can_send_emails(self) -> bool:
        """Check if this SMTP can still send emails today."""
        if self.needs_daily_reset():
            return True
        return self.emails_sent_today < self.daily_limit

    def to_dict(self, include_sensitive: bool = False) -> dict:
        """Convert to dictionary, optionally excluding sensitive data."""
        data = {
            'id': self.id,
            'name': self.name,
            'host': self.host,
            'port': self.port,
            'username': self.username,
            'use_tls': self.use_tls,
            'from_email': self.from_email,
            'is_default': self.is_default,
            'is_active': self.is_active,
            'daily_limit': self.daily_limit,
            'emails_sent_today': self.emails_sent_today,
            'last_used_at':
            self.last_used_at.isoformat() if self.last_used_at else None,
            'last_test_at':
            self.last_test_at.isoformat() if self.last_test_at else None,
            'failure_count': self.failure_count,
        }

        if include_sensitive:
            data['password'] = self.password

        return data
