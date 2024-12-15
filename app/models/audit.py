from datetime import datetime, timezone
from sqlalchemy import event
from sqlalchemy.dialects.postgresql import JSONB
from app.extensions import db


class AuditLog(db.Model):
    """Model for storing audit logs."""
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    model_name = db.Column(db.String(50), nullable=False)
    record_id = db.Column(db.Integer, nullable=False)
    operation = db.Column(db.String(10), nullable=False)
    changes = db.Column(JSONB)
    user_id = db.Column(db.Integer, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.now(timezone.utc))

    __table_args__ = (
        db.Index('idx_audit_model_record', 'model_name', 'record_id'),
    )


@event.listens_for(db.Session, 'after_flush')
def audit_after_flush(session, context):
    """Create audit log entries for model changes."""

    # Import here to avoid circular imports
    from app.models.base import AuditMixin

    changes = []
    for obj in session.new | session.dirty | session.deleted:
        if isinstance(obj, AuditMixin):
            operation = (
                'INSERT' if obj in session.new
                else 'DELETE' if obj in session.deleted
                else 'UPDATE'
            )

            # Get the changes
            if operation == 'UPDATE':
                attrs = {}
                for attr in obj.__mapper__.attrs.keys():
                    history = getattr(obj.__history__, attr).all()
                    if history:
                        attrs[attr] = {
                            'old': history[0],
                            'new': getattr(obj, attr)
                        }
            else:
                attrs = {
                    attr: getattr(obj, attr)
                    for attr in obj.__mapper__.attrs.keys()
                }

            changes.append(AuditLog(
                model_name=obj.__class__.__name__,
                record_id=obj.id,
                operation=operation,
                changes=attrs,
                user_id=getattr(obj, 'updated_by', None)
            ))

    for change in changes:
        session.add(change)
