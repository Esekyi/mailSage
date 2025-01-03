from datetime import datetime, timezone
from typing import Tuple
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from app.extensions import db, redis_client
from app.models import User, Template, APIKey
from app.utils.logging import logger
from app.utils.roles import ROLE_CONFIGURATIONS, ResourceLimit


class QuotaService:
    @staticmethod
    def check_rate_limit(user_id: int, rate_limit: int) -> Tuple[bool, int]:
        """Check if user has exceeded rate limit using Redis."""
        key = f"rate_limit:{user_id}:{datetime.now(timezone.utc)
                                      .strftime('%Y-%m-%d-%H')}"
        count = redis_client.incr(key)
        if count == 1:
            redis_client.expire(key, 3600)  # Expire after 1 hour
        return count <= rate_limit, rate_limit - count

    @staticmethod
    def reset_monthly_quotas() -> bool:
        """Reset monthly quotas for all eligible users."""
        try:
            now = datetime.now(timezone.utc)
            User.query.filter(
                func.extract('month', User.last_quota_reset) != now.month
            ).update({
                'emails_sent_this_month': 0,
                'last_quota_reset': now
            }, synchronize_session=False)
            db.session.commit()
            return True
        except SQLAlchemyError as e:
            logger.error(f"Error resetting quotas: {str(e)}")
            db.session.rollback()
            return False

    @staticmethod
    def check_resource_limit(user_id: int, resource_type: str) -> bool:
        user = User.query.get(user_id)
        if not user:
            return False

        limit = ROLE_CONFIGURATIONS[user.role]['limits'][resource_type]
        if limit == -1:  # unlimited
            return True

        current_count = {
            ResourceLimit.TEMPLATES.value: Template.query.filter_by(
                user_id=user_id).count(),
            ResourceLimit.API_KEYS.value: APIKey.query.filter_by(
                user_id=user_id, is_active=True).count(),
        }.get(resource_type, 0)

        return current_count < limit
