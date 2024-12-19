from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import Schema, validate, fields
from app.services.auth_services import AuthenticationService
from app.models import APIKey
from app.services.verification_service import VerificationService
from app.utils.decorators import require_verified_email
from app.extensions import db
from app.utils.roles import ResourceLimit
from app.utils.decorators import check_resource_limits


# Schema definitions from marshmallow
class UserSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=validate.Length(min=8))


class APIKeySchema(Schema):
    name = fields.Str(required=True)
    permissions = fields.Dict(keys=fields.Str(),
                              values=fields.Raw(), required=False)


class PasswordResetRequestSchema(Schema):
    email = fields.Email(required=True)


class PasswordResetSchema(Schema):
    token = fields.Str(required=True)
    new_password = fields.Str(required=True, validate=validate.Length(min=8))


# Blueprint setup
auth_bp = Blueprint('auth', __name__, url_prefix='/api/v1/auth')


@auth_bp.route('/register', methods=['POST'])
def register():
    """Register a new user."""
    schema = UserSchema()
    try:
        data = schema.load(request.json)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    try:
        user, token = AuthenticationService.register_user(
            email=data['email'],
            password=data['password']
        )

        return jsonify({
            "message": "User registered successfully",
            "access_token": token,
            "user": {
                "id": user.id,
                "email": user.email,
                "role": user.role
            }
        }), 201

    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        # Log the unexpected error
        current_app.logger.error(f"Error during user registration: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred'}), 500


@auth_bp.route('/verify-email', methods=['POST'])
def verify_email():
    """Verify user's email using token."""
    token = request.json.get('token')
    if not token:
        return jsonify({"error": "Verification token is required"}), 400

    user = VerificationService.verify_email(token)
    if not user:
        return jsonify({"error": "Invalid or expired verification token"}), 400

    return jsonify({
        "message": "Email verified successfully",
        "user": {
            "id": user.id,
            "email": user.email,
            "email_verified": user.email_verified
        }
    }), 200


@auth_bp.route('/resend-verification', methods=['POST'])
@jwt_required()
def resend_verification():
    """Resend verification email to user."""
    user_id = get_jwt_identity()
    user = db.session.get(user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    if user.email_verified:
        return jsonify({"error": "Email already verified"}), 400

    success = VerificationService.resend_verification_email(user)
    if not success:
        return jsonify({"error": "Failed to send verification email"}), 500

    return jsonify({
        "message": "Verification email resent successfully"
    }), 200


@auth_bp.route('/refresh', methods=['POST'])
def refresh_token():
    """Generate new access token using refresh token."""
    refresh_token = request.json.get('refresh_token')
    if not refresh_token:
        return jsonify({"error": "Refresh token is required"}), 400

    try:
        # Generate new access token
        tokens = AuthenticationService.refresh_access_token(refresh_token)
        return jsonify({'access_token': tokens['access_token']}), 200

    except ValueError as e:
        return jsonify({"error": str(e)}), 401


@auth_bp.route('/login', methods=['POST'])
def login():
    """Authenticate user and return token."""
    schema = UserSchema()
    try:
        data = schema.load(request.json)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    try:
        user, tokens = AuthenticationService.authenticate_user(
            email=data['email'],
            password=data['password']
        )
        return jsonify({
            "access_token": tokens['access_token'],
            "refresh_token": tokens['refresh_token'],
            "token_type": tokens['token_type'],
            "user": {
                "id": user.id,
                "email": user.email,
                "role": user.role
            }
        }), 200

    except ValueError as e:
        if "Email not verified" in str(e):
            # Suggest the user to verify their email
            return jsonify({
                "error": str(e),
                "resend_verification_link": "/api/v1/auth/resend-verification"
            }), 403
        return jsonify({"error": str(e)}), 401


@auth_bp.route('/password-reset', methods=['POST'])
def request_password_reset():
    """Request a password reset."""
    schema = PasswordResetRequestSchema()
    try:
        data = schema.load(request.json)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    AuthenticationService.initiate_password_reset(data['email'])

    # Always return success to prevent email enumeration
    return jsonify({
        "message": "If an account exists with that email, you will receive \
            a password reset link."
    }), 200


@auth_bp.route('/password-reset/verify', methods=['POST'])
def reset_password():
    """Reset password using token."""
    schema = PasswordResetSchema()
    try:
        data = schema.load(request.json)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    user = AuthenticationService.verify_reset_token(data['token'])
    if not user:
        return jsonify({"error": "Invalid or expired reset token"}), 400

    AuthenticationService.reset_password(user, data['new_password'])

    return jsonify({
        "message": "Password reset successfully"
    }), 200


@auth_bp.route('/api-keys', methods=['POST'])
@jwt_required()
@require_verified_email
@check_resource_limits(ResourceLimit.API_KEYS)
def create_api_key():
    """Generate a new API key for the authenticated user."""
    schema = APIKeySchema()
    try:
        data = schema.load(request.json)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    user_id = get_jwt_identity()
    api_key = AuthenticationService.generate_api_key(
        user_id=user_id,
        name=data['name'],
        permissions=data.get('permissions')
    )

    return jsonify({
        "message": "API key generated successfully",
        "api_key": api_key.key,  # Only time the key is exposed
        "key_id": api_key.id,
        "name": api_key.name,
    }), 201


@auth_bp.route('/api-keys', methods=['GET'])
@jwt_required()
@require_verified_email
def list_api_keys():
    """List all active API keys for the authenticated user."""
    user_id = get_jwt_identity()
    api_keys = APIKey.query.filter_by(
        user_id=user_id,
        is_active=True
    ).all()

    return jsonify({
        "api_keys": [{
            "id": key.id,
            "name": key.name,
            "created_at": key.created_at.isoformat(),
            "last_used_at": key.last_used_at.isoformat(
            ) if key.last_used_at else None,
            "expires_at": key.expires_at.isoformat(
            ) if key.expires_at else None
        } for key in api_keys]
    }), 200


@auth_bp.route('/api-keys/<int:key_id>', methods=['DELETE'])
@jwt_required()
@require_verified_email
def revoke_api_key(key_id):
    """Revoke an API key."""
    user_id = get_jwt_identity()
    success = AuthenticationService.revoke_api_key(key_id, user_id)

    if success:
        return jsonify({"message": "API key revoked successfully"}), 200
    return jsonify({"error": "API key not found"}), 404
