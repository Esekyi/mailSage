from .base import BaseModel, SoftDeleteMixin, AuditMixin
from app.extensions import db
from typing import Dict, Any, Optional, List, Set
from app.models.mixins import SerializationMixin, AdminQueryMixin
from sqlalchemy import event, desc
from app.utils.db import TSVectorType
from datetime import datetime, timezone
from app.utils.db import JSONBType
import re


class Template(BaseModel, SoftDeleteMixin, AuditMixin,
               SerializationMixin, AdminQueryMixin):
    __tablename__ = 'templates'

    user_id = db.Column(db.Integer, db.ForeignKey(
        'users.id', ondelete='CASCADE'),
        nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    html_content = db.Column(db.Text, nullable=False)
    version = db.Column(db.Integer, default=1)
    is_active = db.Column(db.Boolean, default=True, index=True)
    search_vector = db.Column(TSVectorType)

    category = db.Column(db.String(50), nullable=True, index=True)
    tags = db.Column(db.JSON, default=list)

    # Version control fields
    parent_id = db.Column(db.Integer, db.ForeignKey(
        'templates.id'), nullable=True)
    base_template_id = db.Column(
        db.Integer, nullable=False)  # Original template ID
    published_at = db.Column(db.DateTime(timezone=True), nullable=True)
    change_summary = db.Column(db.String(500), nullable=True)

    # Metadata
    meta_data = db.Column(JSONBType, default=dict)

    # Relationships
    children = db.relationship(
        'Template',
        backref=db.backref('parent', remote_side=lambda: [Template.id]),
        cascade='all, delete-orphan'
    )


    __table_args__ = (
        db.Index('idx_template_search', 'search_vector',
                 postgresql_using='gin'),
        db.Index('idx_template_active_version',
                 'base_template_id', 'is_active', 'version'),
        db.UniqueConstraint('base_template_id', 'version',
                            name='uq_template_version')
    )

    @property
    def required_variables(self) -> Set[str]:
        """Extract and return required variables from template."""
        return set(re.findall(r'{{\s*(\w+)\s*}}', self.html_content))

    @classmethod
    def get_latest_version(cls, base_template_id: int) -> Optional['Template']:
        """Get the latest version of a template."""
        return cls.query.filter_by(
            base_template_id=base_template_id,
            is_active=True
        ).order_by(desc(cls.version)).first()

    @classmethod
    def get_version_history(cls, base_template_id: int) -> List['Template']:
        """Get all versions of a template ordered by version."""
        return cls.query.filter_by(
            base_template_id=base_template_id
        ).order_by(desc(cls.version)).all()

    def create_new_version(self, html_content: str, change_summary: str = None) -> 'Template':
        """Create a new version of this template."""
        new_version = Template(
            user_id=self.user_id,
            name=self.name,
            description=self.description,
            html_content=html_content,
            version=self.version + 1,
            parent_id=self.id,
            base_template_id=self.base_template_id or self.id,
            change_summary=change_summary
        )

        # Deactivate the current version
        self.is_active = False

        return new_version

    def publish(self) -> None:
        """Mark template version as published."""
        self.published_at = datetime.now(timezone.utc)
        db.session.flush()  # Ensure the change is reflected in the session


    def to_api_response(self) -> Dict[str, Any]:
        """Convert to API response format with version info."""
        response = self.to_dict(exclude=['search_vector'])
        response['required_variables'] = list(self.required_variables)
        response.update({
            'version_info': {
                'is_latest': self.is_active,
                'published_at': self.published_at.isoformat() if self.published_at else None,
                'change_summary': self.change_summary,
                'created_by': self.created_by,
                'has_newer_version': bool(Template.query.filter(
                    Template.base_template_id == self.base_template_id,
                    Template.version > self.version
                ).first())
            }
        })
        return response


@event.listens_for(Template, 'before_insert')
def set_base_template_id(mapper, connection, target):
    """Set base_template_id to template's own ID for new templates."""
    if target.base_template_id is None:
        # Will be replaced with actual ID after insert
        target.base_template_id = -1


@event.listens_for(Template, 'after_insert')
def update_base_template_id(mapper, connection, target):
    """Update base_template_id with the template's own ID after insert."""
    if target.base_template_id == -1:
        connection.execute(
            Template.__table__.update().
            where(Template.__table__.c.id == target.id).
            values(base_template_id=target.id)
        )


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
