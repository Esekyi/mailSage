from typing import Optional, List, Tuple, Dict, Any
from datetime import datetime, timezone, timedelta
from app.extensions import db
from app.models.api_key import ApiKey, ApiKeyType, ApiKeyPermission, ApiKeyUsage
from app.utils.logging import logger
from app.models.user import User


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
            # Extract prefix
            parts = key.split('_')
            if len(parts) != 3 or parts[0] != 'ms':
                return None, "Invalid API key format"

            prefix = parts[1]

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
            api_key = ApiKey.query.filter_by(
                id=key_id,
                user_id=user_id
            ).first()

            if not api_key:
                return None, "API key not found"

            # Calculate date range
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=days)

            # Get usage logs
            usage_logs = ApiKeyUsage.query.filter(
                ApiKeyUsage.api_key_id == key_id,
                ApiKeyUsage.timestamp >= start_date,
                ApiKeyUsage.timestamp <= end_date
            ).all()

            # Calculate statistics
            total_requests = len(usage_logs)
            success_requests = len(
                [log for log in usage_logs if 200 <= log.status_code < 300])
            error_requests = len(
                [log for log in usage_logs if log.status_code >= 400])

            # Group by endpoint
            endpoint_usage = {}
            for log in usage_logs:
                endpoint_usage[log.endpoint] = endpoint_usage.get(
                    log.endpoint, 0) + 1

            return {
                "total_requests": total_requests,
                "success_requests": success_requests,
                "error_requests": error_requests,
                "success_rate": (success_requests / total_requests * 100) if total_requests > 0 else 0,
                "endpoint_usage": endpoint_usage,
                "daily_average": total_requests / days if days > 0 else 0
            }, None

        except Exception as e:
            logger.error(f"Error getting API key usage: {str(e)}")
            return None, "Failed to get API key usage"

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
