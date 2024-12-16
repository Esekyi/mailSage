from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import Schema, validate, fields
from app.services.auth_services import AuthenticationService
from app.models import APIKey


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


@auth_bp.route('/login', methods=['POST'])
def login():
    """Authenticate user and return token."""
    schema = UserSchema()
    try:
        data = schema.load(request.json)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

    try:
        user, token = AuthenticationService.authenticate_user(
            email=data['email'],
            password=data['password']
        )
        return jsonify({
            "access_token": token,
            "user": {
                "id": user.id,
                "email": user.email,
                "role": user.role
            }
        }), 200

    except ValueError as e:
        return jsonify({'error': str(e)}), 401


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
def revoke_api_key(key_id):
    """Revoke an API key."""
    user_id = get_jwt_identity()
    success = AuthenticationService.revoke_api_key(key_id, user_id)

    if success:
        return jsonify({"message": "API key revoked successfully"}), 200
    return jsonify({"error": "API key not found"}), 404
