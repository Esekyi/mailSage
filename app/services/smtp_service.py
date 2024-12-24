from typing import Dict, Optional, Tuple
import smtplib
from datetime import datetime, timezone
from ssl import SSLError
from flask import current_app
from app.utils.encryption import encrypt_value, decrypt_value
from app.extensions import db
from app.models.smtp import SMTPConfiguration


class SMTPService:
    """Service for managing SMTP configurations and connections."""

    @staticmethod
    def validate_smtp_config(config: Dict) -> Tuple[bool, Optional[str]]:
        """
        Validate SMTP configuration by attempting to establish a connection.

        Args:
            config: Dict containing SMTP configuration (host, port, username,
            password, use_tls)

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """

        require_fields = ['host', 'port', 'username', 'password']
        if not all(field in config for field in require_fields):
            return False, "Missing required SMTP configuration fields"

        try:
            with smtplib.SMTP(config['host'], int(config['port']),
                              timeout=10) as smtp:

                if config.get('use_tls', True):
                    smtp.starttls()
                smtp.login(config['username'], config['password'])
            return True, None

        except (smtplib.SMTPAuthenticationError):
            return False, "Invalid SMTP credentials"
        except (smtplib.SMTPConnectError, ConnectionResetError):
            return False, "Could not connect to SMTP server"
        except SSLError:
            return False, "SSL/TLS error - check your port and TLS settings"
        except Exception as e:
            current_app.logger.error(f"SMTP validation error: {str(e)}")
            return False, f"SMTP configuration error: {str(e)}"

    @staticmethod
    def create_config(user_id: int, config_data: Dict) -> Tuple[
            Optional[SMTPConfiguration], Optional[str]]:
        """
        Create new encrypted SMTP configuration.

        Args:
            user: User model instance
            config: Dict containing SMTP configuration

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            # If this is set as default, unset any existing default
            if config_data.get('is_default'):
                SMTPConfiguration.query.filter_by(
                    user_id=user_id,
                    is_default=True
                ).update({'is_default': False})

            # Encrypt sensitive fields
            config = SMTPConfiguration(
                user_id=user_id,
                name=config_data['name'],
                host=config_data['host'],
                port=int(config_data['port']),
                username=config_data['username'],
                password=encrypt_value(config_data['password']),
                use_tls=config_data.get('use_tls', True),
                from_email=config_data.get('from_email'),
                is_default=config_data.get('is_default', False),
                daily_limit=config_data.get('daily_limit', 2000)
            )

            db.session.add(config)
            db.session.commit()

            return config, None

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error saving SMTP config: {str(e)}")
            return False, f"Failed to save SMTP configuration: {str(e)}"

    @staticmethod
    def update_config(config: SMTPConfiguration, updates: Dict) -> Tuple[
        bool, Optional[str]
    ]:
        """
        Update existing SMTP configuration.

        Args:
            config: SMTPConfiguration model instance
            updates: Dict containing fields to update

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """
        try:
            if updates.get('is_default') and not config.is_default:
                SMTPConfiguration.query.filter_by(
                    user_id=config.user_id,
                    is_default=True
                ).update({'is_default': False})

            for key, value in updates.items():
                if key == 'password':
                    setattr(config, key, encrypt_value(value))
                elif key in ['name', 'host', 'port', 'username',
                             'use_tls', 'from_email', 'is_default',
                             'daily_limit']:
                    setattr(config, key, value)

            db.session.commit()
            return True, None

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error updating SMTP config: {str(e)}")
            return False, f"Failed to update SMTP configuration: {str(e)}"

    @staticmethod
    def delete_config(config: SMTPConfiguration) -> Tuple[bool, Optional[str]]:
        """
        Delete an existing SMTP configuration.

        Args:
            config: SMTPConfiguration model instance

        Returns:
            Tuple of (success: bool, error_message: Optional[str])
        """

        try:
            config.is_active = False

            if config.is_default:
                # Find another config to make default
                new_default = SMTPConfiguration.query.filter_by(
                    user_id=config.user_id,
                    is_active=True
                ).first()

                if new_default:
                    new_default.is_default = True

            db.session.commit()
            return True, None

        except Exception as e:
            current_app.logger.error(f"Error deleting SMTP config: {str(e)}")
            return False, f"Failed to delete SMTP configuration: {str(e)}"

    @staticmethod
    def test_connection(config: SMTPConfiguration
                        ) -> Tuple[bool, Optional[str]]:
        """Test SMTP configuration by sending a test email."""

        try:
            with smtplib.SMTP(config.host, config.port, timeout=10) as smtp:
                if config.use_tls:
                    smtp.starttls()
                smtp.login(config.username, decrypt_value(config.password))

            config.last_test_at = datetime.now(timezone.utc)
            db.session.commit()
            return True, None

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Test connection error: {str(e)}")
            return False, f"Failed to test SMTP connection: {str(e)}"
