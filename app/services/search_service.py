from sqlalchemy import or_
from app.models import Template
from typing import List
from sqlalchemy.sql.expression import cast
from sqlalchemy import String
from sqlalchemy.sql import func
from flask import current_app


class TemplateSearchService:
    @staticmethod
    def search_templates(query: str, user_id: int) -> List[Template]:
        """
        Search templates using full-text search with search vectors.

        Args:
            query: Search query string
            user_id: User ID to filter templates

        Returns:
            List of matching Template objects
        """
        # Clean and prepare the search query
        cleaned_query = ' & '.join(query.split())

        return Template.query.filter(
            Template.user_id == user_id,
            Template.is_active == True,
            Template.deleted_at == None,
            Template.search_vector.match(cleaned_query)
        ).order_by(
            func.ts_rank(Template.search_vector, func.to_tsquery(
                'english', cleaned_query)).desc()
        ).all()

    @staticmethod
    def search_templates_by_tag(tag: str, user_id: int) -> List[Template]:
        """
        Search templates by tag.

        Args:
            tag: Tag to search for
            user_id: User ID to filter templates

        Returns:
            List of matching Template objects
        """
        return Template.query.filter(
            Template.user_id == user_id,
            Template.is_active == True,
            Template.deleted_at == None,
            Template.tags.contains([tag])
        ).all()

    @staticmethod
    def search_templates_combined(query: str, tags: List[str], user_id: int) -> List[Template]:
        """
        Search templates using both full-text search and tags.

        Args:
            query: Search query string
            tags: List of tags to filter by
            user_id: User ID to filter templates

        Returns:
            List of matching Template objects
        """
        # Clean and prepare the search query
        cleaned_query = ' & '.join(query.split())

        base_query = Template.query.filter(
            Template.user_id == user_id,
            Template.is_active == True,
            Template.deleted_at == None
        )

        if query:
            base_query = base_query.filter(
                Template.search_vector.match(cleaned_query)
            )

        if tags:
            base_query = base_query.filter(
                Template.tags.overlap(tags)
            )

        return base_query.order_by(
            func.ts_rank(Template.search_vector, func.to_tsquery(
                'english', cleaned_query)).desc()
            if query else Template.updated_at.desc()
        ).all()

    @staticmethod
    def update_search_vector(template: Template) -> None:
        """
        Update the search vector for a template.

        Args:
            template: Template instance to update search vector for
        """
        try:
            # Combine all searchable fields with weights
            # A: name (highest weight)
            # B: description
            # C: html_content (lowest weight)
            # This ensures name matches appear first in search results
            search_vector = func.setweight(
                func.to_tsvector('english', template.name or ''), 'A')

            if template.description:
                search_vector = search_vector.op('||')(
                    func.setweight(func.to_tsvector(
                        'english', template.description), 'B')
                )

            if template.html_content:
                search_vector = search_vector.op('||')(
                    func.setweight(func.to_tsvector(
                        'english', template.html_content), 'C')
                )

            # Update the template's search vector
            template.search_vector = search_vector

        except Exception as e:
            current_app.logger.error(f"Error updating search vector: {str(e)}")
            # Don't raise the error, as this is a non-critical operation
            pass
