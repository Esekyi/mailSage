from celery import shared_task
from typing import Optional
from app.services.mail_service import MailService
from app.models import EmailJob, EmailDelivery, SMTPConfiguration
from app.extensions import db
from datetime import datetime, timezone
from flask import current_app


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,  # 1 minute
    rate_limit='60/m'  # max 60 emails per minute
)
def send_single_email_task(
    self,
    user_id: int,
    to_email: str,
    subject: str,
    body: str,
    smtp_config_id: Optional[int] = None
) -> bool:
    """Send a single email using Celery."""
    try:
        # Get SMTP configuration
        smtp_config = None
        if smtp_config_id:
            smtp_config = SMTPConfiguration.query.get(smtp_config_id)

        success, error = MailService.send_email(
            user_id=user_id,
            to_email=to_email,
            subject=subject,
            body=body,
            smtp_config=smtp_config
        )

        if not success:
            raise Exception(error)

        return True

    except Exception as e:
        # Retry the task if it fails
        self.retry(exc=e)


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=300,  # 5 minutes
    rate_limit='10/m'  # max 10 batch jobs per minute
)
def send_batch_emails_task(
    self,
    job_id: int,
    batch_size: int = 50
) -> bool:
    """Process batch email sending."""
    try:
        job = EmailJob.query.get(job_id)
        if not job:
            raise ValueError(f"Email job {job_id} not found")

        # Get pending deliveries for this job
        deliveries = EmailDelivery.query.filter(
            job_id=job_id,
            status='pending'
        ).limit(batch_size).all()

        if not deliveries:
            # No more pending deliveries, mark job as completed
            job.status = EmailJob.STATUS_COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            db.session.commit()
            return True

        # Get SMTP configuration
        smtp_config = None
        if job.smtp_config_id:
            smtp_config = SMTPConfiguration.query.get(job.smtp_config_id)

        # Process each delivery
        for delivery in deliveries:
            try:
                success, error = MailService.send_email(
                    user_id=job.user_id,
                    to_email=delivery.recipient,
                    subject=job.subject,
                    body=job.body,
                    smtp_config=smtp_config
                )

                if success:
                    delivery.status = 'sent'
                    job.success_count += 1
                else:
                    delivery.status = 'failed'
                    delivery.error_message = error
                    job.failure_count += 1

                delivery.last_attempt = datetime.now(timezone.utc)
                delivery.attempts += 1

            except Exception as e:
                delivery.status = 'failed'
                delivery.error_message = str(e)
                delivery.last_attempt = datetime.now(timezone.utc)
                delivery.attempts += 1
                job.failure_count += 1

        db.session.commit()

        # Chain to next batch if there are more pending deliveries
        if EmailDelivery.query.filter_by(
                job_id=job_id,
                status='pending'
        ).count() > 0:
            send_batch_emails_task.delay(job_id, batch_size)

        return True

    except Exception as e:
        # Log error and retry
        current_app.logger.error(
            f"Batch email error for job {job_id}: {str(e)}")
        self.retry(exc=e)


@shared_task(bind=True, max_retries=3)
def send_internal_email_task(
    self,
    to_email: str,
    subject: str,
    body: str
) -> bool:
    """Send internal system emails using default system SMTP."""
    try:
        current_app.logger.info(
            f"Starting to send internal email to {to_email}")
        current_app.logger.debug("SMTP Configuration:")
        current_app.logger.debug(
            f"Host: {current_app.config.get('SYSTEM_SMTP_HOST')}")
        current_app.logger.debug(
            f"Port: {current_app.config.get('SYSTEM_SMTP_PORT')}")
        current_app.logger.debug(
            f"Username: {current_app.config.get('SYSTEM_SMTP_USERNAME')}")
        current_app.logger.debug(
            f"From Email: {current_app.config.get('SYSTEM_SMTP_FROM_EMAIL')}")
        current_app.logger.debug(
            f"Use TLS: {current_app.config.get('SYSTEM_SMTP_USE_TLS')}")

        current_app.logger.info(f"Sending internal email to {to_email}")

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

        current_app.logger.debug(f"Using SMTP config: {
            smtp_config.host}:{smtp_config.port}")

        success, error = MailService.send_email(
            user_id=None,  # System email, no user
            to_email=to_email,
            subject=subject,
            body=body,
            smtp_config=smtp_config
        )

        if not success:
            current_app.logger.error(f"Failed to send internal email: {error}")
            raise self.retry(exc=Exception(error), countdown=60)

        current_app.logger.info(
            f"Successfully sent internal email to {to_email}")
        return True

    except Exception as e:
        if 'current_app' in locals():
            current_app.logger.error(f"Internal email error: {str(e)}")
            current_app.logger.exception("Full traceback:")
        raise self.retry(exc=e, countdown=60)
