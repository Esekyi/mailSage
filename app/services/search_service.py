from typing import List
from sqlalchemy import func
from app.models import Template


class TemplateSearchService:
    @staticmethod
    def search_templates(query: str, user_id: int = None) -> List[Template]:
        """Search templates using full-text search."""
        search_query = Template.query.filter(
            Template.search_vector.match(query)
        )

        if user_id is not None:
            search_query = search_query.filter_by(user_id=user_id)

        return search_query.all()

    @staticmethod
    def update_search_vector(template: Template) -> None:
        """Update the search vector for a template."""
        search_text = ' '.join(filter(None, [
            template.name,
            template.description,
            template.html_content
        ]))

        template.search_vector = func.to_tsvector('english', search_text)
