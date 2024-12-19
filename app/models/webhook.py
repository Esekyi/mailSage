from app.extensions import db
from .base import BaseModel, AuditMixin
from app.utils.db import ArrayType


class Webhook(BaseModel, AuditMixin):
    __tablename__ = 'webhooks'

    user_id = db.Column(db.Integer, db.ForeignKey(
        'users.id', ondelete='CASCADE'), nullable=False, index=True)
    url = db.Column(db.String(500), nullable=False)
    description = db.Column(db.String(255), nullable=True)
    # Array of event types
    events = db.Column(ArrayType, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    # For webhook signature verification
    secret = db.Column(db.String(100), nullable=True)

    # Optional fields for monitoring/tracking
    last_triggered_at = db.Column(db.DateTime(timezone=True), nullable=True)
    failure_count = db.Column(db.Integer, default=0)
    last_failure_reason = db.Column(db.Text, nullable=True)

    __table_args__ = (
        db.Index('idx_webhook_events', 'events', postgresql_using='gin'),
    )

    def __repr__(self):
        return f'<Webhook {self.id} {self.url}>'
