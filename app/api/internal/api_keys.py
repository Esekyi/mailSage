from flask import Blueprint, request, jsonify
from app.services.api_key_service import ApiKeyService
from app.models.api_key import ApiKeyType, ApiKeyPermission
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import Schema, fields, validate, ValidationError
from app.utils.logging import logger
from app.utils.decorators import require_verified_email, check_resource_limits
from app.utils.roles import ResourceLimit
api_keys_bp = Blueprint('api_keys', __name__, url_prefix='/api/v1/api-keys')


class CreateApiKeySchema(Schema):
    """Schema for creating API key."""
    name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    key_type = fields.Str(validate=validate.OneOf(
        ['test', 'live']), default='live')
    permissions = fields.List(fields.Str(), required=False)
    expires_in_days = fields.Int(
        required=False, validate=validate.Range(min=1))


@api_keys_bp.route('', methods=['POST'], strict_slashes=False)
@jwt_required()
@require_verified_email
@check_resource_limits(ResourceLimit.API_KEYS)
def create_api_key():
    """
    Create a new API key.

    Example request:
    ```json
    {
        "name": "Production API Key",
        "key_type": "live",
        "permissions": ["send_email", "manage_templates"],
        "expires_in_days": 365
    }
    ```

    Example response:
    ```json
    {
        "message": "API key created successfully",
        "api_key": {
            "id": 1,
            "name": "Production API Key",
            "key_prefix": "abc123",
            "key_type": "live",
            "permissions": ["send_email", "manage_templates"],
            "expires_at": "2024-12-31T23:59:59Z",
            "is_active": true,
            "created_at": "2023-12-31T00:00:00Z"
        },
        "key": "ms_abc123_xyz..."  // Only shown once
    }
    ```
    """
    try:
        # Validate request data
        schema = CreateApiKeySchema()
        data = schema.load(request.get_json())

        # Get the enum by matching its value
        key_type = next(
            (key_type for key_type in ApiKeyType if key_type.value ==
             data['key_type']),
            ApiKeyType.LIVE  # Default to LIVE if not found
        )

        # Validate permissions if provided
        permissions = data.get('permissions')
        if permissions:
            valid_permissions = {p.value for p in ApiKeyPermission}
            if not all(p in valid_permissions for p in permissions):
                return jsonify({
                    "error": "Invalid permissions provided",
                    "valid_permissions": list(valid_permissions)
                }), 400

        # Create API key
        api_key, key, error = ApiKeyService.create_key(
            user_id=get_jwt_identity(),
            name=data['name'],
            key_type=key_type,
            permissions=permissions,
            expires_in_days=data.get('expires_in_days')
        )

        if error:
            return jsonify({"error": error}), 400

        return jsonify({
            "message": "API key created successfully",
            "api_key": api_key.to_dict(),
            "key": key  # Only shown once
        }), 201

    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating API key: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@api_keys_bp.route('', methods=['GET'], strict_slashes=False)
@jwt_required()
@require_verified_email
def list_api_keys():
    """
    List all API keys for the authenticated user.

    Example response:
    ```json
    {
        "api_keys": [
            {
                "id": 1,
                "name": "Production API Key",
                "key_prefix": "abc123",
                "key_type": "live",
                "permissions": ["send_email", "manage_templates"],
                "last_used_at": "2023-12-31T12:00:00Z",
                "expires_at": "2024-12-31T23:59:59Z",
                "is_active": true,
                "created_at": "2023-12-31T00:00:00Z",
                "daily_requests": 150
            }
        ]
    }
    ```
    """
    try:
        user_id = get_jwt_identity()
        api_keys = ApiKeyService.get_user_keys(user_id)
        return jsonify({
            "api_keys": [key.to_dict() for key in api_keys]
        }), 200

    except Exception as e:
        logger.error(f"Error listing API keys: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@api_keys_bp.route('/<int:key_id>', methods=['DELETE'], strict_slashes=False)
@jwt_required()
@require_verified_email
def revoke_api_key(key_id: int):
    """
    Revoke an API key.

    Example response:
    ```json
    {
        "message": "API key revoked successfully"
    }
    ```
    """
    try:
        success, error = ApiKeyService.revoke_key(
            key_id=key_id,
            user_id=get_jwt_identity()
        )

        if not success:
            return jsonify({"error": error}), 400

        return jsonify({
            "message": "API key revoked successfully"
        }), 200

    except Exception as e:
        logger.error(f"Error revoking API key: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@api_keys_bp.route('/<int:key_id>/usage', methods=['GET'], strict_slashes=False)
@jwt_required()
@require_verified_email
def get_api_key_usage(key_id: int):
    """
    Get usage statistics for an API key.

    Query parameters:
    - days: Number of days of history (default: 30)

    Example response:
    ```json
    {
        "usage_stats": {
            "total_requests": 1500,
            "success_requests": 1450,
            "error_requests": 50,
            "success_rate": 96.67,
            "endpoint_usage": {
                "/api/v1/emails/send": 1000,
                "/api/v1/emails/batch": 500
            },
            "daily_average": 50,
            "current_daily_requests": 100,
            "last_used_at": "2023-12-31T12:00:00Z",
            "days_analyzed": 30
        }
    }
    ```
    """
    try:
        days = request.args.get('days', default=30, type=int)
        stats, error = ApiKeyService.get_key_usage(
            key_id=key_id,
            user_id=get_jwt_identity(),
            days=days
        )

        if error:
            return jsonify({"error": error}), 400

        return jsonify({
            "usage_stats": stats
        }), 200

    except Exception as e:
        logger.error(f"Error getting API key usage: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500
