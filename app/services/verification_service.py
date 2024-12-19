from datetime import datetime, timezone, timedelta
from typing import Optional
import secrets
from flask import current_app, render_template
from app.extensions import db
from app.models.user import User
from app.services.mail_service import MailService


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

        user.email_verified = True
        user.verification_token = None
        user.verification_token_expires = None
        db.session.commit()

        return user

    @staticmethod
    def send_verification_email(user: User) -> bool:
        """Send verification email to user."""
        token = VerificationService.generate_verification_token(user)
        verification_url = f"{
            current_app.config['FRONTEND_URL']}/verify-email?token={token}"

        try:
            mail_service = MailService()
            mail_service.send_email(
                recipient=user.email,
                subject="Verify Your Email Address",
                html_body=render_template(
                    'email/verify_email.html',
                    verification_url=verification_url,
                    user=user
                )
            )
            return True
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(
                f"Failed to send verification email: {str(e)}")
            return False

    @staticmethod
    def resend_verification_email(user: User) -> bool:
        """Resend verification email to user."""
        if user.email_verified:
            raise ValueError("Email already verified")

        return VerificationService.send_verification_email(user)
