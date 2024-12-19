from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models.user import User
from app.utils.decorators import check_resource_limits
from app.utils.roles import ResourceLimit
analytics_bp = Blueprint('analytics', __name__, url_prefix='/api/v1')


@analytics_bp.route('/analytics', methods=['GET'])
@jwt_required()
def get_analytics():
    user_id = get_jwt_identity()
    user = db.session.get(User, user_id)
    if user.role not in ['pro', 'enterprise', 'admin']:
        return jsonify({'error': 'Unauthorized'}), 403
    # Add analytics logic
    return jsonify({'data': 'analytics data'}), 200


@analytics_bp.route('/webhooks', methods=['POST'])
@jwt_required()
@check_resource_limits(ResourceLimit.WEBHOOK_ENDPOINTS)
def create_webhook():
    user_id = get_jwt_identity()
    db.session.get(User, user_id)
    # Create webhook logic
    return jsonify({'message': 'Webhook created'}), 201
