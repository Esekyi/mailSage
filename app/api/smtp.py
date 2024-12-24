from flask import Blueprint, request, jsonify
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
    daily_limit = fields.Int(missing=2000, validate=validate.Range(min=1))


smtp_bp = Blueprint('smtp', __name__,
                    url_prefix='/api/v1/smtp')


@smtp_bp.route('/configs', methods=['GET'])
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


@smtp_bp.route('/configs/<int:config_id>', methods=['GET'])
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


@smtp_bp.route('/configs', methods=['POST'])
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

    # Validate SMTP connection
    valid, error = SMTPService.validate_smtp_config(data)
    if not valid:
        return jsonify({"error": f"Invalid SMTP configuration: {error}"}), 400

    # If valid, create the configuration
    config, error = SMTPService.create_config(user.id, data)
    if not config:
        return jsonify({"error": error}), 400

    return jsonify(config.to_dict()), 201


@smtp_bp.route('/configs/<int:config_id>', methods=['PUT'])
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

    # Validate SMTP connection if credentials changed
    if (data['host'] != config.host or
        data['port'] != config.port or
        data['username'] != config.username or
            'password' in data):
        valid, error = SMTPService.validate_smtp_config(data)

        if not valid:
            return jsonify(
                {"error": f"Invalid SMTP configuration: {error}"}), 400

    # Update configuration
    success, error = SMTPService.update_config(config, data)
    if not success:
        return jsonify({"error": error}), 400

    return jsonify(config.to_dict()), 200


@smtp_bp.route('/configs/<int:config_id>', methods=['DELETE'])
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


@smtp_bp.route('/configs/<int:config_id>/test', methods=['POST'])
@jwt_required()
@require_verified_email
@permission_required(Permission.MANAGE_SMTP)
def test_smtp_config(config_id: int):
    """Test specific SMTP configuration."""
    config = SMTPConfiguration.query.get_or_404(config_id)
    if int(config.user_id) != int(get_jwt_identity()):
        return jsonify({"error": "Unauthorized"}), 403

    success, error = MailService.send_test_email(config)
    if not success:
        return jsonify({"error": error}), 400

    return jsonify({
        "message": "Test email sent successfully"
    }), 200


@smtp_bp.route('/configs/<int:config_id>/set-default', methods=['POST'])
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
