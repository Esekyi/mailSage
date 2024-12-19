from .base import BaseModel, SoftDeleteMixin, AuditMixin
from datetime import datetime, timezone
from app.extensions import db
from sqlalchemy.sql.sqltypes import TIMESTAMP
from app.utils.db import JSONBType


class User(BaseModel, SoftDeleteMixin, AuditMixin):
    __tablename__ = 'users'

    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(512), nullable=False)
    is_active = db.Column(db.Boolean, default=True, index=True)
    role = db.Column(db.String(20), default='free', index=True)

    _smtp_config = db.Column('smtp_config', JSONBType, nullable=True)
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
        backref='user',
        lazy='dynamic',
        cascade="all, delete-orphan"
    )
    webhooks = db.relationship('Webhook', backref='user', lazy='dynamic')
