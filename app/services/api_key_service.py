from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime, timezone, timedelta
from app.extensions import db
from app.models.api_key import ApiKey, ApiKeyType, ApiKeyPermission, ApiKeyUsage
from app.utils.logging import logger
from app.models.user import User
from app.utils.roles import ROLE_CONFIGURATIONS, ResourceLimit


class ApiKeyService:
    """Service for managing API keys."""

    @staticmethod
    def create_key(
        user_id: int,
        name: str,
        key_type: ApiKeyType = ApiKeyType.LIVE,
        permissions: Optional[List[str]] = None,
        expires_in_days: Optional[int] = None
    ) -> Tuple[Optional[ApiKey], Optional[str], Optional[str]]:
        """
        Create a new API key.

        Args:
            user_id: ID of the user creating the key
            name: Name/description of the key
            key_type: Type of key (test/live)
            permissions: List of permission strings
            expires_in_days: Optional expiration in days

        Returns:
            Tuple of (ApiKey object, plain text key, error message)
        """
        try:
            # Generate key
            key, prefix, key_hash = ApiKey.generate_key()

            # Set expiration if provided
            expires_at = None
            if expires_in_days:
                expires_at = datetime.now(
                    timezone.utc) + timedelta(days=expires_in_days)

            # Create API key record
            api_key = ApiKey(
                user_id=user_id,
                name=name,
                key_prefix=prefix,
                key_hash=key_hash,
                key_type=key_type,
                permissions=permissions or [p.value for p in ApiKeyPermission],
                expires_at=expires_at
            )

            db.session.add(api_key)

            # Add notification
            user = User.query.get_or_404(user_id)
            user.add_notification(
                title="API Key Created",
                message=f"API key '{api_key.name}' has been created",
                type="info",
                category="api_key",
                meta_data={"api_key_id": api_key.id}
            )

            db.session.commit()

            return api_key, key, None

        except Exception as e:
            db.session.rollback()
            logger.error(f"Error creating API key: {str(e)}")
            return None, None, "Failed to create API key"

    @staticmethod
    def validate_key(key: str) -> Tuple[Optional[ApiKey], Optional[str]]:
        """
        Validate an API key.

        Args:
            key: The API key to validate

        Returns:
            Tuple of (ApiKey object if valid, error message if invalid)
        """
        try:
            # First validate the key format
            if not ApiKey.validate_key_format(key):
                return None, "Invalid API key format"

            # Extract prefix from ms_<prefix>_<random>
            prefix = key.split('_', 2)[1]

            # Find key by prefix
            api_key = ApiKey.query.filter_by(
                key_prefix=prefix,
                is_active=True
            ).first()

            if not api_key:
                return None, "API key not found"

            # Verify key
            if not api_key.verify_key(key):
                return None, "Invalid API key"

            # Check expiration
            if api_key.expires_at and api_key.expires_at < datetime.now(timezone.utc):
                return None, "API key has expired"

            return api_key, None

        except Exception as e:
            logger.error(f"Error validating API key: {str(e)}")
            return None, "Error validating API key"

    @staticmethod
    def get_user_keys(user_id: int) -> List[ApiKey]:
        """Get all API keys for a user."""
        return ApiKey.query.filter_by(
            user_id=user_id,
            is_active=True
        ).order_by(
            ApiKey.created_at.desc()
        ).all()

    @staticmethod
    def revoke_key(key_id: int, user_id: int) -> Tuple[bool, Optional[str]]:
        """
        Revoke an API key.

        Args:
            key_id: ID of the key to revoke
            user_id: ID of the user who owns the key

        Returns:
            Tuple of (success boolean, error message if any)
        """
        try:
            api_key = ApiKey.query.filter_by(
                id=key_id,
                user_id=user_id,
                is_active=True
            ).first()

            if not api_key:
                return False, "API key not found"

            api_key.revoke()

            # Add notification
            user = User.query.get_or_404(user_id)
            user.add_notification(
                title="API Key Revoked",
                message=f"API key '{api_key.name}' has been revoked",
                type="critical",
                category="api_key",
                meta_data={"api_key_id": api_key.id}
            )

            return True, None

        except Exception as e:
            logger.error(f"Error revoking API key: {str(e)}")
            return False, "Failed to revoke API key"

    @staticmethod
    def get_key_usage(
        key_id: int,
        user_id: int,
        days: int = 30
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        """
        Get usage statistics for an API key.

        Args:
            key_id: ID of the API key
            user_id: ID of the user who owns the key
            days: Number of days of history to return

        Returns:
            Tuple of (usage stats dict, error message if any)
        """
        try:
            # Get API key with a fresh query to ensure we have latest data
            api_key = db.session.query(ApiKey).filter(
                ApiKey.id == key_id,
                ApiKey.user_id == user_id,
                ApiKey.is_active == True
            ).with_for_update().first()

            if not api_key:
                return None, "API key not found"

            # Get user to determine role and limits
            user = User.query.get(user_id)
            if not user:
                return None, "User not found"

            # Get daily request limit from role configuration
            daily_limit = ROLE_CONFIGURATIONS[user.role]['limits'][
                ResourceLimit.DAILY_API_KEY_USAGE.value]
            if daily_limit == -1:  # -1 means unlimited
                daily_limit = float('inf')

            # Calculate date range
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=days)

            # Get usage logs with explicit join
            usage_logs = db.session.query(ApiKeyUsage).filter(
                ApiKeyUsage.api_key_id == key_id,
                ApiKeyUsage.timestamp >= start_date,
                ApiKeyUsage.timestamp <= end_date,
            ).order_by(ApiKeyUsage.timestamp.desc()).all()

            # Calculate statistics
            total_requests = len(usage_logs)
            success_requests = sum(
                1 for log in usage_logs if 200 <= log.status_code < 300)
            error_requests = sum(
                1 for log in usage_logs if log.status_code >= 400)

            # Group by endpoint
            endpoint_usage = {}
            for log in usage_logs:
                endpoint_usage[log.endpoint] = endpoint_usage.get(
                    log.endpoint, 0) + 1

            # Calculate daily average and success rate
            daily_average = round(total_requests / days, 2) if days > 0 else 0
            success_rate = round(
                (success_requests / total_requests * 100), 2) if total_requests > 0 else 0

            # Refresh the API key to get latest daily_requests
            db.session.refresh(api_key)

            return {
                "total_requests": total_requests,
                "success_requests": success_requests,
                "error_requests": error_requests,
                "success_rate": success_rate,
                "endpoint_usage": endpoint_usage,
                "daily_average": daily_average,
                "current_daily_requests": api_key.daily_requests,
                "daily_limit": daily_limit,
                "daily_remaining": daily_limit - api_key.daily_requests if daily_limit != float('inf') else None,
                "last_used_at": api_key.last_used_at.isoformat() if api_key.last_used_at else None,
                "days_analyzed": days
            }, None

        except Exception as e:
            logger.error(
                f"Error getting API key usage - Key ID: {
                    key_id}, User ID: {user_id}, Error: {str(e)}",
                exc_info=True
            )
            return None, f"Failed to get API key usage: {str(e)}"

    @staticmethod
    def cleanup_expired_keys():
        """Clean up expired API keys."""
        try:
            expired_keys = ApiKey.query.filter(
                ApiKey.expires_at < datetime.now(timezone.utc),
                ApiKey.is_active == True  # noqa
            ).all()

            for key in expired_keys:
                key.revoke()

            return len(expired_keys)

        except Exception as e:
            logger.error(f"Error cleaning up expired keys: {str(e)}")
            return 0
