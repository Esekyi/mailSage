from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.services.user_service import UserService
from marshmallow import Schema, fields, validate, ValidationError
from app.models import User, Notification, Template, SMTPConfiguration
from app.extensions import db
from flask import current_app


class ProfileUpdateSchema(Schema):
    name = fields.Str(required=True)
    phone = fields.Str(required=False)
    company = fields.Str(required=False)
    job_title = fields.Str(required=False)
    bio = fields.Str(required=False)


class PreferencesSchema(Schema):
    email_notifications = fields.Dict(keys=fields.Str(), values=fields.Bool())
    in_app_notifications = fields.Dict(keys=fields.Str(), values=fields.Bool())
    timezone = fields.Str()
    theme = fields.Str(validate=validate.OneOf(['light', 'dark']))


class PermanentDeleteSchema(Schema):
    confirmation_text = fields.Str(required=True)


class PreferencesUpdateSchema(Schema):
    email_notifications = fields.Dict(keys=fields.Str(),
                                      values=fields.Bool(),
                                      required=False)
    in_app_notifications = fields.Dict(keys=fields.Str(),
                                       values=fields.Bool(),
                                       required=False)
    preferences = fields.Dict(keys=fields.Str(),
                              values=fields.Bool(),
                              required=False)
    timezone = fields.Str(required=False)
    theme = fields.Str(validate=validate.OneOf(['light', 'dark']),
                       required=False)


profile_bp = Blueprint('profile', __name__, url_prefix='/api/v1/profile')


@profile_bp.route('', methods=['GET'], strict_slashes=False)
@jwt_required()
def get_profile():
    """Get user profile and preferences."""
    user = User.query.get_or_404(get_jwt_identity())

    return jsonify({
        "profile": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "phone": user.phone,
            "company": user.company,
            "job_title": user.job_title,
            "bio": user.bio,
            "role": user.role,
            "two_factor_enabled": user.two_factor_enabled
        },
        "preferences": user.get_preferences().preferences,
        "notifications_settings": {
            "email_notifications": user.get_preferences().email_notifications,
            "in_app_notifications": user.get_preferences().in_app_notifications
        }
    }), 200


@profile_bp.route('/preferences', methods=['GET'], strict_slashes=False)
@jwt_required()
def get_preferences():
    """Get all user preferences."""
    user = User.query.get_or_404(get_jwt_identity())
    prefs = user.get_preferences()

    return jsonify({
        "email_notifications": prefs.email_notifications,
        "in_app_notifications": prefs.in_app_notifications,
        "preferences": prefs.preferences,
        "timezone": prefs.timezone,
        "theme": prefs.theme
    }), 200


