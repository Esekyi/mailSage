from datetime import datetime, timezone, timedelta
from typing import Optional
import secrets
from flask import current_app, render_template
from app.extensions import db
from app.models.user import User
from app.services.mail_service import MailService
from app.tasks.email_tasks import send_internal_email_task


class VerificationService:
    @staticmethod
    def generate_verification_token(user: User) -> str:
        """Generate a new verification token for a user."""
        token = secrets.token_urlsafe(32)
        user.verification_token = token
        user.verification_token_expires = datetime.now(
            timezone.utc) + timedelta(hours=24)
        db.session.commit()
        return token

    @staticmethod
    def verify_email(token: str) -> Optional[User]:
        """Verify a user's email using the verification token."""
        user = User.query.filter_by(
            verification_token=token,
            email_verified=False
        ).first()

        if not user or not user.verification_token_expires:
            return None

        if user.verification_token_expires < datetime.now(timezone.utc):
            return None

        try:
            user.email_verified = True
            user.verification_token = None
            user.verification_token_expires = None
            db.session.commit()

            return user
        except Exception as e:
            current_app.logger.error(
                f"Failed to verify email: {str(e)}")
            db.session.rollback()
            return None

    @staticmethod
    def send_verification_email(user: User) -> bool:
        """Send verification email to user."""
        try:
            current_app.logger.info(
                f"Generating verification token for user {user.email}")
            token = VerificationService.generate_verification_token(user)

            verification_url = f"{
                current_app.config[
                    'FRONTEND_URL']}/verify-email?token={token}"

            current_app.logger.debug(f"Verification URL: {verification_url}")

            # Send the email using Celery task
            task = send_internal_email_task.delay(
                to_email=user.email,
                subject="Verify Your Email",
                body=render_template(
                    'email/verify_email.html',
                    verification_url=verification_url,
                    user=user
                )
            )

            # Log that we've queued the task
            current_app.logger.info(
                f"Email verification task queued with ID: {task.id}")

            # Don't wait for the result, just confirm it was queued
            return True

        except Exception as e:
            current_app.logger.error(
                f"Failed to send verification email: {str(e)}")
            current_app.logger.exception("Full traceback:")
            return False

    @staticmethod
    def resend_verification_email(user: User) -> bool:
        """Resend verification email to user."""

        try:
            if user.email_verified:
                current_app.logger.warning(
                    f"Attempted to resend verification to already verified email: {user.email}")
                raise ValueError("Email already verified")

            # Clear any existing verification token
            user.verification_token = None
            user.verification_token_expires = None
            db.session.commit()

            # Send new verification email
            return VerificationService.send_verification_email(user)

        except Exception as e:
            current_app.logger.error(
                f"Error resending verification email: {str(e)}")
            return False
