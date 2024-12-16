from app.extensions import db
from app.models import User, AuditLog


def cleanup_users_without_audit():
    """Clean up users that were created without proper audit logs."""
    with db.session.begin():
        # Find users without corresponding audit logs
        users_to_delete = db.session.query(User).filter(
            ~User.id.in_(
                db.session.query(AuditLog.record_id).filter(
                    AuditLog.model_name == 'User',
                    AuditLog.operation == 'INSERT'
                )
            )
        ).all()

        # Delete users without audit logs
        for user in users_to_delete:
            db.session.delete(user)

        return len(users_to_delete)
