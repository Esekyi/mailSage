from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.extensions import db
from app.models import User, Template, EmailJob
from app.utils.decorators import require_verified_email
from sqlalchemy import func, or_
from datetime import datetime, timezone, timedelta
from marshmallow import Schema, fields
from app.utils.pagination import paginate


class EmailJobSchema(Schema):
    id = fields.Int()
    subject = fields.Str()
    recipient_count = fields.Int()
    success_count = fields.Int()
    failure_count = fields.Int()
    status = fields.Str()
    created_at = fields.DateTime()


class RecentActivitySchema(Schema):
    id = fields.Int()
    type = fields.Str()
    title = fields.Str()
    description = fields.Str()
    status = fields.Str(allow_none=True)
    created_at = fields.DateTime()


dashboard_bp = Blueprint('dashboard', __name__, url_prefix='/api/v1/dashboard')


@dashboard_bp.route('/overview', methods=['GET'])
@jwt_required()
@require_verified_email
def get_dashboard_overview():
    """Get dashboard overview with email statistics."""
    user_id = get_jwt_identity()
    user = db.session.get(User, user_id)

    if not user:
        return jsonify({"error": "User not found"}), 404

    # Get current week's data
    week_start = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0
    ) - timedelta(days=7)

    current_week = db.session.query(
        func.sum(EmailJob.recipient_count).label('sent'),
        func.sum(EmailJob.success_count).label('opened'),
        func.sum(EmailJob.click_count).label('clicked'),
        func.sum(EmailJob.bounce_count).label('bounced')
    ).filter(
        EmailJob.user_id == user_id,
        EmailJob.created_at >= week_start
    ).first()

    # Get previous week's data for comparison
    prev_week_start = week_start - timedelta(days=7)
    prev_week = db.session.query(
        func.sum(EmailJob.recipient_count).label('sent'),
        func.sum(EmailJob.success_count).label('opened'),
        func.sum(EmailJob.click_count).label('clicked'),
        func.sum(EmailJob.bounce_count).label('bounced')
    ).filter(
        EmailJob.user_id == user_id,
        EmailJob.created_at >= prev_week_start,
        EmailJob.created_at < week_start
    ).first()

    # Calculate daily data for the past week
    daily_stats = []
    for i in range(7):
        day = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - timedelta(days=i)

        stats = db.session.query(
            func.sum(EmailJob.recipient_count).label('sent'),
            func.sum(EmailJob.success_count).label('opened'),
            func.sum(EmailJob.click_count).label('clicked')
        ).filter(
            EmailJob.user_id == user_id,
            EmailJob.created_at >= day,
            EmailJob.created_at < day + timedelta(days=1)
        ).first()

        daily_stats.append({
            "name": day.strftime("%a"),
            "sent": stats.sent or 0,
            "opened": stats.opened or 0,
            "clicked": stats.clicked or 0
        })

    # Calculate bounce rate trend
    bounce_trend = []
    for i in range(7):
        day = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        ) - timedelta(days=i)

        stats = db.session.query(
            func.sum(EmailJob.bounce_count).label('bounced'),
            func.sum(EmailJob.recipient_count).label('total')
        ).filter(
            EmailJob.user_id == user_id,
            EmailJob.created_at >= day,
            EmailJob.created_at < day + timedelta(days=1)
        ).first()

        bounce_rate = 0
        if stats.total:
            bounce_rate = (stats.bounced or 0) / stats.total * 100

        bounce_trend.append({
            "name": day.strftime("%a"),
            "rate": round(bounce_rate, 2)
        })

    # Calculate week-over-week changes
    def calculate_change(current, previous, field):
        if not previous or not getattr(previous, field):
            return 0
        change = ((getattr(current, field) or 0) -
                  getattr(previous, field)) / getattr(previous, field) * 100
        return round(change, 1)

    return jsonify({
        "totalEmails": {
            "sent": current_week.sent or 0,
            "opened": current_week.opened or 0,
            "clicked": current_week.clicked or 0,
            "bounced": current_week.bounced or 0
        },
        "weeklyChange": {
            "totalSent": calculate_change(current_week, prev_week, 'sent'),
            "openRate": calculate_change(current_week, prev_week, 'opened'),
            "clickRate": calculate_change(current_week, prev_week, 'clicked'),
            "bounceRate": calculate_change(current_week, prev_week, 'bounced')
        },
        "dailyData": daily_stats[::-1],  # Reverse to show oldest to newest
        # Reverse to show oldest to newest
        "bounceRateData": bounce_trend[::-1]
    }), 200


@dashboard_bp.route('/recent-activity', methods=['GET'], strict_slashes=False)
@jwt_required()
@require_verified_email
def get_recent_activity():
    """Get paginated recent activity for the user."""
    user_id = get_jwt_identity()

    # Combine recent activities from different sources
    activities = []

    # Get recent email jobs
    recent_jobs = EmailJob.query.filter_by(user_id=user_id)\
        .order_by(EmailJob.created_at.desc())\
        .limit(50).all()

    for job in recent_jobs:
        activities.append({
            'id': job.id,
            'type': 'email_job',
            'title': job.subject,
            'description': f'Sent to {job.recipient_count} recipients',
            'status': job.status,
            'created_at': job.created_at
        })

    # Get recent templates
    recent_templates = Template.query.filter_by(user_id=user_id)\
        .order_by(Template.created_at.desc())\
        .limit(50).all()

    for template in recent_templates:
        activities.append({
            'id': template.id,
            'type': 'template',
            'title': template.name,
            'description': template.description or 'Template created',
            'created_at': template.created_at
        })

    # Sort combined activities by created_at
    activities.sort(key=lambda x: x['created_at'], reverse=True)

    # Manual pagination
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 10))
    total = len(activities)
    start = (page - 1) * per_page
    end = start + per_page

    schema = RecentActivitySchema(many=True)

    return jsonify({
        'items': schema.dump(activities[start:end]),
        'total': total,
        'page': page,
        'per_page': per_page,
        'total_pages': (total + per_page - 1) // per_page
    }), 200


@dashboard_bp.route('/email-jobs', methods=['GET'])
@jwt_required()
@require_verified_email
def get_email_jobs():
    """Get paginated email jobs."""
    user_id = get_jwt_identity()
    query = EmailJob.query.filter_by(user_id=user_id)

    # Apply search if provided
    search = request.args.get('search', '').strip()
    if search:
        query = query.filter(
            or_(
                EmailJob.subject.ilike(f'%{search}%'),
                EmailJob.status.ilike(f'%{search}%')
            )
        )

    paginated = paginate(query, EmailJobSchema)
    return jsonify(paginated.to_dict()), 200

@dashboard_bp.route('/usage-stats', methods=['GET'], strict_slashes=False)
@jwt_required()
@require_verified_email
def get_usage_stats():
    """Get user's usage statistics."""
    user_id = get_jwt_identity()

    # Get monthly email stats
    this_month = datetime.now(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0)

    monthly_stats = db.session.query(
        func.sum(EmailJob.recipient_count).label('total_recipients'),
        func.sum(EmailJob.success_count).label('success_count'),
        func.sum(EmailJob.failure_count).label('failure_count')
    ).filter(
        EmailJob.user_id == user_id,
        EmailJob.created_at >= this_month
    ).first()

    return jsonify({
        "monthly_stats": {
            "total_recipients": monthly_stats.total_recipients or 0,
            "successful_sends": monthly_stats.success_count or 0,
            "failed_sends": monthly_stats.failure_count or 0
        }
    }), 200
