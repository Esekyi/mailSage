from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import Schema, fields, ValidationError
from app.extensions import db
from app.models import User, EmailJob, EmailDelivery, SMTPConfiguration
from app.utils.roles import ROLE_CONFIGURATIONS, ResourceLimit, Permission
from app.utils.decorators import permission_required, require_verified_email
from app.tasks.email_tasks import send_single_email_task
from app.tasks.email_tasks import send_batch_emails_task
from datetime import datetime, timezone
from sqlalchemy import func
from typing import List


class SingleEmailSchema(Schema):
    """Schema for single email sending."""
    to_email = fields.Email(required=True)
    subject = fields.Str(required=True)
    body = fields.Str(required=True)
    smtp_config_id = fields.Int(required=False)


class BatchEmailSchema(Schema):
    """Schema for batch email sending."""
    recipients = fields.List(fields.Email(), required=True)
    subject = fields.Str(required=True)
    body = fields.Str(required=True)
    smtp_config_id = fields.Int(required=False)


send_bp = Blueprint('send', __name__,
                    url_prefix='/api/v1/send')


@send_bp.route('/email', methods=['POST'], strict_slashes=False)
@jwt_required()
@require_verified_email
@permission_required(Permission.SEND_EMAILS.value)
def send_single_email():
    """Send a single email."""
    schema = SingleEmailSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400

    user_id = get_jwt_identity()
    user = User.query.get_or_404(user_id)

    # Check daily limit
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
        return jsonify({'error': 'Daily email limit reached'}), 403

    # Verify SMTP config if specified
    smtp_config_id = data.get('smtp_config_id')
    if smtp_config_id:
        smtp_config = SMTPConfiguration.query.get(smtp_config_id)
        if not smtp_config_id or smtp_config.user_id != user.id:
            return jsonify({"error": "Invalid SMTP configuration"}), 400

    # Create email job record
    job = EmailJob(
        user_id=user_id,
        subject=data['subject'],
        status=EmailJob.STATUS_PENDING,
        recipient_count=1,
        smtp_config_id=smtp_config_id
    )
    db.session.add(job)
    db.session.flush()

    # Create delivery record
    delivery = EmailDelivery(
        job_id=job.id,
        recipient=data['to_email'],
        status='pending'
    )
    db.session.add(delivery)
    db.session.commit()

    # Queue the email task
    task = send_single_email_task.delay(
        user_id=user_id,
        to_email=data['to_email'],
        subject=data['subject'],
        body=data['body'],
        smtp_config_id=smtp_config_id
    )

    return jsonify({
        "message": "Email queued successfully",
        "job_id": job.id,
        "task_id": task.id
    }), 202


@send_bp.route('/batch', methods=['POST'], strict_slashes=False)
@jwt_required()
@require_verified_email
@permission_required(Permission.SEND_EMAILS.value)
def send_batch_email():
    """Send emails to multiple recipients."""
    schema = BatchEmailSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as e:
        return jsonify({"error": str(e)}), 400

    user_id = get_jwt_identity()
    user = User.query.get_or_404(user_id)

    recipients: List[str] = data['recipients']
    recipient_count = len(recipients)

    # Check recipient limit
    max_recipients = ROLE_CONFIGURATIONS[user.role]['limits'][
        ResourceLimit.MAX_RECIPIENTS.value]
    if recipient_count > max_recipients:
        return jsonify({
            "error": f"Recipient count eceeds limit of {max_recipients}"
        }), 403

    # Check daily limit
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

    if email_count + recipient_count > daily_limit:
        return jsonify({'error': 'Daily email limit would be exceeded'}), 403

    # Verify SMTP config if specified
    smtp_config_id = data.get('smtp_config_id')
    if smtp_config_id:
        smtp_config = SMTPConfiguration.query.get(smtp_config_id)
        if not smtp_config or smtp_config.user_id != user_id:
            return jsonify({"error": "Invalid SMTP configuration"}), 400

    # Create email job
    job = EmailJob(
        user_id=user_id,
        subject=data['subject'],
        body=data['body'],
        status='pending',
        recipient_count=recipient_count,
        smtp_config_id=smtp_config_id,
        started_at=datetime.now(timezone.utc)
    )
    db.session.add(job)
    db.session.flush()

    # Create delivery records
    deliveries = [
        EmailDelivery(
            job_id=job.id,
            recipient=recipient,
            status='pending'
        )
        for recipient in recipients
    ]
    db.session.bulk_save_objects(deliveries)
    db.session.commit()

    # Queue the batch email task
    task = send_batch_emails_task.delay(job_id=job.id)

    return jsonify({
        "message": "Batch email job queued successfully",
        "job_id": job.id,
        "task_id": task.id,
        "recipient_count": recipient_count
    }), 202


@send_bp.route('/status/<int:job_id>', methods=['GET'], strict_slashes=False)
@jwt_required()
def get_email_status(job_id):
    """Get status of an email job."""
    job = EmailJob.query.get_or_404(job_id)

    if int(job.user_id) != int(get_jwt_identity()):
        return jsonify({"error": "Unauthorized"}), 403

    return jsonify({
        "id": job.id,
        "status": job.status,
        "recipient_count": job.recipient_count,
        "success_count": job.success_count,
        "failure_count": job.failure_count,
        "created_at": job.created_at.isoformat(),
        "completed_at": job.completed_at.isoformat() if job.completed_at else None
    }), 200
