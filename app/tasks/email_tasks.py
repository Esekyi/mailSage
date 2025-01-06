from celery import shared_task, Task
from typing import Optional, Dict, Any, List
from app.services.mail_service import MailService
from app.models import EmailJob, EmailDelivery, SMTPConfiguration, Template
from app.extensions import db
from datetime import datetime, timezone
from flask import current_app
from app.services.template_service import TemplateRenderService
from app.services.smtp_service import SMTPService
from app.utils.logging import logger
from app.services.job_control_service import JobControlService
from app.services.webhook_service import WebhookService
from app.services.template_service import TemplateService


class EmailTask(Task):
    """Base task class for email operations."""

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure."""
        job_id = kwargs.get('job_id')
        if job_id:
            job = EmailJob.query.get(job_id)
            if job:
                job.status = 'failed'
                job.error_details = {
                    'error': str(exc),
                    'traceback': einfo.traceback
                }
                db.session.commit()

                # Notify via webhook
                webhook_service = WebhookService()
                webhook_service.notify_job_status(job_id, 'failed')


@shared_task(bind=True, base=EmailTask)
def send_single_email_task(self, job_id: int) -> bool:
    """Process a single email with job control support."""
    try:
        job = EmailJob.query.get(job_id)
        if not job:
            raise ValueError(f"Email job {job_id} not found")

        # Check if job is stopped
        job_control = JobControlService()
        if job_control.is_job_stopped(job_id):
            return {"status": "stopped", "job_id": job_id}

        # Get the single delivery
        delivery = EmailDelivery.query.filter_by(
            job_id=job_id,
            status=EmailDelivery.STATUS_PENDING
        ).first()

        if not delivery:
            return {"status": "no_pending_delivery", "job_id": job_id}

        # Update job status
        job.status = 'processing'
        job.started_at = datetime.now(timezone.utc)
        db.session.commit()

        mail_service = MailService()
        success, error = mail_service.send_raw_email(
            user_id=job.user_id,
            to_email=delivery.recipient,
            subject=job.subject,
            body=job.body,
            smtp_config=job.smtp_config
        )

        # Update statuses
        delivery.last_attempt = datetime.now(timezone.utc)
        delivery.attempts += 1

        if success:
            delivery.status = 'sent'
            job.status = 'completed'
            job.success_count = 1
        else:
            delivery.status = 'failed'
            delivery.error_message = error
            job.status = 'failed'
            job.failure_count = 1
            job.error_details = {'error': error}

        job.completed_at = datetime.now(timezone.utc)
        db.session.commit()

        # Notify via webhooks
        webhook_service = WebhookService()
        webhook_service.notify_job_status(job_id, job.status)
        webhook_service.notify_delivery_status(delivery.id, delivery.status)

        return {
            "status": job.status,
            "job_id": job_id,
            "success": success,
            "error": error if not success else None
        }

    except Exception as e:
        logger.error(f"Template email error for job {job_id}: {str(e)}")
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))


@shared_task(bind=True, base=EmailTask)
def send_templated_email(self, job_id: int) -> Dict[str, Any]:
    """Process a single templated email with job control support."""
    try:
        job = EmailJob.query.get(job_id)
        if not job:
            raise ValueError(f"Email job {job_id} not found")

        # Check if job is stopped
        job_control = JobControlService()
        if job_control.is_job_stopped(job_id):
            return {"status": "stopped", "job_id": job_id}

        # Get the single delivery
        delivery = EmailDelivery.query.filter_by(
            job_id=job_id,
            status='pending'
        ).first()

        if not delivery:
            return {"status": "no_pending_delivery", "job_id": job_id}

        # Update job status
        job.status = 'processing'
        job.started_at = datetime.now(timezone.utc)
        db.session.commit()

        # Render template
        template_service = TemplateService()
        rendered_content, error = template_service.render_template_for_send(
            template_id=job.template_id,
            variables=delivery.variables
        )

        if error:
            raise ValueError(f"Template rendering failed: {error}")

        # Send email
        mail_service = MailService()
        success, error = mail_service.send_raw_email(
            user_id=job.user_id,
            to_email=delivery.recipient,
            subject=job.subject,
            body=rendered_content,
            smtp_config=job.smtp_config
        )

        # Update statuses
        delivery.last_attempt = datetime.now(timezone.utc)
        delivery.attempts += 1

        if success:
            delivery.status = 'sent'
            job.status = 'completed'
            job.success_count = 1
        else:
            delivery.status = 'failed'
            delivery.error_message = error
            job.status = 'failed'
            job.failure_count = 1
            job.error_details = {'error': error}

        job.completed_at = datetime.now(timezone.utc)
        db.session.commit()

        # Notify via webhooks
        webhook_service = WebhookService()
        webhook_service.notify_job_status(job_id, job.status)
        webhook_service.notify_delivery_status(delivery.id, delivery.status)

        return {
            "status": job.status,
            "job_id": job_id,
            "success": success,
            "error": error if not success else None
        }

    except Exception as e:
        logger.error(f"Template email error for job {job_id}: {str(e)}")
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))


@shared_task(bind=True, base=EmailTask)
def process_email_batch(self, job_id: int, batch_size: int = 50) -> Dict[str, Any]:
    """Process a batch of emails with job control support."""
    try:
        job = EmailJob.query.get(job_id)
        if not job:
            raise ValueError(f"Email job {job_id} not found")

        # Check if job stopped or paused
        job_control = JobControlService()
        if job_control.is_job_stopped(job_id):
            return {
                "status": "stopped",
                "job_id": job_id
            }
        if job_control.is_job_paused(job_id):
            return {
                "status": "paused",
                "job_id": job_id
            }

        # Update job status
        if job.status == EmailJob.STATUS_PENDING:
            job.status = EmailJob.STATUS_PROCESSING
            job.started_at = datetime.now(timezone.utc)
            db.session.commit()

            # Notify start via webhook if configured
            webhook_service = WebhookService()
            webhook_service.notify_job_status(job_id, 'started')

        # Get pending deliveries for this batch
        deliveries = EmailDelivery.query.filter(
            EmailDelivery.job_id == job_id,
            EmailDelivery.status == EmailDelivery.STATUS_PENDING
        ).limit(batch_size).all()

        if not deliveries:
            # No more pending deliveries, mark job as completed
            job.status = EmailJob.STATUS_COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            db.session.commit()

            # Notify completion via webhook
            webhook_service = WebhookService()
            webhook_service.notify_job_status(job_id, 'completed')

            return {
                "status": "completed",
                "job_id": job_id,
                "success_count": job.success_count,
                "failure_count": job.failure_count
            }

        # Process each delivery
        template_service = TemplateService()
        mail_service = MailService()

        for delivery in deliveries:
            try:
                # Check for stop/pause again
                if job_control.is_job_stopped(job_id):
                    return {"status": "stopped", "job_id": job_id}
                if job_control.is_job_paused(job_id):
                    return {"status": "paused", "job_id": job_id}

                # Render template if using one
                if job.template_id:
                    rendered_content, error = template_service.render_template_for_send(
                        template_id=job.template_id,
                        variables=delivery.variables
                    )
                    if error:
                        raise ValueError(f"Template rendering failed: {error}")
                    body = rendered_content
                else:
                    body = job.body

                # Send email
                success, error = mail_service.send_raw_email(
                    user_id=job.user_id,
                    to_email=delivery.recipient,
                    subject=job.subject,
                    body=body,
                    smtp_config=job.smtp_config
                )

                # Update delivery status
                delivery.last_attempt = datetime.now(timezone.utc)
                delivery.attempts += 1

                if success:
                    delivery.status = EmailDelivery.STATUS_SENT
                    job.success_count += 1
                else:
                    delivery.status = EmailDelivery.STATUS_FAILED
                    delivery.error_message = error
                    job.failure_count += 1

                db.session.commit()

                # Notify delivery status via webhook
                webhook_service.notify_delivery_status(
                    delivery.id,
                    'sent' if success else 'failed'
                )

            except Exception as e:
                delivery.status = EmailDelivery.STATUS_FAILED
                delivery.error_message = str(e)
                delivery.last_attempt = datetime.now(timezone.utc)
                delivery.attempts += 1
                job.failure_count += 1

                db.session.commit()
                webhook_service.notify_delivery_status(delivery.id, 'failed')

        # Chain to next batch if there are more pending deliveries
        remaining = EmailDelivery.query.filter_by(
            job_id=job_id,
            status=EmailDelivery.STATUS_PENDING
        ).count()

        if remaining > 0:
            process_email_batch.delay(job_id, batch_size)

        return {
            "status": "processing",
            "job_id": job_id,
            "batch_processed": len(deliveries),
            "remaining": remaining
        }

    except Exception as e:
        # Log error and retry
        current_app.logger.error(
            f"Batch email error for job {job_id}: {str(e)}")
        raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))


@shared_task(bind=True, max_retries=3)
def send_internal_email_task(
    self,
    to_email: str,
    subject: str,
    body: str
) -> bool:
    """Send internal system emails using default system SMTP."""
    try:
        logger.info(
            f"Starting to send internal email to {to_email}")
        logger.debug("SMTP Configuration:")
        logger.debug(
            f"Host: {current_app.config.get('SYSTEM_SMTP_HOST')}")
        logger.debug(
            f"Port: {current_app.config.get('SYSTEM_SMTP_PORT')}")
        logger.debug(
            f"Username: {current_app.config.get('SYSTEM_SMTP_USERNAME')}")
        logger.debug(
            f"From Email: {current_app.config.get('SYSTEM_SMTP_FROM_EMAIL')}")
        logger.debug(
            f"Use TLS: {current_app.config.get('SYSTEM_SMTP_USE_TLS')}")

        logger.info(f"Sending internal email to {to_email}")

        # Get system SMTP configuration from environment
        smtp_config = SMTPConfiguration(
            host=current_app.config['SYSTEM_SMTP_HOST'],
            port=int(current_app.config['SYSTEM_SMTP_PORT']),
            username=current_app.config['SYSTEM_SMTP_USERNAME'],
            password=current_app.config['SYSTEM_SMTP_PASSWORD'],
            use_tls=str(
                current_app.config['SYSTEM_SMTP_USE_TLS']).lower() == 'true',
            from_email=current_app.config['SYSTEM_SMTP_FROM_EMAIL']
        )

        logger.debug(f"Using SMTP config: {
            smtp_config.host}:{smtp_config.port}")

        # Create MailService instance
        mail_service = MailService()
        success, error = mail_service.send_raw_email(
            user_id=None,  # System email, no user
            to_email=to_email,
            subject=subject,
            body=body,
            smtp_config=smtp_config,
            is_system_email=True
        )

        if not success:
            logger.error(f"Failed to send internal email: {error}")
            raise self.retry(exc=Exception(error), countdown=60)

        logger.info(f"Successfully sent internal email to {to_email}")
        return True

    except Exception as e:
        if 'current_app' in locals():
            logger.error(f"Internal email error: {str(e)}")
            logger.exception("Full traceback:")
        raise self.retry(exc=e, countdown=60)


@shared_task
def clean_up_stale_jobs():
    """Clean up stale jobs that have been stopped or paused."""
    job_control = JobControlService()
    job_control.clean_up_stale_jobs()
