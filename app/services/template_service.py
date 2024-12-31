from typing import Dict, Optional, Tuple, List, Set, Any
from sqlalchemy.exc import SQLAlchemyError
from app.extensions import db
from app.models.template import Template, TemplateStats
from app.utils.logging import logger
from datetime import datetime, timezone
from bs4 import BeautifulSoup
import re


class TemplateService:
    @staticmethod
    def validate_template_html(html_content: str) -> Tuple[bool, Optional[str]]:
        """
        Validate HTML template structure.

        Args:
            html_content: HTML content to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Parse Html Body
            soup = BeautifulSoup(html_content, 'html.parser')

            # Check for required email elements
            if not soup.find('body'):
                return False, "Template must contain a body tag"

            return True, None

        except Exception as e:
            return False, f"Invalid HTML: {str(e)}"

    @staticmethod
    def create_template(user_id: int, name: str, html_content: str,
                        description: Optional[str] = None) -> Tuple[Optional[Template], Optional[str]]:
        """
        Create a new template.

        Args:
            user_id: ID of the user creating the template
            name: Template name
            html_content: HTML content of the template
            description: Optional template description

        Returns:
            Tuple of (Template object or None, error message or None)
        """
        try:
            # Validate HTML first
            is_valid, error = TemplateService.validate_template_html(
                html_content)
            if not is_valid:
                return None, error

            template = Template(
                user_id=user_id,
                name=name,
                html_content=html_content,
                description=description,
                version=1,
                is_active=True
            )

            db.session.add(template)
            db.session.commit()

            return template, None

        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error creating template: {str(e)}")
            return None, "Failed to create template"

    @staticmethod
    def update_template(template_id: int, user_id: int,
                        html_content: str,
                        change_summary: Optional[str] = None,
                        name: Optional[str] = None,
                        description: Optional[str] = None) -> Tuple[Optional[Template], Optional[str]]:
        """
        Update a template by creating a new version.
        """
        try:
            # Validate HTML first
            is_valid, error = TemplateService.validate_template_html(
                html_content)
            if not is_valid:
                return None, error

            current_template = Template.query.filter_by(
                id=template_id,
                user_id=user_id,
                is_active=True
            ).first()

            if not current_template:
                return None, "Template not found"

            # Create new version
            new_version = current_template.create_new_version(
                html_content=html_content,
                change_summary=change_summary
            )

            # Update other fields if provided
            if name:
                new_version.name = name
            if description:
                new_version.description = description

            db.session.add(new_version)
            db.session.commit()

            return new_version, None

        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error updating template: {str(e)}")
            return None, "Failed to update template"

    @staticmethod
    def preview_template_content(html_content: str,
                                 variables: Optional[Dict] = None
                                 ) -> Tuple[Optional[str], Optional[str]]:
        """
        Generate a preview with optional test data.

        Args:
            html_content: HTML content to preview
            variables: Optional dictionary of variables to replace

        Returns:
            Tuple of (preview_html, error_message)
        """
        try:
            # Validate HTML first
            is_valid, error = TemplateService.validate_template_html(
                html_content)
            if not is_valid:
                return None, error

            # Replace variables with test data
            preview = html_content
            if variables:
                for var_name, value in variables.items():
                    placeholder = f"{{{{ {var_name} }}}}"
                    preview = preview.replace(
                        placeholder,
                        str(value))

            return preview, None

        except Exception as e:
            return None, f"Preview generation failed: {str(e)}"

    @staticmethod
    def extract_template_variables(html_content: str) -> Set[str]:
        """Extract all variables from template HTML content."""
        return set(re.findall(r'{{\s*(\w+)\s*}}', html_content))

    @staticmethod
    def get_template(template_id: int, user_id: int) -> Optional[Template]:
        """Get a specific template."""

        return Template.query.filter_by(
            id=template_id,
            user_id=user_id,
            is_active=True,
            deleted_at=None
        ).first()

    @staticmethod
    def get_templates(user_id: int, search_query: Optional[str] = None) -> List[Template]:
        """Get all active templates for a user, optionally filtered by search."""
        query = Template.query.filter_by(
            user_id=user_id,
            is_active=True,
            deleted_at=None
        )

        if search_query:
            query = query.filter(
                Template.search_vector.match(search_query)
            )

        return query.all()

    @staticmethod
    def delete_template(template_id: int, user_id: int) -> Tuple[bool, Optional[str]]:
        """Soft delete a template and all its versions."""
        try:
            logger.info(f"Attempting to delete template {
                        template_id} for user {user_id}")

            template = Template.query.filter_by(
                id=template_id,
                user_id=user_id,
                deleted_at=None
            ).first()

            if not template:
                logger.warning(
                    f"Template {template_id} not found or already deleted")
                return False, "Template not found"

            now = datetime.now(timezone.utc)

            # Start with the base template
            templates_to_delete = [template]

            # Get all versions if this is a base template
            if template.base_template_id:
                logger.debug(
                    f"Finding versions for base template {template_id}")
                versions = Template.query.filter_by(
                    base_template_id=template_id,
                    deleted_at=None
                ).all()
                templates_to_delete.extend(versions)

            # Soft delete all versions
            for t in templates_to_delete:
                logger.debug(f"Soft deleting template {t.id}")
                t.deleted_at = now
                t.deleted_by = user_id
                t.is_active = False

            # Log the deletion in template history if you have that
            t.meta_data = {
                **(t.meta_data or {}),
                'deleted_at': now.isoformat(),
                'deleted_by': user_id
            }

            db.session.commit()
            logger.info(f"Successfully deleted template {template_id} and {
                        len(templates_to_delete)-1} versions")
            return True, None

        except SQLAlchemyError as e:
            db.session.rollback()
            error_msg = str(e)
            logger.error(f"Database error deleting template {
                template_id}: {error_msg}")
            return False, "Failed to delete template"

        except Exception as e:
            db.session.rollback()
            error_msg = str(e)
            logger.error(f"Unexpected error deleting template {
                template_id}: {error_msg}")
            return False, "An unexpected error occurred"

    @staticmethod
    def publish_template(template_id: int, user_id: int) -> Tuple[bool, Optional[str]]:
        """Publish a template version."""
        try:
            template = Template.query.filter_by(
                id=template_id,
                user_id=user_id,
                is_active=True
            ).first()

            if not template:
                return False, "Template not found"

            template.publish()
            db.session.commit()
            return True, None

        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error publishing template: {str(e)}")
            return False, "Failed to publish template"

    @staticmethod
    def get_template_versions(base_template_id: int, user_id: int) -> List[Template]:
        """Get all versions of a template."""
        return Template.query.filter_by(
            base_template_id=base_template_id,
            user_id=user_id,
            deleted_at=None
        ).order_by(Template.version.desc()).all()

    @staticmethod
    def get_templates_by_category(user_id: int, category: str) -> List[Template]:
        """Get templates filtered by category."""
        return Template.query.filter_by(
            user_id=user_id,
            category=category,
            is_active=True,
            deleted_at=None
        ).all()

    @staticmethod
    def get_user_categories(user_id: int) -> List[str]:
        """Get all unique categories used by a user."""
        return db.session.query(Template.category).filter_by(
            user_id=user_id,
            deleted_at=None
        ).distinct().all()

    @staticmethod
    def get_template_stats(template_id: int, user_id: int) -> Optional[Dict]:
        """Get usage statistics for a template."""
        stats = TemplateStats.query.join(Template).filter(
            Template.id == template_id,
            Template.user_id == user_id
        ).first()

        if not stats:
            return None

        return {
            'total_sends': stats.total_sends,
            'successful_sends': stats.successful_sends,
            'failed_sends': stats.failed_sends,
            'success_rate': stats.success_rate,
            'last_used': stats.last_used_at.isoformat() if stats.last_used_at else None
        }

    @staticmethod
    def preview_saved_template(
        template_id: int,
        user_id: int,
        test_variables: Optional[Dict[str, Any]] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """Preview an existing template from the database."""

        template = TemplateService.get_template(template_id, user_id)
        if not template:
            return None, "Template not found"

        return TemplateService.preview_template_content(
            template.html_content,
            test_variables
        )
