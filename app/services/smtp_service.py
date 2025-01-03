from typing import Dict, Optional, Tuple
import smtplib
from datetime import datetime, timezone
from ssl import SSLError
from flask import current_app
from app.utils.encryption import encrypt_value, decrypt_value
from app.extensions import db
from app.models import SMTPConfiguration, User
import socket
import ssl
from app.utils.roles import ROLE_CONFIGURATIONS, ResourceLimit

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
            current_app.logger.info(f"Testing SMTP connection to {config['host']}:{
                                    config['port']} with username: {config['username']}")

            # First try to resolve the hostname
            try:
                with smtplib.SMTP(timeout=5) as smtp:
                    smtp.connect(config['host'], int(config['port']))
            except (ConnectionRefusedError, socket.gaierror) as e:
                return False, f"Could not connect to SMTP server: {str(e)}"

            # Now try full connection with authentication
            with smtplib.SMTP(config['host'], int(config['port']), timeout=10) as smtp:
                # Get server info
                server_info = smtp.ehlo()
                if not server_info[0] in [250, 220, 200]:
                    return False, f"SMTP server rejected connection: {server_info}"

                # Check TLS support
                if config.get('use_tls', True):
                    if not smtp.has_extn('STARTTLS'):
                        return False, "Server does not support TLS but TLS is required"
                    try:
                        smtp.starttls()
                        # After TLS, need to EHLO again
                        smtp.ehlo()
                    except ssl.SSLError as e:
                        return False, f"TLS error: {str(e)}"

                # Try authentication with original password
                try:
                    smtp.login(config['username'], config['password'])
                except smtplib.SMTPAuthenticationError as e:
                    return False, f"Authentication failed: {str(e)}"

                # Check if we can send from the specified email
                if 'from_email' in config:
                    try:
                        smtp.verify(config['from_email'])
                    except smtplib.SMTPException as e:
                        current_app.logger.warning(
                            f"From email verification warning: {str(e)}")

            current_app.logger.info(
                "SMTP configuration validated successfully")
            return True, None

        except smtplib.SMTPConnectError as e:
            return False, f"Connection error: {str(e)}"
        except smtplib.SMTPServerDisconnected as e:
            return False, f"Server disconnected unexpectedly: {str(e)}"
        except smtplib.SMTPResponseException as e:
            return False, f"SMTP error {e.smtp_code}: {e.smtp_error}"
        except smtplib.SMTPException as e:
            return False, f"SMTP error: {str(e)}"
        except socket.timeout:
            return False, "Connection timed out"
        except SSLError as e:
            return False, f"SSL/TLS error: {str(e)}"
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

            daily_limit = ROLE_CONFIGURATIONS[user.role]['limits'][
                ResourceLimit.DAILY_EMAILS.value]

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
                daily_limit=daily_limit
            )

            db.session.add(config)

            # Add notification before creation
            user = User.query.get(user_id)
            user.add_notification(
                title="SMTP Configuration Created",
                message=f"SMTP configuration {config.name} has been created",
                type="success",
                category="smtp",
                meta_data={"config_id": config.id}
            )
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

            # Add notification before deletion
            user = User.query.get(config.user_id)
            user.add_notification(
                title="SMTP Configuration Updated",
                message=f"SMTP configuration {config.name} has been updated",
                type="success",
                category="smtp",
                meta_data={"config_id": config.id}
            )
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

            # Add notification before deletion
            user = User.query.get(config.user_id)
            user.add_notification(
                title="SMTP Configuration Deleted",
                message=f"SMTP configuration {config.name} has been deleted",
                type="warning",
                category="smtp",
                meta_data={"config_id": config.id}
            )

            return True, None

        except Exception as e:
            current_app.logger.error(f"Error deleting SMTP config: {str(e)}")
            return False, f"Failed to delete SMTP configuration: {str(e)}"

    @staticmethod
    def test_connection(config: SMTPConfiguration) -> Tuple[bool, Optional[str]]:
        """Test SMTP configuration by performing comprehensive connection tests."""
        try:
            current_app.logger.info(
                f"Starting comprehensive SMTP test for {config.name}")

            # Check and reset daily counter if needed
            if config.needs_daily_reset():
                current_app.logger.info("Resetting daily email counter")
                config.emails_sent_today = 0
                config.last_reset_date = datetime.now(timezone.utc).date()
                db.session.commit()

            # Step 1: Basic Connection Test
            current_app.logger.info("Step 1: Testing basic connection...")
            with smtplib.SMTP(timeout=5) as smtp:
                connect_response = smtp.connect(config.host, config.port)
                if not connect_response[0] in [220, 250]:
                    return False, f"Connection failed: Server response {connect_response}"

            # Step 2: Full Connection with Authentication
            current_app.logger.info("Step 2: Testing authentication...")
            with smtplib.SMTP(config.host, config.port, timeout=10) as smtp:
                # Get server info and capabilities
                server_info = smtp.ehlo()
                if not server_info[0] in [250, 220]:
                    return False, f"EHLO failed: {server_info}"

                # Log server capabilities
                capabilities = smtp.esmtp_features
                current_app.logger.info(f"Server capabilities: {capabilities}")

                # Check and setup TLS if enabled
                if config.use_tls:
                    if not smtp.has_extn('STARTTLS'):
                        return False, "Server does not support STARTTLS"

                    current_app.logger.info("Initiating TLS connection...")
                    smtp.starttls()
                    # Need to EHLO again after STARTTLS
                    smtp.ehlo()

                # Test authentication
                current_app.logger.info("Testing authentication...")
                try:
                    smtp.login(config.username, decrypt_value(config.password))
                except smtplib.SMTPAuthenticationError as e:
                    return False, f"Authentication failed: {str(e)}"

                # Verify 'from' email if set
                if config.from_email:
                    current_app.logger.info(
                        f"Verifying from_email: {config.from_email}")
                    try:
                        smtp.verify(config.from_email)
                    except smtplib.SMTPException as e:
                        current_app.logger.warning(
                            f"From email verification warning: {str(e)}")

                # Test message size limits if server provides them
                size_limit = capabilities.get('size', 0)
                if size_limit:
                    current_app.logger.info(
                        f"Server message size limit: {size_limit}")

            # Update test timestamp
            config.last_test_at = datetime.now(timezone.utc)
            config.failure_count = 0  # Reset failure count after successful test
            db.session.commit()

            # Add success notification
            user = User.query.get(config.user_id)
            user.add_notification(
                title="SMTP Configuration Tested",
                message=f"SMTP configuration {
                    config.name} has been tested successfully. Server supports: "
                f"{'TLS, ' if config.use_tls else ''}"
                f"{'SIZE limit: ' + str(size_limit)
                   if size_limit else 'No size limit'}"
                f"{', VERIFY' if config.from_email else ''}",
                type="success",
                category="smtp",
                meta_data={
                    "config_id": config.id,
                    "capabilities": list(capabilities.keys()) if capabilities else []
                }
            )

            current_app.logger.info("SMTP test completed successfully")
            return True, None

        except smtplib.SMTPConnectError as e:
            return False, f"Connection error: {str(e)}"
        except smtplib.SMTPServerDisconnected as e:
            return False, f"Server disconnected unexpectedly: {str(e)}"
        except smtplib.SMTPResponseException as e:
            return False, f"SMTP error {e.smtp_code}: {e.smtp_error}"
        except smtplib.SMTPException as e:
            return False, f"SMTP error: {str(e)}"
        except socket.timeout:
            return False, "Connection timed out"
        except SSLError as e:
            return False, f"SSL/TLS error: {str(e)}"
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Test connection error: {str(e)}")
            return False, f"Failed to test SMTP connection: {str(e)}"
