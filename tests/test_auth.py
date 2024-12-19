import pytest
from app.models.user import User
from app.extensions import db
from werkzeug.security import generate_password_hash


def test_register_user(client):
    response = client.post('/api/v1/auth/register', json={
        'email': 'new@example.com',
        'password': 'testpassword'
    })
    assert response.status_code == 201
    assert 'access_token' in response.json
    assert 'user' in response.json


def test_login_user(app, client):
    # First create a verified user
    with app.app_context():
        user = User(
            email='login@example.com',
            password_hash=generate_password_hash('testpassword'),
            is_active=True,
            email_verified=True
        )
        db.session.add(user)
        db.session.commit()

    # Then login
    response = client.post('/api/v1/auth/login', json={
        'email': 'login@example.com',
        'password': 'testpassword'
    })
    assert response.status_code == 200
    assert 'access_token' in response.json


def test_refresh_token(client, auth_headers):
    # Test refreshing the access token with a valid refresh token
    response = client.post(
        '/api/v1/auth/refresh',
        json={'refresh_token': auth_headers['refresh_token']}
    )
    assert response.status_code == 200
    assert 'access_token' in response.json


@pytest.mark.parametrize('role,expected_status', [
    ('free', 403),
    ('admin', 200)
])
def test_role_based_access(app, client, auth_headers, role, expected_status):
    # Update user to admin role
    with app.app_context():
        user = User.query.filter_by(email='test@example.com').first()
        user.role = role
        db.session.commit()

    # Test access again
    response = client.get(
        '/api/v1/admin/users',
        headers={'Authorization': auth_headers['Authorization']}
    )
    assert response.status_code == expected_status
