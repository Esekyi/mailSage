from .base import BaseModel, SoftDeleteMixin, AuditMixin
from datetime import datetime, timezone
from app.extensions import db


class User(BaseModel, SoftDeleteMixin, AuditMixin):
    __tablename__ = 'users'

    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    is_active = db.Column(db.Boolean, default=True, index=True)
    role = db.Column(db.String(20), default='free', index=True)

    _smtp_config = db.Column('smtp_config', db.JSON, nullable=True)
    monthly_quota = db.Column(db.Integer, default=200)
    emails_sent_this_month = db.Column(db.Integer, default=0)
    last_quota_reset = db.Column(
        db.DateTime, default=datetime.now(timezone.utc))

    # Relationships
    templates = db.relationship('Template', backref='user', lazy='dynamic')
    api_keys = db.relationship('APIKey', backref='user', lazy='dynamic')
