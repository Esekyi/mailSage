from datetime import datetime, timezone
from typing import Optional, List
from app.extensions import db
from app.utils.db import JSONBType
from app.models.base import BaseModel, AuditMixin
from app.models.mixins import SerializationMixin

import secrets
import enum


class ApiKeyPermission(enum.Enum):
    """Enum for API key permissions."""
    SEND_EMAIL = "send_email"
    MANAGE_TEMPLATES = "manage_templates"
    MANAGE_SMTP = "manage_smtp"
    VIEW_ANALYTICS = "view_analytics"
    WEBHOOK_MANAGEMENT = "webhook_management"


class ApiKeyType(enum.Enum):
    """Enum for API key types."""
    TEST = "test"
    LIVE = "live"


class ApiKey(BaseModel, AuditMixin, SerializationMixin):
    """Model for API keys."""
    __tablename__ = 'api_keys'

    user_id = db.Column(db.Integer, db.ForeignKey(
        'users.id', ondelete='CASCADE'),
        nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    key_prefix = db.Column(db.String(8), nullable=False)
    key_hash = db.Column(db.String(255), nullable=False)
    key_type = db.Column(
        db.Enum(ApiKeyType),
        nullable=False,
        default=ApiKeyType.LIVE
    )
    permissions = db.Column(
        JSONBType,
        nullable=False,
        default=lambda: [p.value for p in ApiKeyPermission]
    )
    last_used_at = db.Column(db.DateTime(timezone=True))
    expires_at = db.Column(db.DateTime(timezone=True))
    is_active = db.Column(db.Boolean, default=True)
    daily_requests = db.Column(db.Integer, default=0)
    last_reset_date = db.Column(
        db.Date,
        default=lambda: datetime.now(timezone.utc).date()
    )

    # Relationships
    user = db.relationship('User', back_populates='api_keys')
    usage_logs = db.relationship('ApiKeyUsage', back_populates='api_key')

    @classmethod
    def generate_key(cls) -> tuple[str, str, str]:
        """Generate a new API key, prefix, and hash."""
        # prefix is the first 8 characters of the key includes test or live
        prefix = secrets.token_hex(4)  # 8 characters
        # Generate random part using base64 for URL safety
        random_part = secrets.token_urlsafe(32)
        key = f"ms_{prefix}_{random_part}"  # Format: ms_<prefix>_<random>
        key_hash = cls.hash_key(key)
        return key, prefix, key_hash

    @staticmethod
    def validate_key_format(key: str) -> bool:
        """Validate the format of an API key.
        Format: ms_<prefix>_<random>
        Only validates the prefix format (ms_<8_hex_chars>_)
        """
        if not key.startswith("ms_"):
            return False

        # Split should have at least 3 parts
        parts = key.split('_', 2)
        if len(parts) < 3:
            return False

        # Validate prefix is 8 hex characters
        prefix = parts[1]
        try:
            int(prefix, 16)  # Validate hex format
            return len(prefix) == 8
        except ValueError:
            return False

    @staticmethod
    def hash_key(key: str) -> str:
        """Hash an API key."""
        from werkzeug.security import generate_password_hash
        return generate_password_hash(key)

    def verify_key(self, key: str) -> bool:
        """Verify an API key."""
        from werkzeug.security import check_password_hash

        # First validate the key format
        if not self.validate_key_format(key):
            return False

        # Then check the hash
        return check_password_hash(self.key_hash, key)

    def has_permission(self, permission: ApiKeyPermission) -> bool:
        """Check if key has specific permission."""
        return permission.value in self.permissions

    def track_usage(self, endpoint: str, status_code: int):
        """Track API key usage."""
        self.last_used_at = datetime.now(timezone.utc)

        # Reset daily counter if needed
        today = datetime.now(timezone.utc).date()
        if self.last_reset_date != today:
            self.daily_requests = 0
            self.last_reset_date = today

        self.daily_requests += 1

        # Create usage log
        usage = ApiKeyUsage(
            api_key_id=self.id,
            endpoint=endpoint,
            status_code=status_code
        )
        db.session.add(usage)

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            raise e

    def revoke(self):
        """Revoke the API key."""
        self.is_active = False
        self.expires_at = datetime.now(timezone.utc)
        db.session.commit()

    def to_dict(self) -> dict:
        """Convert API key to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'key_prefix': self.key_prefix,
            'key_type': self.key_type.value,
            'permissions': self.permissions,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat(),
            'daily_requests': self.daily_requests
        }


class ApiKeyUsage(BaseModel):
    """Model for tracking API key usage."""
    __tablename__ = 'api_key_usage'

    id = db.Column(db.Integer, primary_key=True)
    api_key_id = db.Column(
        db.Integer,
        db.ForeignKey('api_keys.id'),
        nullable=False
    )
    endpoint = db.Column(db.String(255), nullable=False)
    status_code = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    api_key = db.relationship('ApiKey', back_populates='usage_logs')
