from typing import Dict, Optional
from sqlalchemy.exc import SQLAlchemyError
from app.extensions import db
from app.models.template import Template
from app.utils.logging import logger
from sqlalchemy import func


class TemplateService:
    @staticmethod
    def create_new_version(template: Template, html_content: str,
                           variables: Optional[Dict] = None
                           ) -> Optional[Template]:
        """Create a new version of a template with optimistic locking."""
        try:
            with db.session.begin_nested():
                current_version = db.session.query(
                    func.max(Template.version)).filter(
                    Template.user_id == template.user_id,
                    Template.name == template.name
                ).scalar()

                if current_version != template.version:
                    raise ValueError(
                        "Template was modified. Please refresh and try again.")

                template.is_active = False
                new_template = Template(
                    user_id=template.user_id,
                    name=template.name,
                    description=template.description,
                    html_content=html_content,
                    variables=variables or template.variables,
                    version=template.version + 1
                )
                db.session.add(new_template)
                db.session.commit()
                return new_template
        except SQLAlchemyError as e:
            logger.error(f"Error creating template version: {str(e)}")
            db.session.rollback()
            return None
