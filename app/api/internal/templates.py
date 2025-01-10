from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.utils.decorators import require_verified_email
from marshmallow import Schema, fields, validate, ValidationError
from app.models import Template
from app.utils.roles import ResourceLimit
from app.utils.decorators import check_resource_limits
from app.services.template_service import TemplateService
from app.services.search_service import TemplateSearchService

class TemplateSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    description = fields.Str(required=False, allow_none=True)
    html_content = fields.Str(required=True)
    tags = fields.List(fields.Str(), required=False, allow_none=True)


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
        tags=data.get('tags'),
        description=data.get('description'),
        html_content=data['html_content']
    )

    if error:
        return jsonify({'error': error}), 400

    response = template.to_api_response()
    response['version_info'].update({
        'is_initial_version': True,
        'has_versions': True,
        'versions_available': 1,
        'versions_count': 1,
        'current_version': 1,
        'latest_version': 1
    })

    return jsonify(response), 201


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
        tags=data.get('tags'),
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
    """List all templates for the current user."""
    user_id = get_jwt_identity()
    search_query = request.args.get('search', '').strip()
    tags = request.args.getlist('tags')  # Support multiple tags
    category = request.args.get('category')

    # Initialize base query
    if search_query or tags:
        # Use search service for search and/or tag filtering
        if search_query and tags:
            templates = TemplateSearchService.search_templates_combined(
                search_query, tags, user_id)
        elif search_query:
            templates = TemplateSearchService.search_templates(
                search_query, user_id)
        else:
            # Only tag filtering
            templates = []
            for tag in tags:
                templates.extend(
                    TemplateSearchService.search_templates_by_tag(tag, user_id))
            # Remove duplicates while preserving order
            templates = list(dict.fromkeys(templates))
    else:
        # No search or tags, use regular query
        templates = Template.query.filter_by(
            user_id=user_id,
            is_active=True,
            deleted_at=None
        )

        # Apply category filter if provided
        if category:
            templates = templates.filter(Template.category == category)

        # Apply sorting
        sort_by = request.args.get('sort_by', 'updated_at')
        sort_order = request.args.get('sort_order', 'desc')

        if sort_by in ['name', 'created_at', 'updated_at']:
            sort_column = getattr(Template, sort_by)
            if sort_order == 'desc':
                templates = templates.order_by(sort_column.desc())
            else:
                templates = templates.order_by(sort_column.asc())

        # Execute query
        templates = templates.all()

    # Paginate results
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 10, type=int), 100)

    # Manual pagination for search results
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page

    total_items = len(templates)
    paginated_templates = templates[start_idx:end_idx]

    # Prepare response with version information
    templates_response = []
    for template in paginated_templates:
        template_data = template.to_api_response()
        # Count versions correctly
        # Count of archived versions
        versions_in_history = len(template.versions)
        template_data['version_info'].update({
            'has_versions': True,  # If we have a template, it always has at least one version
            'versions_count': versions_in_history,  # Number of archived versions
            # Archived versions + current version
            'versions_available': versions_in_history + 1,
            'current_version': template.version,  # Current version number
            'latest_version': template.version,  # Current version is always latest
            'last_updated': template.updated_at.isoformat() if template.updated_at else None
        })
        templates_response.append(template_data)

    return jsonify({
        'templates': templates_response,
        'pagination': {
            'total': total_items,
            'pages': (total_items + per_page - 1) // per_page,
            'current_page': page,
            'per_page': per_page,
            'has_next': end_idx < total_items,
            'has_prev': page > 1
        }
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

    versions = template.get_version_history()

    return jsonify({
        "versions": versions
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


@templates_bp.route('/<int:template_id>/versions/<int:version>', methods=['GET'])
@jwt_required()
@require_verified_email
def get_specific_version(template_id: int, version: int):
    """Get a specific version of a template."""
    user_id = get_jwt_identity()

    template_version = TemplateService.get_template_version(
        template_id=template_id,
        version=version,
        user_id=user_id
    )

    if not template_version:
        return jsonify({"error": "Template version not found"}), 404

    return jsonify({
        "version": template_version.version,
        "html_content": template_version.html_content,
        "created_at": template_version.created_at.isoformat(),
        "meta_data": template_version.meta_data
    }), 200


@templates_bp.route('/<int:template_id>/versions/<int:version>/revert', methods=['POST'])
@jwt_required()
@require_verified_email
def revert_to_version(template_id: int, version: int):
    """Revert a template to a specific version."""
    user_id = get_jwt_identity()

    template, error = TemplateService.revert_to_version(
        template_id=template_id,
        version=version,
        user_id=user_id
    )

    if error:
        return jsonify({"error": error}), 400 if "not found" not in error else 404

    return jsonify(template.to_api_response()), 200


@templates_bp.route('/<int:template_id>/versions/compare', methods=['GET'])
@jwt_required()
@require_verified_email
def compare_versions(template_id: int):
    """Compare two versions of a template."""
    user_id = get_jwt_identity()
    version1 = request.args.get('version1', type=int)
    version2 = request.args.get('version2', type=int)

    if not version1 or not version2:
        return jsonify({"error": "Both version1 and version2 parameters are required"}), 400

    comparison, error = TemplateService.compare_versions(
        template_id=template_id,
        version1=version1,
        version2=version2,
        user_id=user_id
    )

    if error:
        return jsonify({"error": error}), 400 if "not found" not in error else 404

    return jsonify(comparison), 200


@templates_bp.route('/<int:template_id>/versions/available', methods=['GET'])
@jwt_required()
@require_verified_email
def get_available_versions(template_id: int):
    """Get all versions available for comparison."""
    user_id = get_jwt_identity()

    versions, error = TemplateService.get_available_versions(
        template_id=template_id,
        user_id=user_id
    )

    if error:
        return jsonify({"error": error}), 400 if "not found" not in error else 404

    return jsonify({
        "versions": versions,
        "total_versions": len(versions)
    }), 200
