from flask import current_app
from sqlalchemy import func, or_
from app.models import Template


class TemplateSearchService:
    @staticmethod
    def search_templates(query: str, user_id: int):
        """Search templates with database-appropriate search strategy."""
        if current_app.config['SQLALCHEMY_DATABASE_URI'
                              ].startswith('postgresql'):
            # Use PostgreSQL full-text search
            return Template.query.filter(
                Template.user_id == user_id,
                Template.search_vector.match(query)
            ).all()
        else:
            # Fallback to LIKE search for SQLite
            search_term = f"%{query}%"
            return Template.query.filter(
                Template.user_id == user_id,
                or_(
                    Template.name.ilike(search_term),
                    Template.description.ilike(search_term),
                    Template.html_content.ilike(search_term)
                )
            ).all()

    @staticmethod
    def update_search_vector(template: Template) -> None:
        """Update the search vector for a template."""
        search_text = ' '.join(filter(None, [
            template.name,
            template.description,
            template.html_content
        ]))

        if current_app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgresql'):
            # Use PostgreSQL full-text search
            template.search_vector = func.to_tsvector('english', search_text)
        else:
            # For other databases, store search text directly
            template.search_vector = search_text
