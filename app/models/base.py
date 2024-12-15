from datetime import datetime, timezone
from sqlalchemy.ext.declarative import declared_attr
from app.extensions import db


class BaseModel(db.Model):
    """Abstract base model with common attributes."""
    __abstract__ = True

    id = db.Column(db.Integer, primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.now(timezone.utc))
    updated_at = db.Column(
        db.DateTime, default=datetime.now(
            timezone.utc), onupdate=datetime.now(timezone.utc))


class SoftDeleteMixin:
    """Mixin for soft delete functionality."""
    deleted_at = db.Column(db.DateTime, nullable=True)
    deleted_by = db.Column(db.Integer, nullable=True)

    def soft_delete(self, user_id: int = None) -> None:
        self.deleted_at = datetime.now(timezone.utc)
        self.deleted_by = user_id

    @classmethod
    def not_deleted(cls):
        return cls.query.filter(cls.deleted_at.is_(None))


class AuditMixin:
    """Mixin for audit trail capabilities."""
    created_by = db.Column(db.Integer, nullable=True)
    updated_by = db.Column(db.Integer, nullable=True)

    @declared_attr
    def audit_table(cls):
        return f"{cls.__tablename__}_audit"
