from typing import Optional, Tuple
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from app.extensions import db
from app.models import SMTPConfiguration, User
from app.utils.encryption import decrypt_value
from flask import current_app
from datetime import datetime, timezone
import sqlalchemy.exc


class MailService:
    """Service for sending emails using configured SMTP servers."""

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

    @staticmethod
    def send_email(
        user_id: Optional[int],
        to_email: str,
        subject: str,
        body: str,
        smtp_config: 'SMTPConfiguration'
    ) -> Tuple[bool, Optional[str]]:
        """Send an email using user's SMTP configuration or system
        SMTP configuration.
        For system emails, pass user_id=None and provide smtp_config.
        """
        try:
            current_app.logger.info(
                f"Starting email send process to {to_email}")

            # Determine if this is a system email
            is_system_email = user_id is None

            # Handle user emails
            if not is_system_email:
                user = User.query.get(user_id)
                if not user:
                    return False, "User not found"

                # Get user's SMTP config if not provided
                if not smtp_config:
                    smtp_config = MailService.get_smtp_config(user_id)
                    if not smtp_config:
                        return False, "No active SMTP configuration found"

                # Check daily limits for user SMTPs
                if smtp_config.needs_daily_reset():
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
            current_app.logger.debug(f"Using SMTP Configuration:")
            current_app.logger.debug(f"Host: {smtp_config.host}")
            current_app.logger.debug(f"Port: {smtp_config.port}")
            current_app.logger.debug(f"Username: {smtp_config.username}")
            current_app.logger.debug(f"From Email: {from_email}")
            current_app.logger.debug(f"Use TLS: {smtp_config.use_tls}")

            # Prepare email message
            msg = MIMEMultipart()

            # If from_email formatting
            if '<' in from_email and '>' in from_email:
                msg['From'] = from_email
                current_app.logger.debug(
                    f"Using formatted from_email: {from_email}")
            else:
                display_name = "mailSage Support" if is_system_email else None
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
                    smtp_config.emails_sent_today += 1
                    smtp_config.last_used_at = datetime.now(timezone.utc)
                    smtp_config.failure_count = 0
                    db.session.commit()
                    current_app.logger.debug("Updated user SMTP statistics")

                return True, None

        except smtplib.SMTPAuthenticationError as e:
            error_msg = "SMTP Authentication failed"
            current_app.logger.error(f"{error_msg}: {str(e)}")
            return False, error_msg

        except smtplib.SMTPConnectError as e:
            error_msg = "Failed to connect to SMTP server"
            current_app.logger.error(f"{error_msg}: {str(e)}")
            return False, error_msg

        except smtplib.SMTPException as e:
            error_msg = f"SMTP error occurred: {str(e)}"
            current_app.logger.error(error_msg)
            return False, error_msg

        except sqlalchemy.exc.SQLAlchemyError as e:
            if user_id is not None:
                db.session.rollback()
                try:
                    smtp_config.failure_count += 1
                    db.session.commit()
                except:
                    db.session.rollback()
            error_msg = "Database error occurred"
            current_app.logger.error(f"{error_msg}: {str(e)}")
            return False, error_msg

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            current_app.logger.error(error_msg)
            # This logs the full stack trace
            current_app.logger.exception("Full traceback:")
            return False, error_msg

    @staticmethod
    def send_test_email(
            smtp_config: SMTPConfiguration) -> Tuple[bool, Optional[str]]:
        """Send a test email using specific SMTP configuration."""
        user = User.query.get(smtp_config.user_id)
        if not user:
            return False, "User not found"

        return MailService.send_email(
            user_id=user.id,
            to_email=user.email,
            subject="MailSage SMTP Test",
            body="Your SMTP configuration is working correctly!",
            smtp_config=smtp_config
        )
