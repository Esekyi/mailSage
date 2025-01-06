from flask import Blueprint, request, jsonify
from typing import Dict, Any, Optional, List
from app.utils.decorators import require_api_key
from app.services.mail_service import MailService
from app.services.template_service import TemplateRenderService
from app.services.job_control_service import JobControlService
from app.models import Template, SMTPConfiguration, EmailJob, EmailDelivery
from marshmallow import Schema, fields, validate, validates_schema, ValidationError
from app.utils.logging import logger
from app.tasks.email_tasks import send_single_email_task, process_email_batch, send_templated_email

# Initialize Blueprint
emails_bp = Blueprint('emails', __name__, url_prefix='/api/v1/emails')


class RecipientSchema(Schema):
    """Schema for email recipient with variables."""
    email = fields.Email(required=True)
    variables = fields.Dict(
        keys=fields.Str(), values=fields.Raw(), required=False)


class SingleEmailSchema(Schema):
    """Schema for single email sending request."""
    recipient = fields.Nested(RecipientSchema(), required=True)
    template_id = fields.Int(required=False)
    subject = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    body = fields.Str(required=False)  # Required if no template_id
    smtp_id = fields.Int(required=False)

    @validates_schema
    def validate_content(self, data: Dict[str, Any], **kwargs):
        """Validate that either template_id or body is provided."""
        if not data.get('template_id') and not data.get('body'):
            raise ValidationError(
                "Either template_id or body must be provided")


class BatchEmailSchema(Schema):
    """Schema for batch email sending request."""
    template_id = fields.Int(required=False)
    recipients = fields.List(fields.Nested(RecipientSchema()), required=True,
                             validate=validate.Length(min=1))
    subject = fields.Str(
        required=True, validate=validate.Length(min=1, max=255))
    body = fields.Str(required=False)
    smtp_id = fields.Int(required=False)
    smtp_strategy = fields.Str(
        required=False,
        validate=validate.OneOf(['default', 'round_robin']),
        missing='default'
    )
    campaign_id = fields.Int(required=False)

    @validates_schema
    def validate_content(self, data: Dict[str, Any], **kwargs):
        if not data.get('template_id') and not data.get('body'):
            raise ValidationError(
                "Either template_id or body must be provided")


@emails_bp.route('/send', methods=['POST'], strict_slashes=False)
@require_api_key
def send_email():
    """
    Send a single email using template or raw content.

    Request body:
    {
        "template_id": "Int",  # Optional
        "recipient": {
            "email": "user@example.com",
            "variables": {"name": "John"}  # Optional, required if using template
        },
        "subject": "Email subject",
        "body": "Email content",  # Optional if template_id provided
        "smtp_id": "Int"  # Optional, uses default if not specified
    }

    Returns:
        JSON response with job ID for tracking
    """
    try:
        # Validate request data
        schema = SingleEmailSchema()
        data = schema.load(request.get_json())

        # Get user from API key
        user_id = request.user_id

        # Initialize services
        mail_service = MailService()
        template_render_service = TemplateRenderService()
        # Validate sending quota
        quota_valid, error = mail_service.validate_sending_quota(
            user_id=user_id,
            recipient_count=1
        )
        if not quota_valid:
            return jsonify({"error": error}), 429

        # Verify template access if provided
        if data.get('template_id'):
            template = Template.query.get(data['template_id'])
            if not template or template.user_id != user_id:
                return jsonify({"error": "Template not found or access denied"}), 404

            # Validate template variables
            is_valid, error = template_render_service.validate_template_variables(
                template,
                data['recipient'].get('variables', {})
            )
            if not is_valid:
                return jsonify({"error": error}), 400

        # Get SMTP configuration
        smtp_config = None
        if data.get('smtp_id'):
            smtp_config = SMTPConfiguration.query.get(data['smtp_id'])
            if not smtp_config or smtp_config.user_id != user_id:
                return jsonify({"error": "SMTP configuration not found or access denied"}), 404

        # Create email job
        job, error = mail_service.create_email_job(
            user_id=user_id,
            recipients=[{
                'email': data['recipient']['email'],
                'variables': data['recipient'].get('variables', {})
            }],
            subject=data['subject'],
            body=data.get('body'),
            template_id=data.get('template_id'),
            smtp_id=data.get('smtp_id')
        )

        if error:
            return jsonify({"error": error}), 400

        # Queue the task
        if data.get('template_id'):
            task = send_templated_email.delay(job.id)
        else:
            task = send_single_email_task.delay(job.id)

        return jsonify({
            "message": "Email queued successfully",
            "job_id": job.id,
            "task_id": task.id,
            "tracking_id": job.tracking_id,
            "status": "queued",
        }), 202

    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Email send error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@emails_bp.route('/send/batch', methods=['POST'], strict_slashes=False)
