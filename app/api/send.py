from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models import User, EmailJob
from app.utils.roles import ROLE_CONFIGURATIONS, ResourceLimit
from datetime import datetime, timezone
from sqlalchemy import func
send_bp = Blueprint('send', __name__, url_prefix='/api/v1')


@send_bp.route('/send', methods=['POST'])
@jwt_required()
def send_email():
    user_id = get_jwt_identity()
    user = db.session.get(User, user_id)
    daily_limit = ROLE_CONFIGURATIONS[user.role]['limits'][
        ResourceLimit.DAILY_EMAILS.value]

    start_of_day = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0)

    email_count = db.session.query(
        func.sum(EmailJob.recipient_count)
    ).filter(
        EmailJob.user_id == user.id,
        EmailJob.created_at >= start_of_day
    ).scalar() or 0

    if email_count >= daily_limit:
        return jsonify({'error': 'Daily limit reached for emails'}), 403

    return jsonify({'message': 'Email sent'}), 200


@send_bp.route('/send/batch', methods=['POST'])
@jwt_required()
def send_batch_email():
    user_id = get_jwt_identity()
    db.session.get(User, user_id)
    return jsonify({'message': 'Batch email sent'}), 200
