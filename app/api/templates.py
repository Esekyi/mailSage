from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.utils.decorators import require_verified_email
from app.extensions import db
from app.models import User, Template
from app.utils.roles import ROLE_CONFIGURATIONS, ResourceLimit
from app.utils.decorators import check_resource_limits
templates_bp = Blueprint('templates', __name__, url_prefix='/api/v1/templates')


@templates_bp.route('', methods=['POST'])
@jwt_required()
@require_verified_email
@check_resource_limits(ResourceLimit.TEMPLATES)
def create_template():
    user_id = get_jwt_identity()
    user = db.session.get(User, user_id)

    data = request.get_json()
    name = data.get('name')
    content = data.get('content', '')

    size_limit = ROLE_CONFIGURATIONS[user.role]['limits'][
        ResourceLimit.TEMPLATE_SIZE.value]
    if len(content) > size_limit:
        return jsonify({'error': 'Template size exceeds limit'}), 403

    # Create actual template
    template = Template(
        user_id=user_id,
        name=name,
        html_content=content,
        variables={},
        version=1
    )
    db.session.add(template)
    db.session.commit()

    return jsonify({'message': 'Template created', 'id': template.id}), 201
