from .base import BaseModel, AuditMixin
from app.extensions import db
from app.models.mixins import SerializationMixin


class APIKey(BaseModel, AuditMixin, SerializationMixin):
    __tablename__ = 'api_keys'

    user_id = db.Column(db.Integer, db.ForeignKey(
        'users.id', ondelete='CASCADE'),
        nullable=False, index=True)
    key_hash = db.Column(db.String(128), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=True)
    permissions = db.Column(db.JSON, default=dict)
    is_active = db.Column(db.Boolean, default=True, index=True)
    last_used_at = db.Column(db.DateTime, nullable=True)