@profile_bp.route('/preferences', methods=['PUT'], strict_slashes=False)
@jwt_required()
def update_preferences():
    """Update user preferences."""
    schema = PreferencesUpdateSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400

    user = User.query.get_or_404(get_jwt_identity())
    prefs = user.get_preferences()

    try:
        if "preferences" in data:
            prefs.update_preferences(data["preferences"])

        if "email_notifications" in data:
            prefs.update_notifications('email', data["email_notifications"])

        if "in_app_notifications" in data:
            prefs.update_notifications('in_app', data["in_app_notifications"])

        if "timezone" in data:
            prefs.timezone = data["timezone"]

        if "theme" in data:
            prefs.theme = data["theme"]

        db.session.commit()

        return jsonify({
            "message": "Preferences updated successfully",
            "preferences": {
                "email_notifications": prefs.email_notifications,
                "in_app_notifications": prefs.in_app_notifications,
                "preferences": prefs.preferences,
                "timezone": prefs.timezone,
                "theme": prefs.theme
            }
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400


@profile_bp.route('', methods=['PUT'], strict_slashes=False)
@jwt_required()
def update_profile():
    """Update user profile."""
    schema = ProfileUpdateSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400

    success, error = UserService.update_profile(get_jwt_identity(), data)
    if not success:
        return jsonify({"error": error}), 400

    return jsonify({"message": "Profile updated successfully"}), 200


@profile_bp.route('/notifications', methods=['GET'], strict_slashes=False)
@jwt_required()
def get_notifications():
    """Get user notifications."""
    user = User.query.get_or_404(get_jwt_identity())

    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)

    notifications = user.notifications.order_by(
        Notification.read_at.is_(None).desc(),
        Notification.created_at.desc()
    ).paginate(page=page, per_page=per_page)

    return jsonify({
        "notifications": [{
            "id": n.id,
            "title": n.title,
            "message": n.message,
            "type": n.type,
            "category": n.category,
            "created_at": n.created_at.isoformat(),
            "read_at": n.read_at.isoformat() if n.read_at else None,
            "meta_data": n.meta_data
        } for n in notifications.items],
        "pagination": {
            "page": notifications.page,
            "per_page": notifications.per_page,
            "total": notifications.total,
            "pages": notifications.pages
        }
    }), 200


@profile_bp.route('/notifications/unread', methods=['GET'], strict_slashes=False)
@jwt_required()
def get_unread_notifications_count():
    """Get count of unread notifications."""
    user = User.query.get_or_404(get_jwt_identity())
    return jsonify({
        "unread_count": user.unread_notifications_count
    }), 200


@profile_bp.route('/notifications/read', methods=['POST'], strict_slashes=False)
@jwt_required()
def mark_notifications_read():
    """Mark notifications as read."""
    try:
        user = User.query.get_or_404(get_jwt_identity())

        # Get and validate notification_ids
        data = request.get_json()
        if data is None:
            return jsonify({"error": "No JSON data provided"}), 400

        notification_ids = data.get('notification_ids')
        if notification_ids is not None and not isinstance(notification_ids, list):
            return jsonify({"error": "notification_ids must be a list of integers"}), 400

        # If notification_ids provided, validate they are integers
        if notification_ids:
            if not all(isinstance(nid, int) for nid in notification_ids):
                return jsonify({"error": "All notification IDs must be integers"}), 400

            # Verify all notifications belong to the user
            invalid_ids = []
            for nid in notification_ids:
                if not user.notifications.filter_by(id=nid).first():
                    invalid_ids.append(nid)
            if invalid_ids:
                return jsonify({"error": f"Invalid notification IDs: {invalid_ids}"}), 400

        user.mark_notifications_as_read(notification_ids)

        return jsonify({
            "message": "Notifications marked as read",
            "unread_count": user.unread_notifications_count
        }), 200

    except Exception as e:
        current_app.logger.error(
            f"Error marking notifications as read: {str(e)}")
        db.session.rollback()
        return jsonify({"error": "Failed to mark notifications as read"}), 500


@profile_bp.route('/deleted', methods=['GET'], strict_slashes=False)
@jwt_required()
def get_deleted_items():
    """Get user's deleted templates and SMTP configurations."""
    user = User.query.get_or_404(get_jwt_identity())

    # Get deleted templates
    deleted_templates = user.templates.filter(
        Template.deleted_at.is_not(None)
    ).order_by(Template.deleted_at.desc()).all()

    # Get deleted SMTP configs
    deleted_smtp_configs = user.smtp_configs.filter(
        SMTPConfiguration.is_active.is_(False)
    ).order_by(SMTPConfiguration.updated_at.desc()).all()

    return jsonify({
        "templates": [{
            "id": t.id,
            "name": t.name,
            "deleted_at": t.deleted_at.isoformat(),
            "category": t.category
        } for t in deleted_templates],
        "smtp_configs": [{
            "id": c.id,
            "name": c.name,
            "host": c.host,
            "updated_at": c.updated_at.isoformat()
        } for c in deleted_smtp_configs]
    }), 200


@profile_bp.route('/restore/template/<int:template_id>', methods=['POST'], strict_slashes=False)
@jwt_required()
def restore_template(template_id):
    """Restore a deleted template."""
    success, error = UserService.restore_template(
        template_id=template_id,
        user_id=get_jwt_identity()
    )

    if not success:
        return jsonify({"error": error}), 400

    return jsonify({
        "message": "Template restored successfully"
    }), 200


@profile_bp.route('/restore/smtp/<int:config_id>', methods=['POST'])
@jwt_required()
def restore_smtp_config(config_id):
    """Restore a deleted SMTP configuration."""
    success, error = UserService.restore_smtp_config(
        config_id=config_id,
        user_id=get_jwt_identity()
    )

    if not success:
        return jsonify({"error": error}), 400

    return jsonify({
        "message": "SMTP configuration restored successfully"
    }), 200


@profile_bp.route('/template/<int:template_id>/permanent', methods=['DELETE'], strict_slashes=False)
@jwt_required()
def permanent_delete_template(template_id):
    """Permanently delete a template."""
    schema = PermanentDeleteSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400

    success, error = UserService.permanent_delete_template(
        template_id=template_id,
        user_id=get_jwt_identity(),
        confirmation_text=data['confirmation_text']
    )

    if not success:
        return jsonify({"error": error}), 400

    return jsonify({
        "message": "Template permanently deleted"
    }), 200


@profile_bp.route('/smtp/<int:config_id>/permanent', methods=['DELETE'])
@jwt_required()
def permanent_delete_smtp_config(config_id):
    """Permanently delete an SMTP configuration."""
    schema = PermanentDeleteSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400

    success, error = UserService.permanent_delete_smtp_config(
        config_id=config_id,
        user_id=get_jwt_identity(),
        confirmation_text=data['confirmation_text']
    )

    if not success:
        return jsonify({"error": error}), 400

    return jsonify({
        "message": "SMTP configuration permanently deleted"
    }), 200


@profile_bp.route('/templates/permanent-delete-all', methods=['DELETE'])
@jwt_required()
def permanent_delete_all_templates():
    """Permanently delete all soft-deleted templates."""
    schema = PermanentDeleteSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400

    success, error = UserService.permanent_delete_all_templates(
        user_id=get_jwt_identity(),
        confirmation_text=data['confirmation_text']
    )

    if not success:
        return jsonify({"error": error}), 400

    return jsonify({
        "message": "All deleted templates have been permanently removed"
    }), 200



@profile_bp.route('/smtps/permanent-delete-all', methods=['DELETE'])
@jwt_required()
def permanent_delete_all_smtp_configs():
    """Permanently delete all soft-deleted SMTP configurations."""
    schema = PermanentDeleteSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400

    success, error = UserService.permanent_delete_all_smtp_configs(
        user_id=get_jwt_identity(),
        confirmation_text=data['confirmation_text']
    )

    if not success:
        return jsonify({"error": error}), 400

    return jsonify({
        "message": "All deleted SMTP configurations have been permanently removed"
    }), 200
