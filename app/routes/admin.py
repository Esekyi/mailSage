from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required
from app.utils.decorators import permission_required
from app.utils.roles import Permission

admin_bp = Blueprint('admin', __name__, url_prefix='/api/v1/admin')


@admin_bp.route('/users', methods=['GET'])
@jwt_required()
@permission_required([Permission.ACCESS_ADMIN])
def get_users():
    return jsonify({'users': []}), 200
