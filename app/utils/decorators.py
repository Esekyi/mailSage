from functools import wraps
from flask import jsonify
from flask_jwt_extended import get_jwt_identity
from app.extensions import db
from app.models import User, EmailJob
from app.utils.roles import Permission, ResourceLimit, ROLE_CONFIGURATIONS
from typing import Union, List
from datetime import datetime, timezone
from flask import current_app


def require_verified_email(f):
    """Decorator to check if user's email is verified."""
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


def permission_required(permissions: Union[Permission,
                                           List[Permission], str, List[str]]):
    """
    Decorator to check if user has required permissions.

    Args:
        permissions: Can be a Permission enum, list of Permission enums,
                    permission string, or list of permission strings
    """
    if isinstance(permissions, (Permission, str)):
        permissions = [permissions]

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            user = db.session.get(User, get_jwt_identity())
            if not user:
                return jsonify({"error": "User not found"}), 404

            user_permissions = ROLE_CONFIGURATIONS[user.role]['permissions']

            # Convert permissions to strings if they're enums
            required_permissions = [
                p.value if isinstance(p, Permission) else p
                for p in permissions
            ]

            if not all(
                    perm in user_permissions for perm in required_permissions):
                return jsonify({
                    "error": "Insufficient permissions",
                    "required_permissions": required_permissions,
                    "user_permissions": user_permissions
                }), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator


def get_resource_usage(user: User, resource_type: ResourceLimit) -> int:
    """Get current resource usage for a user."""
    today = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0)

    if resource_type == ResourceLimit.TEMPLATES:
        return user.templates.filter_by(is_active=True, deleted_at=None).count()

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
        return sum(t.size for t in user.templates.filter_by(is_active=True, deleted_at=None).all())

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

            try:
                limit = ROLE_CONFIGURATIONS[user.role]['limits'][
                    resource_type.value]
            except KeyError:
                current_app.logger.error(
                    f"No limit configuration found for role {
                        user.role} and resource {resource_type.value}"
                )
                return jsonify({
                    "error": "Resource limit configuration not found"
                }), 500

            if limit != -1:  # -1 means unlimited
                current_usage = get_resource_usage(user, resource_type)
                if current_usage >= limit:
                    resource_name = resource_type.value.replace('_', ' ').title()
                    return jsonify({
                        "error": f"You have reached the limit of {limit} {resource_name} "
                        f"for your {user.role} plan",
                        "current_usage": current_usage,
                        "limit": limit,
                        "resource_type": resource_type.value,
                        "plan": user.role
                    }), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator
