from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.utils.decorators import permission_required
from app.services.analytics_service import AnalyticsService
from app.utils.roles import Permission
from datetime import datetime, timezone, timedelta
from marshmallow import Schema, fields


analytics_bp = Blueprint('analytics', __name__, url_prefix='/api/v1/analytics')


class DateRangeSchema(Schema):
    start_date = fields.DateTime(required=False)
    end_date = fields.DateTime(required=False)
    days = fields.Integer(required=False)


@analytics_bp.route('/dashboard', methods=['GET'])
@jwt_required()
@permission_required(Permission.VIEW_ANALYTICS.value)
def get_dashboard_metrics():
    """Get comprehensive dashboard metrics."""
    try:
        metrics = AnalyticsService.get_user_dashboard_metrics(
            get_jwt_identity())
        return jsonify(metrics), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@analytics_bp.route('/email-metrics', methods=['GET'])
@jwt_required()
@permission_required(Permission.VIEW_ANALYTICS)
def get_email_metrics():
    """Get email sending metrics with optional date range."""
    schema = DateRangeSchema()
    args = schema.load(request.args)

    start_date = args.get('start_date')
    end_date = args.get('end_date')

    if not start_date and args.get('days'):
        start_date = datetime.now(timezone.utc) - timedelta(days=args['days'])

    metrics = AnalyticsService.get_email_metrics(
        get_jwt_identity(),
        start_date=start_date,
        end_date=end_date
    )

    return jsonify(metrics), 200


@analytics_bp.route('/smtp-performance', methods=['GET'])
@jwt_required()
@permission_required(Permission.VIEW_ANALYTICS)
def get_smtp_performance():
    """Get performance metrics for SMTP configurations."""
    metrics = AnalyticsService.get_smtp_performance(get_jwt_identity())
    return jsonify(metrics), 200


@analytics_bp.route('/template-usage', methods=['GET'])
@jwt_required()
@permission_required(Permission.VIEW_ANALYTICS)
def get_template_usage():
    """Get template usage statistics."""
    stats = AnalyticsService.get_template_usage(get_jwt_identity())
    return jsonify(stats), 200


@analytics_bp.route('/delivery-timeline', methods=['GET'])
@jwt_required()
@permission_required(Permission.VIEW_ANALYTICS)
def get_delivery_timeline():
    """Get daily email delivery statistics."""
    days = request.args.get('days', default=30, type=int)
    timeline = AnalyticsService.get_delivery_timeline(
        get_jwt_identity(),
        days=days
    )
    return jsonify(timeline), 200


@analytics_bp.route('/engagement', methods=['GET'])
@jwt_required()
@permission_required(Permission.VIEW_ANALYTICS)
def get_engagement_metrics():
    """Get email engagement metrics."""
    metrics = AnalyticsService.get_engagement_metrics(get_jwt_identity())
    return jsonify(metrics), 200
