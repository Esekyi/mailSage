from app.models.base import BaseModel
from app.extensions import db
from app.utils.db import JSONBType


class Notification(BaseModel):
    __tablename__ = 'notifications'

    user_id = db.Column(db.Integer, db.ForeignKey(
        'users.id', ondelete='CASCADE'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    # 'info', 'warning', 'success', 'error'
    type = db.Column(db.String(50), nullable=False)
    # 'system', 'template', 'smtp', etc.
    category = db.Column(db.String(50), nullable=False)
    read_at = db.Column(db.DateTime(timezone=True), nullable=True)
    meta_data = db.Column(JSONBType, default=dict)

    __table_args__ = (
        db.Index('idx_user_unread', user_id, read_at.is_(None)),
    )


class UserPreferences(BaseModel):
    """User preferences including notification settings."""
    __tablename__ = 'user_preferences'

    user_id = db.Column(db.Integer, db.ForeignKey(
        'users.id', ondelete='CASCADE'), nullable=False, unique=True)
    email_notifications = db.Column(JSONBType, default={
        'system_updates': True,
        'security_alerts': True,
        'quota_alerts': True,
        'template_changes': True,
        'smtp_changes': True,
        'delivery_status': True
    })
    in_app_notifications = db.Column(JSONBType, default={
        'system_updates': True,
        'security_alerts': True,
        'quota_alerts': True,
        'template_changes': True,
        'smtp_changes': True,
        'delivery_status': True
    })
    timezone = db.Column(db.String(50), default='UTC')
    theme = db.Column(db.String(20), default='light')  # 'light' or 'dark'
    preferences = db.Column(JSONBType, default={
        # security
        'login_alerts': True,
        'failed_attempt_alerts': True,
        'two_factor_auth': False,

        # Usage
        'quota_alerts': True,
        'usage_reports': True,
        'rate_limit_alerts': True,

        # Templates
        'template_versioning': True,
        'template_autosave': True,
        'template_change_alerts': True,

        # SMTP
        'smtp_failure_alerts': True,
        'smtp_performance_alerts': True,
        'delivery_status_alerts': True,

        # Marketing
        'marketing_emails': False,
        'product_updates': True,
        'maintenance_alerts': True
    })  # For any additional preferences

    def update_preferences(self, new_preferences: dict) -> None:
        """Update user preferences."""
        # Create a new dictionary with updated values to force SQLAlchemy to detect the change
        updated_prefs = dict(self.preferences)
        updated_prefs.update(new_preferences)
        self.preferences = updated_prefs

    def update_notifications(self, notification_type: str,
                             settings: dict) -> None:
        """Update notification settings."""
        if notification_type == 'email':
            # Create a new dictionary with updated values
            updated_settings = dict(self.email_notifications)
            updated_settings.update(settings)
            self.email_notifications = updated_settings
        elif notification_type == 'in_app':
            # Create a new dictionary with updated values
            updated_settings = dict(self.in_app_notifications)
            updated_settings.update(settings)
            self.in_app_notifications = updated_settings
