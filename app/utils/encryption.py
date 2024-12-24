from cryptography.fernet import Fernet
from flask import current_app
from base64 import b64encode, b64decode


def generate_key():
    """Generate a new Fernet encryption key."""
    return Fernet.generate_key()


def get_encryption_key():
    """Get or generate the encryption key."""
    key = current_app.config.get('ENCRYPTION_KEY')
    if not key:
        # If no key exists, generate one
        # Note: In production, this should be set via environment variable
        # and remain consistent across application restarts - me to myself lol
        key = generate_key()
        current_app.config['ENCRYPTION_KEY'] = key
    return key


def encrypt_value(value: str) -> str:
    """
    Encrypt a string value using Fernet symmetric encryption.

    Args:
        value: String to encrypt

    Returns:
        Base64 encoded encrypted string
    """
    if not value:
        return value

    try:
        f = Fernet(get_encryption_key())
        encrypted = f.encrypt(value.encode())
        return b64encode(encrypted).decode()

    except Exception as e:
        current_app.logger.error(f"Encryption error: {str(e)}")
        raise ValueError("Failed to encrypt value") from e


def decrypt_value(encrypted_value: str) -> str:
    """
    Decrypt a Fernet-encrypted string value.

    Args:
        encrypted_value: Base64 encoded encrypted string

    Returns:
        Decrypted string
    """
    if not encrypted_value:
        return encrypted_value

    try:
        f = Fernet(get_encryption_key())
        decrypted = f.decrypt(b64decode(encrypted_value))
        return decrypted.decode()
    except Exception as e:
        current_app.logger.error(f"Decryption error: {str(e)}")
        raise ValueError("Failed to decrypt value") from e
