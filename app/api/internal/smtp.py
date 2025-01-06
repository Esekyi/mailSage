from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import Schema, fields, validate, ValidationError
from app.models import User, SMTPConfiguration
from app.services.smtp_service import SMTPService
from app.services.mail_service import MailService
from app.utils.roles import Permission, ResourceLimit, ROLE_CONFIGURATIONS
from app.utils.decorators import permission_required, require_verified_email
from app.extensions import db


class SMTPConfigSchema(Schema):
    """Schema for validating SMTP configuration."""
    name = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    host = fields.Str(required=True)
    port = fields.Int(required=True, validate=validate.Range(min=1, max=65535))
    username = fields.Str(required=True)
    password = fields.Str(required=True)
    use_tls = fields.Bool(missing=True)
    from_email = fields.Email(required=True)
    is_default = fields.Bool(missing=False)
    daily_limit = fields.Int(missing=100, validate=validate.Range(min=1))


smtp_bp = Blueprint('smtp', __name__,
                    url_prefix='/api/v1/smtp')


@smtp_bp.route('/configs', methods=['GET'], strict_slashes=False)
@jwt_required()
@require_verified_email
def list_smtp_configs():
    """List all SMTP configurations for the authenticated user."""
    user = User.query.get_or_404(get_jwt_identity())

    configs = SMTPConfiguration.query.filter_by(
        user_id=user.id,
        is_active=True
    ).all()

    return jsonify({
        "smtp_configurations": [config.to_dict() for config in configs]
    }), 200


@smtp_bp.route('/configs/<int:config_id>', methods=['GET'], strict_slashes=False)
@jwt_required()
@require_verified_email
@permission_required(Permission.MANAGE_SMTP)
def get_smtp_config(config_id: int):
    """Get specific SMTP configuration for the authenticated user."""
    config = SMTPConfiguration.query.get_or_404(config_id)

    # check if user has access to this config
    if int(config.user_id) != int(get_jwt_identity()):
        return jsonify({"error": "Unauthorized"}), 403

    return jsonify(config.to_dict()), 200


@smtp_bp.route('/configs', methods=['POST'], strict_slashes=False)
@jwt_required()
@require_verified_email
@permission_required(Permission.MANAGE_SMTP)
def create_smtp_config():
    """Create new SMTP configuration for the authenticated user."""
    user = User.query.get_or_404(get_jwt_identity())

    # Check SMTP configuration limits based on role
    existing_configs = SMTPConfiguration.query.filter_by(
        user_id=user.id,
        is_active=True
    ).count()

    # Get max configs from role configurations
    max_configs = ROLE_CONFIGURATIONS[user.role]['limits'].get(
        ResourceLimit.SMTPCONFIGS.value, 1)

    if existing_configs >= max_configs:
        return jsonify({
            "error": f"Maximum SMTP configurations ({max_configs}) reached for your plan",
            "code": "SMTP_LIMIT_REACHED"
        }), 403

    # Validate request body
    schema = SMTPConfigSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as e:
        return jsonify({'error': str(e)}), 400

    # Validate SMTP connection with detailed error handling
    current_app.logger.info(f"Validating new SMTP configuration for {
                            data['host']}:{data['port']}")
    valid, error = SMTPService.validate_smtp_config(data)
    if not valid:
        return jsonify({
            "error": "Invalid SMTP configuration",
            "details": error,
            "code": "SMTP_VALIDATION_FAILED"
        }), 400

    # If valid, create the configuration
    config, error = SMTPService.create_config(user.id, data)
    if not config:
        return jsonify({
            "error": "Failed to save configuration",
            "details": error,
            "code": "SMTP_SAVE_FAILED"
        }), 400

    return jsonify({
        "message": "SMTP configuration created successfully",
        "config": config.to_dict()
    }), 201


@smtp_bp.route('/configs/<int:config_id>', methods=['PUT'], strict_slashes=False)
@jwt_required()
@require_verified_email
@permission_required(Permission.MANAGE_SMTP)
def update_smtp_config(config_id: int):
    """Update SMTP configuration."""
    config = SMTPConfiguration.query.get_or_404(config_id)
    if int(config.user_id) != int(get_jwt_identity()):
        return jsonify({"error": "Unauthorized"}), 403

    # Validate request body
    schema = SMTPConfigSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as e:
        return jsonify({'error': str(e)}), 400

    # Check if critical SMTP settings have changed
    credentials_changed = (
        data['host'] != config.host or
        data['port'] != config.port or
        data['username'] != config.username or
        'password' in data
    )

    # Validate SMTP connection if credentials changed
    if credentials_changed:
        current_app.logger.info(f"Validating updated SMTP configuration for {
                                data['host']}:{data['port']}")
        valid, error = SMTPService.validate_smtp_config(data)
        if not valid:
            return jsonify({
                "error": "Invalid SMTP configuration",
                "details": error,
                "code": "SMTP_VALIDATION_FAILED"
            }), 400

    # Update configuration
    success, error = SMTPService.update_config(config, data)
    if not success:
        return jsonify({
            "error": "Failed to update configuration",
            "details": error,
            "code": "SMTP_UPDATE_FAILED"
        }), 400

    return jsonify({
        "message": "SMTP configuration updated successfully",
        "config": config.to_dict()
    }), 200


