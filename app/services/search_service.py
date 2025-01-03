from flask import current_app
from sqlalchemy import func, or_, text
from app.models import Template


class TemplateSearchService:
    @staticmethod
    def search_templates(query: str, user_id: int):
        """Search templates with database-appropriate search strategy."""
        base_query = Template.query.filter_by(
            user_id=user_id,
            is_active=True,
            deleted_at=None
        )

        if current_app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgresql'):
            # Process the search query to handle partial words
            if not query.strip():
                return base_query

            # Convert search terms to tsquery format with prefix matching
            terms = query.strip().split()
            processed_terms = []
            for term in terms:
                # Remove any special characters that might interfere with the query
                clean_term = ''.join(c for c in term if c.isalnum())
                if clean_term:
                    processed_terms.append(f"{clean_term}:*")

            if not processed_terms:
                return base_query

            processed_query = ' & '.join(processed_terms)

            # Use a single to_tsquery call
            return base_query.filter(
                Template.search_vector.op('@@')(
                    func.to_tsquery('english', processed_query)
                )
            )
        else:
            # Fallback to LIKE search for SQLite
            search_term = f"%{query}%"
            return base_query.filter(
                or_(
                    Template.name.ilike(search_term),
                    Template.description.ilike(search_term),
                    Template.html_content.ilike(search_term)
                )
            )

    @staticmethod
    def update_search_vector(template: Template) -> None:
        """Update the search vector for a template."""
        # Combine all searchable fields
        search_text = ' '.join(filter(None, [
            template.name,
            template.description,
            template.html_content
        ]))

        if current_app.config['SQLALCHEMY_DATABASE_URI'].startswith('postgresql'):
            # Use PostgreSQL full-text search with English dictionary
            template.search_vector = func.to_tsvector('english', search_text)
        else:
            # For other databases, store search text directly
            template.search_vector = search_text
