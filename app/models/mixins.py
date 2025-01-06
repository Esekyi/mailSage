from datetime import datetime
from sqlalchemy.orm import Query
from typing import Any, Dict
import enum


class SerializationMixin:
    """Mixin to add serialization capabilities to models."""

    def to_dict(self, exclude: list = None) -> Dict[str, Any]:
        """Convert model instance to dictionary."""
        exclude = exclude or []
        result = {}
        for key in self.__mapper__.c.keys():
            if key not in exclude:
                value = getattr(self, key)
                if isinstance(value, datetime):
                    value = value.isoformat()
                elif isinstance(value, enum.Enum):
                    value = value.value  # Use the string value of the enum
                result[key] = value
        return result


class AdminQueryMixin:
    """Mixin for admin-specific query functionality."""
    class AdminQuery(Query):
        def with_deleted(self):
            """Include soft-deleted records in query."""
            return self.execution_options(include_deleted=True)

        def _get_options(self, kw):
            """Override to handle soft delete filter."""
            options = super()._get_options(kw)
            if not kw.get('include_deleted', False):
                options.append(lambda q: q.filter_by(deleted_at=None))
            return options

    query_class = AdminQuery
