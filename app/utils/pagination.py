from flask import request
from typing import TypeVar, Generic, List, Dict, Any
from sqlalchemy.orm import Query
from dataclasses import dataclass

T = TypeVar('T')


@dataclass
class PaginatedResponse(Generic[T]):
    items: List[T]
    total: int
    page: int
    per_page: int
    total_pages: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "items": [item.to_dict() if hasattr(item, 'to_dict') else item
                      for item in self.items],
            "total": self.total,
            "page": self.page,
            "per_page": self.per_page,
            "total_pages": self.total_pages
        }


def paginate(query: Query, schema=None) -> PaginatedResponse:
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    search = request.args.get('search', '').strip()
    sort_by = request.args.get('sort_by')
    sort_order = request.args.get('sort_order', 'desc')

    # Apply search if the model has a search vector
    if search and hasattr(query.column_descriptions[0]['type'], 'search_vector'):
        query = query.filter(
            query.column_descriptions[0]['type'].search_vector.match(search)
        )

    # Apply sorting
    if sort_by and hasattr(query.column_descriptions[0]['type'], sort_by):
        sort_column = getattr(query.column_descriptions[0]['type'], sort_by)
        if sort_order == 'desc':
            sort_column = sort_column.desc()
        query = query.order_by(sort_column)
    else:
        # Default sort by created_at desc
        if hasattr(query.column_descriptions[0]['type'], 'created_at'):
            query = query.order_by(
                query.column_descriptions[0]['type'].created_at.desc()
            )

    # Get total before pagination
    total = query.count()
    total_pages = (total + per_page - 1) // per_page

    # Ensure page is within bounds
    page = min(max(1, page), total_pages) if total_pages > 0 else 1

    # Apply pagination
    items = query.offset((page - 1) * per_page).limit(per_page).all()

    # Apply schema if provided
    if schema:
        items = [schema.dump(item) for item in items]

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages
    )
