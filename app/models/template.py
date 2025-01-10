from .base import BaseModel, SoftDeleteMixin, AuditMixin
from app.extensions import db
from typing import Dict, Any, Optional, List, Set
from app.models.mixins import SerializationMixin, AdminQueryMixin
from sqlalchemy import event
from app.utils.db import TSVectorType
from datetime import datetime, timezone
from app.utils.db import JSONBType
import re


class TemplateVersion(BaseModel, AuditMixin):
    """Model for storing template versions."""
    __tablename__ = 'template_versions'

    template_id = db.Column(db.Integer, db.ForeignKey(
        'templates.id', ondelete='CASCADE'), nullable=False)
    version = db.Column(db.Integer, nullable=False)
    html_content = db.Column(db.Text, nullable=False)
    change_summary = db.Column(db.String(500), nullable=True)
    meta_data = db.Column(JSONBType, default=dict)

    # Relationship back to template
    template = db.relationship('Template', back_populates='versions')

    __table_args__ = (
        db.UniqueConstraint('template_id', 'version',
                            name='uq_template_version'),
        db.Index('idx_template_versions_template_id_version',
                 'template_id', 'version'),
    )


class Template(BaseModel, SoftDeleteMixin, AuditMixin, SerializationMixin, AdminQueryMixin):
    __tablename__ = 'templates'

    user_id = db.Column(db.Integer, db.ForeignKey(
        'users.id', ondelete='CASCADE'), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    html_content = db.Column(db.Text, nullable=False)
    version = db.Column(db.Integer, default=1)
    is_active = db.Column(db.Boolean, default=True, index=True)
    search_vector = db.Column(TSVectorType)
    category = db.Column(db.String(50), nullable=True, index=True)
    tags = db.Column(db.JSON, default=list)
    published_at = db.Column(db.DateTime(timezone=True), nullable=True)
    meta_data = db.Column(JSONBType, default=dict)

    # Relationships
    versions = db.relationship(
        'TemplateVersion', back_populates='template', cascade='all, delete-orphan')

    __table_args__ = (
        db.Index('idx_template_search', 'search_vector',
                 postgresql_using='gin'),
    )

    @property
    def required_variables(self) -> Set[str]:
        """Extract and return required variables from template."""
        return set(re.findall(r'{{\s*(\w+)\s*}}', self.html_content))

    def archive_current_version(self, change_summary: Optional[str] = None) -> None:
        """Archive the current version before updating."""
        version = TemplateVersion(
            template_id=self.id,
            version=self.version,
            html_content=self.html_content,
            change_summary=change_summary,
            meta_data={
                'name': self.name,
                'description': self.description,
                'archived_at': datetime.now(timezone.utc).isoformat()
            }
        )
        db.session.add(version)

    def get_version_history(self) -> List[Dict[str, Any]]:
        """Get the version history of the template, including the current version."""
        # Start with the current version
        history = [{
            'version': self.version,
            'html_content': self.html_content,
            'change_summary': self.meta_data.get('change_summary') if self.meta_data else None,
            'created_at': self.updated_at or self.created_at,
            'meta_data': self.meta_data,
            'is_current': True
        }]

        # Add archived versions
        versions = sorted(self.versions, key=lambda x: x.version, reverse=True)
        for version in versions:
            history.append({
                'version': version.version,
                'html_content': version.html_content,
                'change_summary': version.change_summary,
                'created_at': version.created_at,
                'meta_data': version.meta_data,
                'is_current': False
            })

        return history

    def to_api_response(self) -> Dict[str, Any]:
        """Convert to API response format with version info."""
        response = self.to_dict(exclude=['search_vector'])
        response['required_variables'] = list(self.required_variables)
        response.update({
            'version_info': {
                'current_version': self.version,
                'published_at': self.published_at.isoformat() if self.published_at else None,
                'versions_count': len(self.versions)
            }
        })
        return response

    def publish(self) -> None:
        """Mark template as published."""
        self.published_at = datetime.now(timezone.utc)
        db.session.flush()


@event.listens_for(Template, 'before_insert')
@event.listens_for(Template, 'before_update')
def update_search_vector(mapper, connection, target):
    """Update search_vector before save."""
    from app.services.search_service import TemplateSearchService
    TemplateSearchService.update_search_vector(target)


class TemplateStats(BaseModel):
    __tablename__ = 'template_stats'

    template_id = db.Column(db.Integer, db.ForeignKey(
        'templates.id'), nullable=False)
    total_sends = db.Column(db.Integer, default=0)
    successful_sends = db.Column(db.Integer, default=0)
    failed_sends = db.Column(db.Integer, default=0)
    last_used_at = db.Column(db.DateTime(timezone=True))

    @property
    def success_rate(self) -> float:
        return (self.successful_sends / self.total_sends * 100) if self.total_sends > 0 else 0
