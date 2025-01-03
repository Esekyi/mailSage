from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models import User, EmailDelivery, EmailJob
from app.utils.decorators import check_resource_limits, require_verified_email, permission_required
from app.utils.roles import ResourceLimit, Permission
from datetime import datetime, timezone, timedelta


analytics_bp = Blueprint('analytics', __name__, url_prefix='/api/v1/analytics')


@analytics_bp.route('', methods=['GET'], strict_slashes=False)
@jwt_required()
@require_verified_email
def get_analytics():
    user_id = get_jwt_identity()
    user = db.session.get(User, user_id)
    if user.role not in ['pro', 'enterprise', 'admin']:
        return jsonify({'error': 'Unauthorized'}), 403
    # Add analytics logic
    return jsonify({'data': 'analytics data'}), 200


@analytics_bp.route('/webhooks', methods=['POST'], strict_slashes=False)
@jwt_required()
@require_verified_email
@check_resource_limits(ResourceLimit.WEBHOOK_ENDPOINTS)
def create_webhook():
    user_id = get_jwt_identity()
    db.session.get(User, user_id)
    # Create webhook logic
    return jsonify({'message': 'Webhook created'}), 201


@analytics_bp.route('/email/overview', methods=['GET'])
@jwt_required()
@require_verified_email
@permission_required(Permission.VIEW_ANALYTICS)
def get_email_overview():
    """Get overall email statistics for the user."""
    user_id = get_jwt_identity()

    # Get date range from query params
    days = request.args.get('days', 30, type=int)
    end_date = datetime.now(timezone.utc)
    start_date = end_date - timedelta(days=days)

    # Get statistics
    stats = EmailJob.get_user_statistics(user_id, start_date, end_date)

    return jsonify(stats), 200


@analytics_bp.route('/email/daily', methods=['GET'])
@jwt_required()
@require_verified_email
@permission_required(Permission.VIEW_ANALYTICS)
def get_daily_stats():
    """Get daily email statistics."""
    user_id = get_jwt_identity()
    days = request.args.get('days', 30, type=int)

    stats = EmailJob.get_daily_statistics(user_id, days)

    return jsonify({
        'daily_stats': stats,
        'days_analyzed': days
    }), 200


@analytics_bp.route('/email/smtp-performance', methods=['GET'])
@jwt_required()
@require_verified_email
@permission_required(Permission.VIEW_ANALYTICS)
def get_smtp_performance():
    """Get performance statistics per SMTP configuration."""
    user_id = get_jwt_identity()

    performance_stats = EmailJob.get_smtp_performance(user_id)

    return jsonify({
        'smtp_stats': [
            {
                'smtp_config_id': stat.smtp_config_id,
                'total_jobs': stat.total_jobs,
                'total_emails': stat.total_emails,
                'successful_emails': stat.successful_emails,
                'failed_emails': stat.failed_emails,
                'success_rate': float(stat.success_rate) if stat.success_rate else 0
            }
            for stat in performance_stats
        ]
    }), 200


@analytics_bp.route('/email/jobs/<int:job_id>/engagement', methods=['GET'])
@jwt_required()
def get_job_engagement(job_id):
    """Get engagement metrics for a specific email job."""
    job = EmailJob.query.get_or_404(job_id)

    # Check authorization
    if job.user_id != get_jwt_identity():
        return jsonify({"error": "Unauthorized"}), 403

    engagement_metrics = EmailDelivery.get_engagement_metrics(job_id)
    delivery_stats = EmailDelivery.get_delivery_time_stats(job_id)

    return jsonify({
        'job_id': job_id,
        'engagement': engagement_metrics,
        'delivery_stats': delivery_stats
    }), 200
