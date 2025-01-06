from flask import Blueprint, request, jsonify, current_app
from marshmallow import Schema, validate, fields, ValidationError
from app.services.auth_services import AuthenticationService
from app.models import User
from app.services.verification_service import VerificationService


# Schema definitions from marshmallow
class RegisterSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=validate.Length(min=8))
    name = fields.Str(required=True)


class LoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True)



class PasswordResetRequestSchema(Schema):
    email = fields.Email(required=True)


class PasswordResetSchema(Schema):
    token = fields.Str(required=True)
    new_password = fields.Str(required=True, validate=validate.Length(min=8))


# Blueprint setup
auth_bp = Blueprint('auth', __name__, url_prefix='/api/v1/auth')


@auth_bp.route('/register', methods=['POST'], strict_slashes=False)
def register():
    """Register a new user."""
    schema = RegisterSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as e:
        return jsonify({
            "status": "error",
            "message": "Validation error",
            "errors": e.messages
        }), 400

    try:
        user, token = AuthenticationService.register_user(
            email=data['email'],
            password=data['password'],
            name=data['name']
        )

        return jsonify({
            "status": "success",
            "message": "Registration successful. Please check your email to verify your account.",
            "data": {
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "name": user.name,
                    "email_verified": user.email_verified
                }
            }
        }), 201

    except ValueError as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 400
    except Exception as e:
        current_app.logger.error(f"Error during user registration: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "Failed to create account. Please try again later."
        }), 500


@auth_bp.route('/verify-email', methods=['POST', 'GET'], strict_slashes=False)
def verify_email():
    """Verify user's email using token."""
    if request.method == 'POST':
        # Handle POST requests
        token = request.json.get('token')
        if not token:
            return jsonify({"error": "Verification token is required"}), 400

    elif request.method == 'GET':
        # Handle GET requests
        token = request.args.get('token')
        if not token:
            return jsonify(
                {
                    "error": "Verification token is required"
                }), 400

    user = VerificationService.verify_email(token)
    if not user:
        return jsonify(
            {
                "error": "Invalid or expired verification token"
            }), 400

    return jsonify({
        "message": "Email verified successfully",
        "user": {
            "id": user.id,
            "email": user.email,
            "email_verified": user.email_verified
        }
    }), 200


@auth_bp.route('/resend-verification', methods=['POST'], strict_slashes=False)
def resend_verification():
    """Resend verification email to user."""
    try:
        data = request.get_json()
        email = data.get('email')

        if not email:
            return jsonify({
                "status": "error",
                "message": "Email is required"
            }), 400

        user = User.query.filter_by(email=email).first()
        if not user:
            return jsonify({
                "status": "error",
                "message": "If an account exists, a verification email will be sent."
            }), 200

        if user.email_verified:
            return jsonify({
                "status": "error",
                "message": "Email already verified"
            }), 400

        if VerificationService.resend_verification_email(user):
            return jsonify({
                "status": "success",
                "message": "Verification email has been sent. Please check your inbox."
            }), 200
        else:
            return jsonify({
                "status": "error",
                "message": "Failed to send verification email. Please try again later."
            }), 500

    except Exception as e:
        current_app.logger.error(
            f"Resend verification error: {str(e)}")
        current_app.logger.exception("Full traceback:")
        return jsonify({
            "status": "error",
            "message": "An unexpected error occurred"
        }), 500


@auth_bp.route('/refresh', methods=['POST'], strict_slashes=False)
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


@auth_bp.route('/login', methods=['POST'], strict_slashes=False)
def login():
    """Authenticate user and return token."""
    schema = LoginSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as e:
        return jsonify({
            "status": "error",
            "message": "Validation error",
            "errors": e.messages
        }), 400

    try:
        user, tokens = AuthenticationService.authenticate_user(
            email=data['email'],
            password=data['password']
        )
        return jsonify({
            "status": "success",
            "data": {
                "access_token": tokens['access_token'],
                "refresh_token": tokens['refresh_token'],
                "token_type": tokens['token_type'],
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "role": user.role,
                    "name": user.name,
                    "email_verified": user.email_verified
                }
            }
        }), 200

    except ValueError as e:
        if "Email not verified" in str(e):
            # Suggest the user to verify their email
            return jsonify({
                "status": "error",
                "message": "Email not verified. Please verify your email before logging in.",
                "code": "EMAIL_VERIFICATION_REQUIRED"
            }), 403
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 401
    except Exception as e:
        current_app.logger.error(f"Login error: {str(e)}")
        return jsonify({
            "status": "error",
            "message": "An unexpected error occurred"
        }), 500


@auth_bp.route('/password-reset', methods=['POST'], strict_slashes=False)
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
        "message": "If an account exists with that email, you will receive a password reset link."
    }), 200


@auth_bp.route('/password-reset/verify', methods=['POST'], strict_slashes=False)
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
