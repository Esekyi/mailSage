from typing import Optional, Tuple, List, Dict, Any
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.extensions import db
from app.models import (
    SMTPConfiguration, User, Template,
    EmailDelivery, EmailJob
)
from app.utils.encryption import decrypt_value
from flask import current_app
from datetime import datetime, timezone
import sqlalchemy.exc
from app.services.template_service import TemplateRenderService
from app.services.smtp_service import SMTPService
from app.utils.roles import ROLE_CONFIGURATIONS, ResourceLimit
from app.utils.logging import logger
import uuid


class MailService:
    """Core service for email sending operations."""

    def __init__(self):
        self.template_renderer = TemplateRenderService()

    @staticmethod
    def get_smtp_config(user_id: int) -> Optional[SMTPConfiguration]:
        """Get the default or first active SMTP configuration for a user."""
        return SMTPConfiguration.query.filter_by(
            user_id=user_id,
            is_active=True,
            is_default=True
        ).first() or SMTPConfiguration.query.filter_by(
            user_id=user_id,
            is_active=True
        ).first()

    def send_raw_email(
        self,
        user_id: Optional[int],
        to_email: str,
        subject: str,
        body: str,
        smtp_config: Optional[SMTPConfiguration] = None,
        is_system_email: bool = False
    ) -> Tuple[bool, Optional[str]]:
        """
        Send a raw email (no template).
        Core method for sending both system and user emails.
        """
        try:
            logger.info(
                f"Starting email send process to {to_email}")

            # Handle system vs user email configuration
            if not is_system_email:
                user = User.query.get(user_id)
                if not user:
                    return False, "User not found"

                # Get user's SMTP config if not provided
                if not smtp_config:
                    smtp_config = self.get_smtp_config(user_id)
                    if not smtp_config:
                        return False, "No active SMTP configuration found"

                # Lock the SMTP config for update to prevent race conditions
                smtp_config = db.session.query(
                    SMTPConfiguration).with_for_update().get(smtp_config.id)

                logger.info(f"Current SMTP stats - emails_sent_today: {
                                        smtp_config.emails_sent_today}, last_reset_date: {smtp_config.last_reset_date}")
                logger.info(f"Current UTC date: {
                                        datetime.now(timezone.utc).date()}")

                # Check daily limits for user SMTPs
                if smtp_config.needs_daily_reset():
                    logger.info("Resetting daily counter to 0")
                    smtp_config.emails_sent_today = 0
                    smtp_config.last_reset_date = datetime.now(
                        timezone.utc).date()
                elif not smtp_config.can_send_emails():
                    return False, f"Daily email limit ({smtp_config.daily_limit}) reached"

                from_email = smtp_config.from_email or user.email

            else:
                # System email - must provide smtp_config
                if not smtp_config:
                    return False, "SMTP configuration required for system emails"

                from_email = smtp_config.from_email

            # Log SMTP configuration (excluding password)
            logger.debug(f"Using SMTP Configuration:")
            logger.debug(f"Host: {smtp_config.host}")
            logger.debug(f"Port: {smtp_config.port}")
            logger.debug(f"Username: {smtp_config.username}")
            logger.debug(f"From Email: {from_email}")
            logger.debug(f"Use TLS: {smtp_config.use_tls}")

            # Prepare email message
            msg = MIMEMultipart()

            # If from_email formatting
            if '<' in from_email and '>' in from_email:
                msg['From'] = from_email
                current_app.logger.debug(
                    f"Using formatted from_email: {from_email}")
            else:
                display_name = "Mailsage Support" if is_system_email else None
                from_header = f"{display_name} <{from_email}>" if display_name else from_email
                msg['From'] = from_header
                current_app.logger.debug(
                    f"Constructed from_email: {from_header}")

            msg['To'] = to_email
            msg['Subject'] = subject
            msg.attach(MIMEText(body, 'html'))

            # Attempt SMTP connection
            current_app.logger.info("Establishing SMTP connection...")
            with smtplib.SMTP(
                smtp_config.host,
                smtp_config.port,
                timeout=30
            ) as smtp:
                if smtp_config.use_tls:
                    current_app.logger.debug("Starting TLS...")
                    smtp.starttls()

                current_app.logger.debug("Attempting SMTP login...")
                # For user SMTP, decrypt the password. For system SMTP, use as is.
                password = smtp_config.password if is_system_email else decrypt_value(
                    smtp_config.password)
                if not password:
                    raise ValueError("Invalid SMTP password")

                smtp.login(
                    smtp_config.username,
                    password
                )
                current_app.logger.debug("Sending email message...")
                smtp.send_message(msg)

                current_app.logger.info("Email sent successfully")

                # Update stats only for user SMTPs
                if not is_system_email:
                    current_app.logger.info(
                        f"Before increment - emails_sent_today: {smtp_config.emails_sent_today}")
                    smtp_config.emails_sent_today += 1
                    smtp_config.last_used_at = datetime.now(timezone.utc)
                    smtp_config.failure_count = 0
                    current_app.logger.info(
                        f"After increment - emails_sent_today: {smtp_config.emails_sent_today}")
                    db.session.commit()
                    current_app.logger.info(
                        "Committed counter update to database")
                    current_app.logger.debug("Updated user SMTP statistics")

                return True, None

        except Exception as e:
            error_msg = self._handle_email_error(e, smtp_config)
            return False, error_msg

    def create_email_job(
        self,
        user_id: int,
        recipients: List[Dict[str, Any]],
        subject: str,
        body: Optional[str] = None,
        template_id: Optional[int] = None,
        smtp_id: Optional[int] = None,
        campaign_id: Optional[str] = None
    ) -> Tuple[EmailJob, Optional[str]]:
        """Create an email job for either templated or raw emails."""
        try:
            # Generate tracking ID for the job
            tracking_id = str(uuid.uuid4())

            # Create job record
            job = EmailJob(
                user_id=user_id,
                template_id=template_id,
                subject=subject,
                body=body,  # Only for non-templated emails
                status='pending',
                recipient_count=len(recipients),
                smtp_config_id=smtp_id,
                campaign_id=campaign_id,
                tracking_id=tracking_id,
                meta_data={
                    'smtp_strategy': 'specific' if smtp_id else 'default',
                    'is_templated': template_id is not None
                }
            )
            db.session.add(job)
            db.session.flush()

            # Create delivery records
            deliveries = []
            for recipient in recipients:
                delivery = EmailDelivery(
                    job_id=job.id,
                    recipient=recipient['email'],
                    variables=recipient.get(
                        'variables', {}) if template_id else None,
                    status='pending'
                )
                deliveries.append(delivery)

            db.session.bulk_save_objects(deliveries)
            db.session.commit()

            return job, None

        except Exception as e:
            db.session.rollback()
            return None, f"Failed to create email job: {str(e)}"

    def validate_sending_quota(
            self,
            user_id: int,
            recipient_count: int
    ) -> Tuple[bool, Optional[str]]:
        """Validate if user has enough quota to send emails."""
        user = User.query.get(user_id)
        if not user:
            return False, "User not found"

        daily_limit = ROLE_CONFIGURATIONS[user.role]['limits'][
            ResourceLimit.DAILY_EMAILS.value]
        if daily_limit == -1:  # unlimited
            return True, None

        today_start = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        sent_today = EmailJob.query.filter(
            EmailJob.user_id == user_id,
            EmailJob.created_at >= today_start
        ).with_entities(db.func.sum(EmailJob.recipient_count)).scalar() or 0

        if sent_today + recipient_count > daily_limit:
            remaining = max(0, daily_limit - sent_today)
            return False, f"Daily sending limit exceeded. Remaining quota: {remaining}"

        return True, None

    def _handle_email_error(
        self,
        error: Exception,
        smtp_config: Optional[SMTPConfiguration]
    ) -> str:
        """Handle different types of email sending errors."""
        if isinstance(error, smtplib.SMTPAuthenticationError):
            error_msg = "SMTP Authentication failed"
        elif isinstance(error, smtplib.SMTPConnectError):
            error_msg = "Failed to connect to SMTP server"
        elif isinstance(error, smtplib.SMTPException):
            error_msg = f"SMTP error occurred: {str(error)}"
        elif isinstance(error, sqlalchemy.exc.SQLAlchemyError):
            db.session.rollback()
            if smtp_config:
                try:
                    smtp_config.failure_count += 1
                    db.session.commit()
                except:
                    db.session.rollback()
            error_msg = "Database error occurred"
        else:
            error_msg = f"Unexpected error: {str(error)}"
            logger.exception("Full traceback:")

        logger.error(f"{error_msg}: {str(error)}")
        return error_msg


    @staticmethod
    def send_test_email(
        smtp_config: SMTPConfiguration
    ) -> Tuple[bool, Optional[str]]:
        """Send a test email using specific SMTP configuration."""
        service = MailService()

        return service.send_raw_email(
            user_id=smtp_config.user_id,
            to_email=smtp_config.from_email,
            subject="MailSage SMTP Test",
            body="Your SMTP configuration is working correctly!",
            smtp_config=smtp_config
        )
