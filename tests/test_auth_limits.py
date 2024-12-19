def test_template_limits(client, auth_headers):
    endpoint = '/api/v1/templates'

    # Test free user template limit
    for i in range(6):  # Free users are limited to 5 templates
        response = client.post(
            endpoint,
            json={
                'name': f'Template {i}',
                'content': '<h1>Test</h1>'
            },
            headers={'Authorization': auth_headers['Authorization']}
        )
        if i < 5:
            assert response.status_code == 201, f"Failed on template {i}"
        else:
            assert response.status_code == 403, "Should fail after limit \
                reached"


def test_api_key_limits(client, auth_headers):
    endpoint = '/api/v1/auth/api-keys'
    # Test free user API key limit
    for i in range(3):  # Free users are limited to 2 API keys
        response = client.post(
            endpoint,
            json={'name': f'Key {i}'},
            headers={'Authorization': auth_headers['Authorization']}
        )
        if i < 2:
            assert response.status_code == 201
        else:
            assert response.status_code == 403


def test_email_verification_required(app, client):
    # Create unverified user
    register_response = client.post('/api/v1/auth/register', json={
        'email': 'unverified@example.com',
        'password': 'testpassword'
    })
    assert register_response.status_code == 201
    token = register_response.json['access_token']

    # Try to access protected endpoint
    response = client.post(
        '/api/v1/auth/api-keys',
        json={'name': 'Test Key'},
        headers={'Authorization': f'Bearer {token}'}
    )
    assert response.status_code == 403
    assert response.json['code'] == 'EMAIL_VERIFICATION_REQUIRED'
