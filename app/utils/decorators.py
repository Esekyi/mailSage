from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt_identity
from app.extensions import db
from app.models import User, EmailJob
from app.utils.roles import Permission, ResourceLimit, ROLE_CONFIGURATIONS
from typing import Union, List
from datetime import datetime, timezone


def require_verified_email(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        user_id = get_jwt_identity()
        user = db.session.get(User, user_id)

        if not user or not user.email_verified:
            return jsonify({
                "error": "Email verification required",
                "code": "EMAIL_VERIFICATION_REQUIRED"
            }), 403

        return f(*args, **kwargs)
    return decorated_function


def permission_required(permissions: Union[Permission, List[Permission]]):
    """Decorator to check if user has required permissions."""
    if isinstance(permissions, Permission):
        permissions = [permissions]

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = db.session.get(User, get_jwt_identity())
            if not user:
                return jsonify({"error": "User not found"}), 404

            user_permissions = ROLE_CONFIGURATIONS[user.role]['permissions']
            if not all(p.value in user_permissions for p in permissions):
                return jsonify({
                    "error": "Insufficient permissions",
                    "required_permissions": [p.value for p in permissions]
                }), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def get_resource_usage(user: User, resource_type: ResourceLimit) -> int:
    """Get current resource usage for a user."""
    today = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0)

    if resource_type == ResourceLimit.TEMPLATES:
        return user.templates.count()

    elif resource_type == ResourceLimit.API_KEYS:
        return user.api_keys.filter_by(is_active=True).count()

    elif resource_type == ResourceLimit.DAILY_EMAILS:
        return user.email_jobs.filter(
            EmailJob.created_at >= today
        ).with_entities(db.func.sum(EmailJob.recipient_count)).scalar() or 0

    elif resource_type == ResourceLimit.MONTHLY_EMAILS:
        return user.email_jobs.filter(
            db.func.date(EmailJob.created_at) >= today.replace(day=1)
        ).with_entities(db.func.sum(EmailJob.recipient_count)).scalar() or 0

    elif resource_type == ResourceLimit.TEMPLATE_SIZE:
        return sum(t.size for t in user.templates)

    elif resource_type == ResourceLimit.MAX_RECIPIENTS:
        return sum(d.recipient_count for d in user.email_jobs.email_deliveries)

    elif resource_type == ResourceLimit.WEBHOOK_ENDPOINTS:
        return user.webhooks.count()

    return 0


def check_resource_limits(resource_type: ResourceLimit):
    """Decorator to check if user has reached resource limits."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = db.session.get(User, get_jwt_identity())
            if not user:
                return jsonify({"error": "User not found"}), 404

            limit = ROLE_CONFIGURATIONS[user.role]['limits'][
                resource_type.value]
            if limit != -1:  # -1 means unlimited
                current_usage = get_resource_usage(user, resource_type)
                if current_usage >= limit:
                    return jsonify({
                        "error": f"Daily limit reached for {resource_type.value}",
                        "current_usage": current_usage,
                        "limit": limit
                    }), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator
