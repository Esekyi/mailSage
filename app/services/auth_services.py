from datetime import datetime, timedelta, timezone
from flask import request
from typing import Optional, Tuple
import secrets
import hashlib
from flask_jwt_extended import create_access_token, create_refresh_token
from app.models import User
from app.extensions import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask import current_app, render_template
from app.services.mail_service import MailService
from app.services.verification_service import VerificationService


class AuthenticationService:
    @staticmethod
    def register_user(email: str, password: str, name: str,
                      role: str = 'free') -> Tuple[User, str]:
        """Register a new user and return the user object with access token."""
        db.session.begin_nested()  # Create a savepoint

        try:
            # verify if user already exists
            existing_user = User.query.filter_by(email=email).first()

            if existing_user:
                db.session.rollback()
                raise ValueError('Email already registered')

            # create new user
            user = User(
                email=email,
                password_hash=generate_password_hash(password),
                name=name,
                role=role,
                is_active=True,
                email_verified=False
            )

            db.session.add(user)
            db.session.flush()  # Trigger the audit log

            # Send verification email
            if not VerificationService.send_verification_email(user):
                db.session.rollback()
                raise ValueError(
                    "Registration successful but failed to send verification email. Please try resending the verification email.")

            # Add notification
            user.add_notification(
                title="Welcome to Mailsage!",
                message=f"You've successfully registered an account. Check documentation for next steps.",
                type="success",
                category="user",
                meta_data={"user_id": user.id}
            )

            db.session.commit()  # Commit the transaction

            # create access token
            access_token = create_access_token(identity=str(user.id))

            return user, access_token
        except Exception as e:
            db.session.rollback()  # Roll back the entire transaction
            current_app.logger.error(f"Registration error: {str(e)}")
            raise e  # Re-raise the exception to be handled by the route/view

    @staticmethod
    def generate_tokens(user_id: int) -> dict:
        """Generate both access and refresh tokens."""
        access_token = create_access_token(identity=str(user_id))
        refresh_token = create_refresh_token(identity=str(user_id))

        # Store refresh token in database
        user = db.session.get(User, user_id)
        hashed_refresh_token = hashlib.sha256(
            refresh_token.encode()
        ).hexdigest()
        user.refresh_token = hashed_refresh_token
        user.refresh_token_expires = datetime.now(
            timezone.utc) + timedelta(days=30)
        db.session.commit()

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer"
        }

    @staticmethod
    def refresh_access_token(refresh_token: str) -> dict:
        """Generate new access token using refresh token."""
        hashed_refresh_token = hashlib.sha256(
            refresh_token.encode()
        ).hexdigest()

        user = User.query.filter_by(
            refresh_token=hashed_refresh_token,
            is_active=True
        ).first()

        if not user or not user.refresh_token_expires:
            raise ValueError('Invalid refresh token')

        if user.refresh_token_expires < datetime.now(timezone.utc):
            user.refresh_token = None
            user.refresh_token_expires = None
            db.session.commit()
            raise ValueError('Refresh token expired')

        tokens = AuthenticationService.generate_tokens(user.id)

        return tokens

    @staticmethod
    def authenticate_user(email: str, password: str) -> Tuple[User, str]:
        """Authenticate user and return user object with access token."""
        user = User.query.filter_by(email=email, is_active=True).first()

        if not user:
            raise ValueError('Invalid email or password')

        if not user.email_verified:
            raise ValueError('Email not verified. Please verify your email before logging in.')

        if not check_password_hash(user.password_hash, password):
            raise ValueError('Invalid email or password')

        # create access token
        tokens = AuthenticationService.generate_tokens(user.id)

        # Add notification
        user.add_notification(
            title="Activity: Login",
            message=f"Your account was accessed from {request.remote_addr}. If this was not you, please reset your password.",
            type="security",
            category="user",
            meta_data={"user_id": user.id}
        )

        return user, tokens

    @staticmethod
    def generate_password_reset_token(user: User) -> str:
        """Generate a password reset token and save it to the user."""
        token = secrets.token_urlsafe(32)
        user.reset_token = token
        user.reset_token_expires = datetime.now(
            timezone.utc
        ) + timedelta(hours=24)
        db.session.commit()

        return token

    @staticmethod
    def verify_reset_token(token: str) -> Optional[User]:
        """Verify a password reset token and return the user if valid."""
        user = User.query.filter_by(
            reset_token=token,
            is_active=True,
        ).first()

        if not user or not user.reset_token_expires:
            return None

        if user.reset_token_expires < datetime.now(timezone.utc):
            user.reset_token = None
            user.reset_token_expires = None
            db.session.commit()
            return None

        return user

    @staticmethod
    def reset_password(user: User, new_password: str) -> bool:
        """Reset a user's password and clear the reset token."""
        user.password_hash = generate_password_hash(new_password)
        user.reset_token = None
        user.reset_token_expires = None
        db.session.commit()
        return True

    @staticmethod
    def initiate_password_reset(email: str) -> bool:
        """Initiate the password reset process for a user."""
        user = User.query.filter_by(
            email=email,
            is_active=True
        ).first()

        if not user:
            # Return True even if the user does not exist
            # to prevent email enumeration
            return True

        token = AuthenticationService.generate_password_reset_token(user)

        # Send reset email
        reset_url = f"{
            current_app.config['FRONTEND_URL']}/reset-password?token={token}"

        try:
            mail_service = MailService()
            mail_service.send_raw_email(
                recipient=user.email,
                subject="Password Reset Request",
                html_content=render_template(
                    'email/password_reset.html',
                    reset_url=reset_url
                )
            )
            return True
        except Exception as e:
            current_app.logger.error(f"Failed to send reset email: {str(e)}")
            return False