@require_api_key
def send_batch():
    """
    Send batch emails using template or raw content.

    Request body:
    {
        "template_id": "Int",  # Optional
        "recipients": [
            {
                "email": "user1@example.com",
                "variables": {"name": "John"}
            }
        ],
        "subject": "Email subject",
        "body": "Email content",  # Optional if template_id provided
        "smtp_id": "Int",  # Optional
        "campaign_id": "Int"  # Optional, for tracking
    }

    Returns:
        JSON response with job ID for tracking
    """
    try:
        # Validate request data
        schema = BatchEmailSchema()
        data = schema.load(request.get_json())

        user_id = request.user_id
        mail_service = MailService()
        template_render_service = TemplateRenderService()

        # Validate sending quota
        recipient_count = len(data['recipients'])
        can_send, error = mail_service.validate_sending_quota(
            user_id, recipient_count)
        if not can_send:
            return jsonify({"error": error}), 429

        # Validate template if provided
        if data.get('template_id'):
            template = Template.query.get(data['template_id'])
            if not template or template.user_id != user_id:
                return jsonify({"error": "Template not found or access denied"}), 404

            # Validate variables for each recipient
            for recipient in data['recipients']:
                is_valid, error = template_render_service.validate_template_variables(
                    template,
                    recipient.get('variables', {})
                )
                if not is_valid:
                    return jsonify({
                        "error": f"Invalid variables for {recipient['email']}: {error}"
                    }), 400

        # Validate SMTP configuration
        smtp_config = None
        if data.get('smtp_id'):
            smtp_config = SMTPConfiguration.query.get(data['smtp_id'])
            if not smtp_config or smtp_config.user_id != user_id:
                return jsonify({"error": "SMTP configuration not found or access denied"}), 404

        # Create email job
        job, error = mail_service.create_email_job(
            user_id=user_id,
            recipients=data['recipients'],
            subject=data['subject'],
            body=data.get('body'),
            template_id=data.get('template_id'),
            smtp_id=data.get('smtp_id'),
            campaign_id=data.get('campaign_id')
        )

        if error:
            return jsonify({"error": error}), 400

        # Queue the batch processing task
        task = process_email_batch.delay(job.id)

        return jsonify({
            "message": "Batch email queued successfully",
            "job_id": job.id,
            "task_id": task.id,
            "tracking_id": job.tracking_id,
            "status": "queued",
            "recipient_count": recipient_count
        }), 202

    except ValidationError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logger.error(f"Batch email error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@emails_bp.route('/jobs/active', methods=['GET'], strict_slashes=False)
@require_api_key
def get_active_jobs():
    """
    Get all active jobs for the authenticated user.
    """
    user_id = request.user_id
    job_control = JobControlService()
    return jsonify(job_control.get_active_jobs(user_id)), 200


@emails_bp.route('/jobs/<int:job_id>/status', methods=['GET'], strict_slashes=False)
@require_api_key
def get_job_status(job_id):
    """
    Get the status of an email job.

    Parameters:
        job_id: int of the email job

    Returns:
        JSON response with job status and progress details
    """
    try:
        user_id = request.user_id
        job_control = JobControlService()

        # Get job progress
        progress = job_control.get_job_progress(job_id, user_id)
        if not progress:
            return jsonify({"error": "Job not found or access denied"}), 404

        return jsonify(progress), 200

    except Exception as e:
        logger.error(f"Job status error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@emails_bp.route('/jobs/<int:job_id>/control', methods=['POST'], strict_slashes=False)
@require_api_key
def control_job(job_id):
    """
    Control an email job (pause/resume/stop).

    Request body:
    {
        "action": "pause|resume|stop"
    }

    Returns:
        JSON response with updated job status
    """
    try:
        user_id = request.user_id
        action = request.json.get('action')

        if action not in ['pause', 'resume', 'stop']:
            return jsonify({"error": "Invalid action"}), 400

        job_control = JobControlService()

        if action == 'pause':
            success = job_control.pause_job(job_id, user_id)
        elif action == 'resume':
            success = job_control.resume_job(job_id, user_id)
        else:  # stop
            success = job_control.stop_job(job_id, user_id)

        if not success:
            return jsonify({"error": "Failed to control job"}), 400

        progress = job_control.get_job_progress(job_id, user_id)
        return jsonify(progress), 200

    except Exception as e:
        logger.error(f"Job control error: {str(e)}")
        return jsonify({"error": "Internal server error"}), 500


@emails_bp.route('/jobs/<int:job_id>/deliveries', methods=['GET'], strict_slashes=False)
@require_api_key
def get_job_deliveries(job_id):
    """
    Get detailed delivery information for a job.
    """
    try:
        # Verify job ownership
        job = EmailJob.query.filter_by(
            id=job_id,
            user_id=request.user_id
        ).first()

        if not job:
            return jsonify({"error": "Job not found or access denied"}), 404

        # Get deliveries with pagination
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        status = request.args.get('status')  # Optional status filter

        query = EmailDelivery.query.filter_by(
            job_id=job_id
        )
        if status:
            query = query.filter_by(status=status.lower())

        deliveries = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )

        return jsonify({
            "deliveries": [{
                "id": d.id,
                "recipient": d.recipient,
                "status": d.status,
                "tracking_id": d.tracking_id,
                "attempts": d.attempts,
                "last_attempt": d.last_attempt.isoformat() if d.last_attempt else None,
                "error_message": d.error_message,
                "opened_at": d.opened_at.isoformat() if d.opened_at else None,
                "clicked_at": d.clicked_at.isoformat() if d.clicked_at else None
            } for d in deliveries.items],
            "pagination": {
                "page": deliveries.page,
                "per_page": deliveries.per_page,
                "total": deliveries.total,
                "pages": deliveries.pages
            }
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500

