from typing import Dict, Optional, Tuple, List, Set, Any
from sqlalchemy.exc import SQLAlchemyError
from app.extensions import db
from app.models import Template, TemplateStats, User, TemplateVersion
from app.services.search_service import TemplateSearchService
from app.utils.logging import logger
from datetime import datetime, timezone
from bs4 import BeautifulSoup
import re
from jinja2 import Environment, exceptions
from app.extensions import redis_client


class TemplateRenderService:
    def __init__(self):
        self.env = Environment(autoescape=True)
        self.cache_timeout = 3600  # 1 hour

    def _get_cache_key(self, template_id: int, variables: Dict[str, Any]) -> str:
        """Generate cache key for template rendering."""
        variables_hash = hash(frozenset(variables.items()))
        return f"template_render:{template_id}:{variables_hash}"

    def sanitize_html(self, html_content: str) -> str:
        """Sanitize HTML content to prevent XSS and ensure email client compatibility."""
        soup = BeautifulSoup(html_content, 'html.parser')

        # Remove potentially dangerous tags and attributes
        for tag in soup.find_all():
            if tag.name in ['script', 'iframe', 'object', 'embed']:
                tag.decompose()

            # Remove on* attributes (event handlers)
            for attr in list(tag.attrs):
                if attr.startswith('on'):
                    del tag[attr]

        return str(soup)

    def get_cached_render(self, template_id: int, variables: Dict[str, Any]) -> Optional[str]:
        """Get cached rendered template if available."""
        cache_key = self._get_cache_key(template_id, variables)
        return redis_client.get(cache_key)

    def cache_render(self, template_id: int, variables: Dict[str, Any], rendered: str):
        """Cache rendered template."""
        cache_key = self._get_cache_key(template_id, variables)
        redis_client.setex(cache_key, self.cache_timeout, rendered)

    def validate_template_variables(self, template: Template, variables: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate that all required variables are provided."""
        try:
            # Get required variables from template
            required_vars = template.required_variables

            # Check for missing variables
            missing_vars = required_vars - set(variables.keys())
            if missing_vars:
                return False, f"Missing required variables: {', '.join(missing_vars)}"

            return True, None

        except Exception as e:
            logger.error(f"Template variable validation error: {str(e)}")
            return False, str(e)

    def render_template(self,
                        template: Template,
                        variables: Dict[str, Any],
                        use_cache: bool = True) -> Tuple[str, Optional[str]]:
        """
        Render template with provided variables.

        Args:
            template: Template model instance
            variables: Dictionary of variables to render
            use_cache: Whether to use template caching

        Returns:
            Tuple of (rendered_content, error_message)
        """
        try:
            # Check cache first if enabled
            if use_cache:
                cached = self.get_cached_render(template.id, variables)
                if cached:
                    return cached, None

            # Validate variables
            is_valid, error = self.validate_template_variables(
                template, variables)
            if not is_valid:
                raise ValueError(error)

            # Render template
            template_obj = self.env.from_string(template.html_content)
            rendered_html = template_obj.render(**variables)

            # Sanitize output
            rendered = self.sanitize_html(rendered_html)

            # Cache result if caching is enabled
            if use_cache:
                self.cache_render(template.id, variables, rendered)

            return rendered, None

        except exceptions.TemplateError as e:
            error_msg = f"Template rendering error: {str(e)}"
            logger.error(error_msg)
            return None, error_msg
        except Exception as e:
            error_msg = f"Unexpected error rendering template: {str(e)}"
            logger.error(error_msg)
            return None, error_msg


class TemplateService:
    def __init__(self):
        self.renderer = TemplateRenderService()

    def render_template_for_send(self, template_id: int, user_id: int, variables: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
        """
        Render a template for email sending with variable validation and caching.

        Returns:
            Tuple of (rendered_content, error_message)
        """
        template = self.get_template(template_id, user_id)
        if not template:
            return None, "Template not found"

        return self.renderer.render_template(template, variables)


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
                        description: Optional[str] = None,
                        tags: Optional[List[str]] = None) -> Tuple[Optional[Template], Optional[str]]:
        """
        Create a new template.

        Args:
            user_id: ID of the user creating the template
            name: Template name
            html_content: HTML content of the template
            description: Optional template description
            tags: Optional list of tags

        Returns:
            Tuple of (Template object or None, error message or None)
        """
        try:
            # Validate HTML first
            is_valid, error = TemplateService.validate_template_html(
                html_content)
            if not is_valid:
                return None, error

            # Create the template with initial version
            template = Template(
                user_id=user_id,
                name=name,
                html_content=html_content,
                tags=tags,
                description=description,
                version=1,  # Initial version is 1
                is_active=True,
                meta_data={
                    'initial_version': True,
                    'created_at': datetime.now(timezone.utc).isoformat()
                }
            )

            # Update search vector
            TemplateSearchService.update_search_vector(template)
            db.session.add(template)
            db.session.commit()  # Commit to get template.id

            # Add notification
            user = User.query.get_or_404(user_id)
            user.add_notification(
                title="Template Created",
                message=f"Template '{template.name}' has been created",
                type="info",
                category="template",
                meta_data={
                    "template_id": template.id,
                    "version": template.version
                }
            )

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
                        tags: Optional[List[str]] = None,
                        description: Optional[str] = None) -> Tuple[Optional[Template], Optional[str]]:
        """Update an existing template by updating the current version and storing history."""
        try:
            # Validate HTML first
            is_valid, error = TemplateService.validate_template_html(
                html_content)
            if not is_valid:
                return None, error

            template = Template.query.filter_by(
                id=template_id,
                user_id=user_id,
                is_active=True
            ).first()

            if not template:
                return None, "Template not found"

            # Store the current version in template_versions
            current_version = TemplateVersion(
                template_id=template_id,
                version=template.version,  # Archive current version number
                html_content=template.html_content,
                change_summary=change_summary,
                meta_data={
                    "name": template.name,
                    "description": template.description,
                    "archived_at": datetime.now(timezone.utc).isoformat()
                },
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            db.session.add(current_version)

            # Update the current template
            if name:
                template.name = name
            if description:
                template.description = description
            if tags:
                template.tags = tags

            template.html_content = html_content
            template.version += 1  # Simply increment version by 1
            template.updated_at = datetime.now(timezone.utc)
            template.meta_data = {
                **(template.meta_data or {}),
                'change_summary': change_summary,
                'previous_version': template.version - 1
            }

            # Update search vector
            TemplateSearchService.update_search_vector(template)

            # Add notification
            user = User.query.get_or_404(user_id)
            user.add_notification(
                title="Template Updated",
                message=f"Template '{template.name}' has been updated to version {
                    template.version}",
                type="success",
                category="template",
                meta_data={
                    "template_id": template.id,
                    "version": template.version,
                    "previous_version": template.version - 1
                }
            )

            db.session.commit()
            return template, None

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
        """Soft delete a template and its versions."""
        try:
            logger.info(f"Soft deleting template {
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

            # Soft delete the template
            template.deleted_at = now
            template.deleted_by = user_id
            template.is_active = False

            # Update metadata
            template.meta_data = {
                **(template.meta_data or {}),
                'deleted_at': now.isoformat(),
                'deleted_by': user_id,
                'version_at_deletion': template.version
            }

            # Add notification
            user = User.query.get_or_404(user_id)
            user.add_notification(
                title="Template Deleted",
                message=f"Template '{template.name}' has been deleted",
                type="critical",
                category="template",
                meta_data={
                    "template_id": template.id,
                    "version": template.version
                }
            )

            db.session.commit()
            logger.info(f"Successfully soft deleted template {
                        template_id} with {len(template.versions)} versions")
            return True, None

        except SQLAlchemyError as e:
            db.session.rollback()
            error_msg = str(e)
            logger.error(f"Database error soft deleting template {
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

    @staticmethod
    def get_template_version(template_id: int, version: int, user_id: int) -> Optional[TemplateVersion]:
        """Get a specific version of a template."""
        template = Template.query.filter_by(
            id=template_id,
            user_id=user_id,
            is_active=True
        ).first()

        if not template:
            return None

        return TemplateVersion.query.filter_by(
            template_id=template_id,
            version=version
        ).first()

    @staticmethod
    def revert_to_version(template_id: int, version: int, user_id: int) -> Tuple[Optional[Template], Optional[str]]:
        """Revert a template to a specific version."""
        try:
            template = Template.query.filter_by(
                id=template_id,
                user_id=user_id,
                is_active=True
            ).first()

            if not template:
                return None, "Template not found"

            # Don't revert if already at the requested version
            if template.version == version:
                return None, "Template is already at this version"

            target_version = TemplateVersion.query.filter_by(
                template_id=template_id,
                version=version
            ).first()

            if not target_version:
                return None, f"Version {version} not found"

            # Get the next version number for archiving
            next_version = db.session.query(db.func.max(TemplateVersion.version)).filter(
                TemplateVersion.template_id == template_id
            ).scalar() or 0
            next_version += 1

            # Archive current version with the next version number
            current_version = TemplateVersion(
                template_id=template_id,
                version=next_version,
                html_content=template.html_content,
                change_summary=f"Auto-archived before reverting to version {
                    version}",
                meta_data={
                    "name": template.name,
                    "description": template.description,
                    "archived_at": datetime.now(timezone.utc).isoformat()
                },
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            db.session.add(current_version)

            # Update template with target version content
            template.html_content = target_version.html_content
            template.version = next_version + 1  # Set to next version after archive
            template.updated_at = datetime.now(timezone.utc)
            template.meta_data = {
                **(template.meta_data or {}),
                'reverted_from_version': version,
                'revert_date': datetime.now(timezone.utc).isoformat()
            }

            # Add notification
            user = User.query.get_or_404(user_id)
            user.add_notification(
                title="Template Reverted",
                message=f"Template '{
                    template.name}' has been reverted to version {version}",
                type="info",
                category="template",
                meta_data={
                    "template_id": template.id,
                    "current_version": template.version,
                    "reverted_from": version
                }
            )

            db.session.commit()
            return template, None

        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error reverting template: {str(e)}")
            return None, "Failed to revert template"

    @staticmethod
    def compare_versions(template_id: int, version1: int, version2: int, user_id: int) -> Tuple[Optional[Dict], Optional[str]]:
        """Compare two versions of a template."""
        try:
            template = Template.query.filter_by(
                id=template_id,
                user_id=user_id,
                is_active=True
            ).first()

            if not template:
                return None, "Template not found"

            # For version1, check if it's the current version
            if version1 == template.version:
                v1_content = template.html_content
                v1_created_at = template.updated_at or template.created_at
                v1_meta = template.meta_data
            else:
                v1 = TemplateVersion.query.filter_by(
                    template_id=template_id,
                    version=version1
                ).first()
                if not v1:
                    return None, f"Version {version1} not found"
                v1_content = v1.html_content
                v1_created_at = v1.created_at
                v1_meta = v1.meta_data

            # For version2, check if it's the current version
            if version2 == template.version:
                v2_content = template.html_content
                v2_created_at = template.updated_at or template.created_at
                v2_meta = template.meta_data
            else:
                v2 = TemplateVersion.query.filter_by(
                    template_id=template_id,
                    version=version2
                ).first()
                if not v2:
                    return None, f"Version {version2} not found"
                v2_content = v2.html_content
                v2_created_at = v2.created_at
                v2_meta = v2.meta_data

            # Compare the versions
            return {
                'version1': {
                    'version': version1,
                    'html_content': v1_content,
                    'created_at': v1_created_at.isoformat(),
                    'meta_data': v1_meta
                },
                'version2': {
                    'version': version2,
                    'html_content': v2_content,
                    'created_at': v2_created_at.isoformat(),
                    'meta_data': v2_meta
                },
                'template_name': template.name,
                'current_version': template.version
            }, None

        except SQLAlchemyError as e:
            logger.error(f"Error comparing versions: {str(e)}")
            return None, "Failed to compare versions"

    @staticmethod
    def get_available_versions(template_id: int, user_id: int) -> Tuple[List[Dict], Optional[str]]:
        """
        Get all available versions that can be compared.

        Returns:
            Tuple of (List of version info, error message if any)
        """
        try:
            template = Template.query.filter_by(
                id=template_id,
                user_id=user_id,
                is_active=True
            ).first()

            if not template:
                return [], "Template not found"

            # Get all archived versions
            archived_versions = TemplateVersion.query.filter_by(
                template_id=template_id
            ).order_by(TemplateVersion.version.asc()).all()

            versions = []

            # Add archived versions
            for version in archived_versions:
                versions.append({
                    'version': version.version,
                    'created_at': version.created_at.isoformat(),
                    'change_summary': version.change_summary,
                    'is_current': False
                })

            # Add current version
            versions.append({
                'version': template.version,
                'created_at': template.updated_at.isoformat() if template.updated_at else template.created_at.isoformat(),
                'change_summary': template.meta_data.get('change_summary') if template.meta_data else None,
                'is_current': True
            })

            return versions, None

        except SQLAlchemyError as e:
            logger.error(f"Error getting available versions: {str(e)}")
            return [], "Failed to get versions"
