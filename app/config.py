import os
from dotenv import load_dotenv
import logging
from datetime import timedelta

load_dotenv()


class Config:
    """Set Flask configuration vars from .env file."""
    SECRETE_KEY = os.getenv(
        'SECRETE_KEY', 'Supersecret-tiny-littel-bit-secret-key')
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-secret-key')
    FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=1)
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        'postgresql://user:password@localhost:5432/mailsage_db')
    SQLALCHEMY_TRACK_MODIFICATION = False
    LOG_LEVEL = logging.INFO
    LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            'logs', 'mailsage.log')

    # Celery and Redis configuration
    REDIS_URL = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0')
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL

    # SMTP Defaults (used for testing SMTP validation)
    # These may not be global since we rely on user-specific
    # SMTP, but could be fallback
    MAIL_DEFAULT_SERVER = os.getenv('MAIL_DEFAULT_SERVER', 'smtp.gmail.com')
    MAIL_DEFAULT_PORT = int(os.getenv('MAIL_DEFAULT_PORT', 587))
    MAIL_USE_TLS = True
    MAIL_USE_SSL = False

    # Rate limiting or Quotas configuration
    MONTHLY_FREE_LIMIT = int(os.getenv('MONTHLY_FREE_LIMIT', 200))


class DevConfig(Config):
    DEBUG = True
    LOG_LEVEL = logging.DEBUG


class ProdConfig(Config):
    DEBUG = False
    LOG_LEVEL = logging.WARNING
    SERVER_NAME = 'mailsage.com'


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'  # For tests
    LOG_FILE = None
    LOG_LEVEL = logging.ERROR
