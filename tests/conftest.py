import pytest
from unittest.mock import patch
from werkzeug.security import generate_password_hash
from app import create_app
from app.extensions import db
from app.models import User
from app.services.auth_services import AuthenticationService
from .mocks import MockMailService


@pytest.fixture(autouse=True)
def mock_mail_service():
    """Automatically mock mail service for all tests."""
    with patch('app.services.verification_service.MailService',
               return_value=MockMailService()):
        yield


@pytest.fixture(autouse=True)
def mock_redis():
    """Mock Redis client for all tests."""
    with patch('app.extensions.redis_client') as mock:
        mock.incr.return_value = 1
        mock.get.return_value = 0
        mock.setex.return_value = True
        yield mock
@pytest.fixture
def app():
    app = create_app('app.config.TestConfig')

    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_headers(app, client):
    """Create a test user and return auth headers."""
    with app.app_context():
        # Create and verify user
        # Create and verify user
        user = User(
            email='test@example.com',
            password_hash=generate_password_hash('test_password'),
            role='free',
            email_verified=True,
            is_active=True
        )
        db.session.add(user)
        db.session.commit()

        # Generate tokens
        tokens = AuthenticationService.generate_tokens(user.id)
        return {
            'Authorization': f'Bearer {tokens["access_token"]}',
            'refresh_token': tokens['refresh_token']
        }
