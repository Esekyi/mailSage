from typing import Dict, List, Optional, Tuple
from app.models import User, Template, SMTPConfiguration, Notification
from app.extensions import db
from datetime import datetime, timezone
from sqlalchemy.exc import SQLAlchemyError
from flask import current_app
from app.utils.roles import ROLE_CONFIGURATIONS, ResourceLimit


class UserService:
    @staticmethod
    def update_profile(user_id: int, data: Dict) -> Tuple[bool, Optional[str]]:
        """Update user profile information."""
        try:
            user = User.query.get(user_id)
            if not user:
                return False, "User not found"

            # Email can only be changed by admin
            if 'email' in data:
                return False, "Email can only be changed by an administrator"

            updatable_fields = ['name', 'phone', 'company', 'job_title', 'bio']
            for field in updatable_fields:
                if field in data:
                    setattr(user, field, data[field])

            db.session.commit()

            # Add notification
            user.add_notification(
                title="Profile Updated",
                message=f"Profile has been updated",
                type="info",
                category="profile",
                meta_data={"profile_id": user.id}
            )

            return True, None

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating profile: {str(e)}")
            return False, "Failed to update profile"

    @staticmethod
    def update_preferences(user_id: int, preferences: Dict) -> Tuple[bool, Optional[str]]:
        """Update user preferences."""
        try:
            user = User.query.get(user_id)
            if not user:
                return False, "User not found"

            user_prefs = user.get_preferences()

            if 'email_notifications' in preferences:
                user_prefs.email_notifications.update(
                    preferences['email_notifications'])

            if 'in_app_notifications' in preferences:
                user_prefs.in_app_notifications.update(
                    preferences['in_app_notifications'])

            if 'timezone' in preferences:
                user_prefs.timezone = preferences['timezone']

            if 'theme' in preferences:
                user_prefs.theme = preferences['theme']

            db.session.commit()

            # Add notification
            user.add_notification(
                title="Preferences Updated",
                message=f"Preferences have been updated",
                type="success",
                category="preferences",
                meta_data={"preferences": preferences}
            )

            return True, None

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating preferences: {str(e)}")
            return False, "Failed to update preferences"

    @staticmethod
    def restore_template(template_id: int, user_id: int) -> Tuple[bool, Optional[str]]:
        """Restore a soft-deleted template."""
        try:
            template = Template.query.filter_by(
                id=template_id,
                user_id=user_id
            ).first()

            if not template:
                return False, "Template not found"

            if not template.deleted_at:
                return False, "Template is not deleted"

            # Check if restoring would exceed limits
            current_templates = Template.query.filter_by(
                user_id=user_id,
                is_active=True,
                deleted_at=None
            ).count()

            user = User.query.get(user_id)
            template_limit = ROLE_CONFIGURATIONS[user.role]['limits'][
                ResourceLimit.TEMPLATES.value]

            if template_limit != -1 and current_templates >= template_limit:
                return False, f"Cannot restore template: would exceed limit of {template_limit}"

            template.deleted_at = None
            template.deleted_by = None
            template.is_active = True

            # Add notification
            user.add_notification(
                title="Template Restored",
                message=f"Template '{template.name}' has been restored",
                type="info",
                category="template",
                meta_data={"template_id": template.id}
            )

            db.session.commit()
            return True, None

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error restoring template: {str(e)}")
            return False, "Failed to restore template"

    @staticmethod
    def restore_smtp_config(config_id: int, user_id: int) -> Tuple[bool, Optional[str]]:
        """Restore a soft-deleted SMTP configuration."""
        try:
            config = SMTPConfiguration.query.filter_by(
                id=config_id,
                user_id=user_id
            ).first()

            if not config:
                return False, "SMTP configuration not found"

            if config.is_active:
                return False, "SMTP configuration is not deleted"

            # Check if restoring would exceed limits
            current_configs = SMTPConfiguration.query.filter_by(
                user_id=user_id,
                is_active=True
            ).count()

            user = User.query.get(user_id)
            smtp_limit = ROLE_CONFIGURATIONS[user.role]['limits'][
                ResourceLimit.SMTPCONFIGS.value]

            if smtp_limit != -1 and current_configs >= smtp_limit:
                return False, f"Cannot restore SMTP config: would exceed limit of {smtp_limit}"

            config.is_active = True

            # Add notification
            user.add_notification(
                title="SMTP Configuration Restored",
                message=f"SMTP configuration '{
                    config.name}' has been restored",
                type="info",
                category="smtp",
                meta_data={"config_id": config.id}
            )

            db.session.commit()
            return True, None

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error restoring SMTP config: {str(e)}")
            return False, "Failed to restore SMTP configuration"

    @staticmethod
    def permanent_delete_template(template_id: int, user_id: int, confirmation_text: str) -> Tuple[bool, Optional[str]]:
        """Permanently delete a template after confirmation."""
        try:
            if confirmation_text != "PERMANENT DELETE":
                return False, "Invalid confirmation text. Please type 'PERMANENT DELETE' to confirm."

            template = Template.query.filter_by(
                id=template_id,
                user_id=user_id
                # Must be soft-deleted first
            ).filter(Template.deleted_at.is_not(None)).first()

            if not template:
                return False, "Template not found or not in deleted state"

            # If this is a base template, get all its versions
            templates_to_delete = [template]
            if template.base_template_id is None:
                versions = Template.query.filter_by(
                    base_template_id=template.id
                ).all()
                templates_to_delete.extend(versions)

            # Add notification before deletion
            user = User.query.get(user_id)
            user.add_notification(
                title="Template Permanently Deleted",
                message=f"Template '{
                    template.name}' has been permanently deleted",
                type="warning",
                category="template",
                meta_data={
                    "template_name": template.name,
                    "deleted_versions": len(templates_to_delete) - 1
                }
            )

            # Perform deletion
            for t in templates_to_delete:
                db.session.delete(t)

            db.session.commit()
            return True, None

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(
                f"Error permanently deleting template: {str(e)}")
            return False, "Failed to delete template permanently"

    @staticmethod
    def permanent_delete_smtp_config(config_id: int, user_id: int, confirmation_text: str) -> Tuple[bool, Optional[str]]:
        """Permanently delete an SMTP configuration after confirmation."""
        try:
            if confirmation_text != "PERMANENT DELETE":
                return False, "Invalid confirmation text. Please type 'PERMANENT DELETE' to confirm."

            config = SMTPConfiguration.query.filter_by(
                id=config_id,
                user_id=user_id,
                is_active=False  # Must be deactivated first
            ).first()

            if not config:
                return False, "SMTP configuration not found or not in deleted state"

            # Add notification before deletion
            user = User.query.get(user_id)
            user.add_notification(
                title="SMTP Configuration Permanently Deleted",
                message=f"SMTP configuration '{
                    config.name}' has been permanently deleted",
                type="warning",
                category="smtp",
                meta_data={
                    "config_name": config.name,
                    "config_host": config.host
                }
            )

            # Perform deletion
            db.session.delete(config)
            db.session.commit()
            return True, None

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(
                f"Error permanently deleting SMTP config: {str(e)}")
            return False, "Failed to delete SMTP configuration permanently"

    @staticmethod
    def permanent_delete_all_templates(user_id: int, confirmation_text: str) -> Tuple[bool, Optional[str]]:
        """Permanently delete all soft-deleted templates."""
        try:
            if confirmation_text != "PERMANENT DELETE ALL TEMPLATES":
                return False, "Invalid confirmation text. Please type 'PERMANENT DELETE ALL TEMPLATES' to confirm."

            deleted_templates = Template.query.filter_by(
                user_id=user_id
            ).filter(Template.deleted_at.is_not(None)).all()

            if not deleted_templates:
                return False, "No deleted templates found"

            count = len(deleted_templates)

            # Add notification before deletion
            user = User.query.get(user_id)
            user.add_notification(
                title="All Deleted Templates Removed",
                message=f"{
                    count} deleted templates have been permanently removed",
                type="critical",
                category="template",
                meta_data={"templates_count": count}
            )

            # Perform deletion
            for template in deleted_templates:
                db.session.delete(template)

            db.session.commit()
            return True, None

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error deleting all templates: {str(e)}")
            return False, "Failed to delete all templates permanently"

    @staticmethod
    def permanent_delete_all_smtp_configs(user_id: int, confirmation_text: str) -> Tuple[bool, Optional[str]]:
        """Permanently delete all soft-deleted SMTP configurations."""
        try:
            if confirmation_text != "PERMANENT DELETE ALL SMTP CONFIGS":
                return False, "Invalid confirmation text. Please type 'PERMANENT DELETE ALL SMTP CONFIGS' to confirm."

            deleted_configs = SMTPConfiguration.query.filter_by(
                user_id=user_id,
                is_active=False
            ).all()

            if not deleted_configs:
                return False, "No deleted SMTP configurations found"

            count = len(deleted_configs)

            # Add notification before deletion
            user = User.query.get(user_id)
            user.add_notification(
                title="All Deleted SMTP Configurations Removed",
                message=f"{
                    count} deleted SMTP configurations have been permanently removed",
                type="critical",
                category="smtp",
                meta_data={"configs_count": count}
            )

            # Perform deletion
            for config in deleted_configs:
                db.session.delete(config)

            db.session.commit()
            return True, None

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(
                f"Error deleting all SMTP configs: {str(e)}")
            return False, "Failed to delete all SMTP configurations permanently"
