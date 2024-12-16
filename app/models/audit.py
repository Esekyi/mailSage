from datetime import datetime, timezone, date
from sqlalchemy import event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import RelationshipProperty
from sqlalchemy.orm.dynamic import AppenderQuery
from app.extensions import db
from sqlalchemy.sql.sqltypes import TIMESTAMP


def serialize_value(value):
    """Safely serialize a value for audit logging."""
    if isinstance(value, AppenderQuery):
        return f"<relationship count={value.count()}>"
    elif hasattr(value, '__table__'):  # SQLAlchemy model instance
        return f"<{value.__class__.__name__} id={getattr(value, 'id', None)}>"
    elif isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


class AuditLog(db.Model):
    """Model for storing audit logs."""
    __tablename__ = 'audit_logs'

    id = db.Column(db.Integer, primary_key=True)
    model_name = db.Column(db.String(50), nullable=False)
    record_id = db.Column(db.Integer, nullable=False)
    operation = db.Column(db.String(10), nullable=False)
    changes = db.Column(JSONB)
    user_id = db.Column(db.Integer, nullable=True)
    timestamp = db.Column(TIMESTAMP(timezone=True),
                          default=datetime.now(timezone.utc)
                          )

    __table_args__ = (
        db.Index('idx_audit_model_record', 'model_name', 'record_id'),
    )


def get_safe_changes(obj, attrs):
    """Get changes in a JSON-serializable format."""
    safe_changes = {}

    for attr, value in attrs.items():
        # Skip internal SQLAlchemy attributes
        if attr.startswith('_'):
            continue

        # Handle different types of changes
        if isinstance(value, dict) and 'old' in value and 'new' in value:
            # For UPDATE operations
            safe_changes[attr] = {
                'old': serialize_value(value['old']),
                'new': serialize_value(value['new'])
            }
        else:
            # For INSERT/DELETE operations
            safe_changes[attr] = serialize_value(value)

    return safe_changes


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
            if operation == 'UPDATE' and hasattr(obj, '__history__'):
                attrs = {}
                for attr in obj.__mapper__.attrs.keys():
                    if not isinstance(obj.__mapper__.attrs[attr],
                                      RelationshipProperty):
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
                    if not isinstance(obj.__mapper__.attrs[attr],
                                      RelationshipProperty)
                }

            # Serialize changes safely
            safe_changes = get_safe_changes(obj, attrs)

            changes.append(AuditLog(
                model_name=obj.__class__.__name__,
                record_id=obj.id,
                operation=operation,
                changes=safe_changes,
                user_id=getattr(obj, 'updated_by', None)
            ))

    for change in changes:
        session.add(change)
