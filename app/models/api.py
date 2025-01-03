from .base import BaseModel, AuditMixin
from app.extensions import db
from app.models.mixins import SerializationMixin
from sqlalchemy.sql.sqltypes import TIMESTAMP
from app.utils.db import JSONBType


class APIKey(BaseModel, AuditMixin, SerializationMixin):
    __tablename__ = 'api_keys'

    user_id = db.Column(db.Integer, db.ForeignKey(
        'users.id', ondelete='CASCADE'),
        nullable=False, index=True)
    key_hash = db.Column(db.String(128), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=True)
    permissions = db.Column(JSONBType, default=dict)

    is_active = db.Column(db.Boolean, default=True, index=True)
    last_used_at = db.Column(TIMESTAMP(timezone=True), nullable=True)
    expires_at = db.Column(TIMESTAMP(timezone=True), nullable=False)
