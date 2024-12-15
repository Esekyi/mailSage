from .base import BaseModel, SoftDeleteMixin, AuditMixin
from app.extensions import db
from typing import Dict, Any
from app.models.mixins import SerializationMixin, AdminQueryMixin
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy import event


class Template(BaseModel, SoftDeleteMixin, AuditMixin,
               SerializationMixin, AdminQueryMixin):
    __tablename__ = 'templates'

    user_id = db.Column(db.Integer, db.ForeignKey(
        'users.id', ondelete='CASCADE'),
        nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    html_content = db.Column(db.Text, nullable=False)
    variables = db.Column(db.JSON, default=dict)
    version = db.Column(db.Integer, default=1)
    is_active = db.Column(db.Boolean, default=True, index=True)
    search_vector = db.Column(TSVECTOR)

    __table_args__ = (
        db.Index(
            'idx_template_search', 'search_vector', postgresql_using='gin'
        ),
    )

    def to_api_response(self) -> Dict[str, Any]:
        """Convert to API response format."""
        return self.to_dict(exclude=['search_vector'])


@event.listens_for(Template, 'before_insert')
@event.listens_for(Template, 'before_update')
def update_search_vector(mapper, connection, target):
    """Update search_vector before save."""
    from app.services.search_service import TemplateSearchService
    TemplateSearchService.update_search_vector(target)
