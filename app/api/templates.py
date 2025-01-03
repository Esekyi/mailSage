from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.utils.decorators import require_verified_email
from app.extensions import db
from marshmallow import Schema, fields, validate, ValidationError
from app.models import User, Template
from app.utils.roles import ROLE_CONFIGURATIONS, ResourceLimit
from app.utils.decorators import check_resource_limits
from app.services.template_service import TemplateService
from app.utils.pagination import paginate
from app.services.search_service import TemplateSearchService
from sqlalchemy import or_
from flask import current_app

class TemplateSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    description = fields.Str(required=False, allow_none=True)
    html_content = fields.Str(required=True)


class TemplateUpdateSchema(TemplateSchema):
    """Schema for template updates."""
    change_summary = fields.Str(required=False, allow_none=True)



templates_bp = Blueprint('templates', __name__, url_prefix='/api/v1/templates')


@templates_bp.route('', methods=['POST'], strict_slashes=False)
@jwt_required()
@require_verified_email
@check_resource_limits(ResourceLimit.TEMPLATES)
def create_template():
    """Create a new email template."""
    schema = TemplateSchema()

    try:
        data = schema.load(request.json)
    except ValidationError as e:
        return jsonify({'error': str(e)}), 400

    user_id = get_jwt_identity()

    # Create actual template
    template, error = TemplateService.create_template(
        user_id=user_id,
        name=data['name'],
        description=data.get('description'),
        html_content=data['html_content'],
    )

    if error:
        return jsonify({'error': error}), 400

    return jsonify(template.to_api_response()), 201


@templates_bp.route('/preview', methods=['POST'], strict_slashes=False)
@jwt_required()
@require_verified_email
def preview_unsaved_template():
    """Preview template content before saving."""
    data = request.json
    if not data or 'html_content' not in data:
        return jsonify({"error": "HTML content is required"}), 400

    preview, error = TemplateService.preview_template_content(
        html_content=data['html_content'],
        variables=data.get('variables')
    )

    if error:
        return jsonify({"error": error}), 400

    return jsonify({
        "preview_html": preview,
        "required_variables": list(
            TemplateService.extract_template_variables(data['html_content']))
    }), 200


@templates_bp.route('/<int:template_id>', methods=['PUT'], strict_slashes=False)
@jwt_required()
@require_verified_email
def update_template(template_id: int):
    """Update an existing template, creating a new version."""
    schema = TemplateUpdateSchema()

    try:
        data = schema.load(request.json)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400

    user_id = get_jwt_identity()
    template, error = TemplateService.update_template(
        template_id=template_id,
        user_id=user_id,
        name=data['name'],
        html_content=data['html_content'],
        description=data.get('description'),
        change_summary=data.get('change_summary')
    )

    if error:
        return jsonify({"error": error}), 400 if "not found" not in error else 404

    return jsonify(template.to_api_response()), 200


@templates_bp.route('', methods=['GET'], strict_slashes=False)
@jwt_required()
@require_verified_email
def list_templates():
    """List all active templates for the user."""
    user_id = get_jwt_identity()
    search_query = request.args.get('search', '').strip()

    # Start with base query
    if search_query:
        # Use search service when search parameter is present
        query = TemplateSearchService.search_templates(search_query, user_id)
    else:
        # Normal query without search
        query = Template.query.filter_by(
            user_id=user_id,
            is_active=True,
            deleted_at=None
        )

    # Apply sorting
    sort_by = request.args.get('sort_by', 'created_at')
    sort_order = request.args.get('sort_order', 'desc')

    if hasattr(Template, sort_by):
        sort_column = getattr(Template, sort_by)
        if sort_order == 'desc':
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(Template.created_at.desc())

    # Use the pagination utility
    paginated = paginate(query, schema=None)

    return jsonify({
        "items": [template.to_api_response() for template in paginated.items],
        "total": paginated.total,
        "page": paginated.page,
        "per_page": paginated.per_page,
        "total_pages": paginated.total_pages
    }), 200


@templates_bp.route('/<int:template_id>', methods=['GET'], strict_slashes=False)
@jwt_required()
@require_verified_email
def get_template(template_id):
    """Get a specific template."""
    template = TemplateService.get_template(
        template_id=template_id,
        user_id=get_jwt_identity()
    )

    if not template:
        return jsonify({"error": "Template not found"}), 404

    return jsonify(template.to_api_response()), 200


@templates_bp.route('/<int:template_id>/versions', methods=['GET'], strict_slashes=False)
@jwt_required()
@require_verified_email
def get_template_versions(template_id):
    """Get all versions of a template."""

    user_id = get_jwt_identity()

    template = TemplateService.get_template(
        template_id=template_id,
        user_id=user_id
    )

    if not template:
        return jsonify({"error": "Template not found"}), 404

    versions = template.get_version_history(template.base_template_id)

    return jsonify({
        "versions": [v.to_api_response() for v in versions]
    }), 200


@templates_bp.route('/<int:template_id>/publish', methods=['POST'])
@jwt_required()
def publish_template(template_id):
    """Publish a template version."""
    success, error = TemplateService.publish_template(
        template_id=template_id,
        user_id=get_jwt_identity()
    )

    if error:
        return jsonify({"error": error}), 400 if "not found" not in error else 404

    return jsonify({"message": "Template published successfully"}), 200


@templates_bp.route('/<int:template_id>', methods=['DELETE'], strict_slashes=False)
@jwt_required()
@require_verified_email
def delete_template(template_id):
    """Delete a template."""
    success, error = TemplateService.delete_template(
        template_id=template_id,
        user_id=get_jwt_identity()
    )

    if error:
        return jsonify({"error": error}), 400 if "not found" not in error else 404

    return jsonify({"message": "Template deleted successfully"}), 200