@smtp_bp.route('/configs/<int:config_id>', methods=['DELETE'], strict_slashes=False)
@jwt_required()
@require_verified_email
@permission_required(Permission.MANAGE_SMTP)
def delete_smtp_config(config_id: int):
    """Delete SMTP configuration."""
    config = SMTPConfiguration.query.get_or_404(config_id)
    if int(config.user_id) != int(get_jwt_identity()):
        return jsonify({"error": "Unauthorized"}), 403

    # Don't allow deletion of last active configuration
    active_configs = SMTPConfiguration.query.filter_by(
        user_id=config.user_id,
        is_active=True
    ).count()
    if active_configs <= 1:
        return jsonify({
            "error": "Cannot delete the last active SMTP configuration",
        }), 400

    success, error = SMTPService.delete_config(config)
    if not success:
        return jsonify({"error": error}), 400

    return jsonify({"message": "Configuration deleted successfully"}), 200


@smtp_bp.route('/configs/<int:config_id>/test', methods=['POST'], strict_slashes=False)
@jwt_required()
@require_verified_email
@permission_required(Permission.MANAGE_SMTP)
def test_smtp_config(config_id: int):
    """Test specific SMTP configuration with comprehensive checks and send a test email."""
    config = SMTPConfiguration.query.get_or_404(config_id)
    if int(config.user_id) != int(get_jwt_identity()):
        return jsonify({"error": "Unauthorized"}), 403

    # Step 1: Test SMTP Connection
    current_app.logger.info(
        f"Starting comprehensive SMTP test for configuration {config.id}")
    connection_success, connection_error = SMTPService.test_connection(config)

    if not connection_success:
        return jsonify({
            "error": "SMTP connection test failed",
            "details": connection_error,
            "code": "SMTP_CONNECTION_TEST_FAILED"
        }), 400

    # Step 2: Send Test Email
    current_app.logger.info(
        f"Sending test email using configuration {config.id}")
    user = User.query.get(config.user_id)
    to_email = request.json.get('to_email', user.email)

    success, error = MailService.send_raw_email(
        user_id=user.id,
        to_email=to_email,
        subject="Mailsage SMTP Test",
        body=f"""
        <h2>SMTP Configuration Test</h2>
        <p>Your SMTP configuration has been tested successfully!</p>
        <h3>Configuration Details:</h3>
        <ul>
            <li>Name: {config.name}</li>
            <li>Host: {config.host}</li>
            <li>Port: {config.port}</li>
            <li>Username: {config.username}</li>
            <li>From Email: {config.from_email}</li>
            <li>TLS Enabled: {'Yes' if config.use_tls else 'No'}</li>
        </ul>
        <p>This email confirms that your SMTP configuration is working correctly.</p>
        """,
        smtp_config=config
    )

    if not success:
        return jsonify({
            "error": "SMTP test email failed",
            "details": error,
            "code": "SMTP_TEST_EMAIL_FAILED",
            "connection_test": "Passed"
        }), 400

    return jsonify({
        "message": "SMTP test completed successfully",
        "details": "Both connection test and test email were successful",
        "config": config.to_dict(),
        "last_test": config.last_test_at.isoformat() if config.last_test_at else None,
        "test_email_sent_to": to_email
    }), 200


@smtp_bp.route('/configs/<int:config_id>/set-default', methods=['POST'], strict_slashes=False)
@jwt_required()
@require_verified_email
@permission_required(Permission.MANAGE_SMTP.value)
def set_default_config(config_id: int):
    """Set an SMTP configuration as default."""
    config = SMTPConfiguration.query.get_or_404(config_id)
    if int(config.user_id) != int(get_jwt_identity()):
        return jsonify({"error": "Unauthorized"}), 403

    try:
        # Unset current default
        SMTPConfiguration.query.filter_by(
            user_id=config.user_id,
            is_default=True
        ).update({'is_default': False})

        # Set new default
        config.is_default = True
        db.session.commit()

        return jsonify({
            "message": "Default SMTP configuration updated",
            "config": config.to_dict()
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Failed to update default configuration: {str(e)}"}), 400
