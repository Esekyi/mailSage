import os
from dotenv import load_dotenv
import logging
from datetime import timedelta
from cryptography.fernet import Fernet
load_dotenv()


class Config:
    """Set Flask configuration vars from .env file."""
    # Basic Flask config
    SECRETE_KEY = os.getenv(
        'SECRETE_KEY', 'Supersecret-tiny-littel-bit-secret-key')

    # JWT settings
    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-secret-key')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)

    # Database
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'DATABASE_URL',
        'postgresql://user:password@localhost:5432/mailsage_db')
    SQLALCHEMY_TRACK_MODIFICATION = False

    # Logging
    LOG_LEVEL = logging.INFO
    LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)),
                            'logs', 'mailsage.log')

    # Frontend URL
    FRONTEND_URL = os.getenv('FRONTEND_URL', 'http://localhost:3000')

    # CORS settings
    CORS_ORIGINS = [FRONTEND_URL]
    if 'localhost' in FRONTEND_URL or '127.0.0.1' in FRONTEND_URL:
        # common development ports if we're in local development
        local_host = FRONTEND_URL.split('://')[1].split(':')[0]
        CORS_ORIGINS.extend([
            f'http://{local_host}:3000',
            f'http://{local_host}:5173',
            f'http://{local_host}:8080'
        ])

    # Encryption
    ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY', Fernet.generate_key())

    # Celery and Redis configuration
    REDIS_URL = os.getenv('REDIS_URL', 'redis://127.0.0.1:6379/0')
    CELERY_BROKER_URL = REDIS_URL
    CELERY_RESULT_BACKEND = REDIS_URL

    # Task settings
    CELERY_TASK_SERIALIZER = 'json'
    CELERY_RESULT_SERIALIZER = 'json'
    CELERY_ACCEPT_CONTENT = ['json']
    CELERY_TIMEZONE = 'UTC'
    CELERY_ENABLE_UTC = True

    # Task specific settings
    CELERY_TASK_SOFT_TIME_LIMIT = 300  # 5 minutes
    CELERY_TASK_TIME_LIMIT = 600  # 10 minutes
    CELERY_TASK_MAX_RETRIES = 3
    CELERY_TASK_RETRY_DELAY = 60  # 1 minute

    # Rate limiting or Quotas configuration
    MONTHLY_FREE_LIMIT = int(os.getenv('MONTHLY_FREE_LIMIT', 200))

    # System SMTP configuration
    SYSTEM_SMTP_HOST = os.getenv('SYSTEM_SMTP_HOST')
    SYSTEM_SMTP_PORT = int(os.getenv('SYSTEM_SMTP_PORT'))
    SYSTEM_SMTP_USERNAME = os.getenv('SYSTEM_SMTP_USERNAME')
    SYSTEM_SMTP_PASSWORD = os.getenv('SYSTEM_SMTP_PASSWORD')
    SYSTEM_SMTP_USE_TLS = os.getenv('SYSTEM_SMTP_USE_TLS')
    SYSTEM_SMTP_FROM_EMAIL = os.getenv('SYSTEM_SMTP_FROM_EMAIL')


class DevConfig(Config):
    DEBUG = True
    LOG_LEVEL = logging.DEBUG
    DEVELOPMENT = True


class ProdConfig(Config):
    DEBUG = False
    LOG_LEVEL = logging.WARNING
    SERVER_NAME = 'mailsage.com'
    ENCRYPTION_KEY = os.environ.get('ENCRYPTION_KEY')

    # In production, only allow the specified FRONTEND_URL
    CORS_ORIGINS = [Config.FRONTEND_URL]

    # Ensure these are set in production
    def __init__(self):
        required_vars = [
            'SECRET_KEY',
            'JWT_SECRET_KEY',
            'DATABASE_URL',
            'FRONTEND_URL'
        ]
        for var in required_vars:
            if not os.getenv(var):
                raise ValueError(
                    f'Missing required environment variable: {var}')


class TestConfig(Config):
    TESTING = True
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.getenv(
        'TEST_DATABASE_URL',
        'postgresql://user:password@localhost:5432/mailsage_test')
    LOG_FILE = None
    LOG_LEVEL = logging.ERROR
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JWT_SECRET_KEY = 'test-secret-key'
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=1)
