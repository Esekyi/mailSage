import pytest
from datetime import datetime, timezone
from app.models import User, Template, EmailJob
from app.utils.roles import ROLE_CONFIGURATIONS, ResourceLimit, UserRole
from app.extensions import db
from tests.utils import generate_token_for_user
from app.models.webhook import Webhook


@pytest.fixture
def users(app):
    """Create users with different roles."""
    with app.app_context():
        users = {}
        for role in UserRole:
            user = User(
                email=f'{role.value}@example.com',
                password_hash='test_hash',
                role=role.value,
                email_verified=True,
                is_active=True
            )
            db.session.add(user)
            db.session.commit()
            users[role.value] = user
        return users


class TestPermissions:
    @pytest.mark.parametrize('role,expected_status', [
        (UserRole.FREE, 403),
        (UserRole.PRO, 403),
        (UserRole.ENTERPRISE, 403),
        (UserRole.ADMIN, 200),
    ])
    def test_admin_access(self, client, users, role, expected_status):
        """Test admin panel access for different roles."""
        headers = {'Authorization': f'Bearer {
            generate_token_for_user(users[role.value])}'}
        response = client.get('/api/v1/admin/users', headers=headers)
        assert response.status_code == expected_status

    @pytest.mark.parametrize('role,expected_status', [
        (UserRole.FREE, 403),
        (UserRole.PRO, 200),
        (UserRole.ENTERPRISE, 200),
        (UserRole.ADMIN, 200),
    ])
    def test_analytics_access(self, client, users, role, expected_status):
        """Test analytics access for different roles."""
        headers = {'Authorization': f'Bearer {
            generate_token_for_user(users[role.value])}'}
        response = client.get('/api/v1/analytics', headers=headers)
        assert response.status_code == expected_status


class TestResourceLimits:
    @pytest.mark.parametrize('role,template_count,expected_status', [
        (UserRole.FREE, 4, 201),
        (UserRole.FREE, 5, 403),
        (UserRole.PRO, 49, 201),
        (UserRole.PRO, 50, 403),
        (UserRole.ENTERPRISE, 100, 201),
    ])
    def test_template_limits(self, app, client, users, role, template_count,
                             expected_status):
        """Test template creation limits for different roles."""
        user = users[role.value]
        headers = {'Authorization': f'Bearer {generate_token_for_user(user)}'}

        # Create templates up to test count
        with app.app_context():
            for i in range(template_count):
                template = Template(
                    user_id=user.id,
                    name=f'Template {i}',
                    html_content='<p>Test</p>'
                )
                db.session.add(template)
            db.session.commit()

        # Try to create one more template
        response = client.post('/api/v1/templates',
                               json={'name': 'Test Template',
                                     'content': '<p>Test</p>'},
                               headers=headers)
        assert response.status_code == expected_status

    def test_email_rate_limits(self, app, client, users):
        """Test email sending rate limits."""
        user = users[UserRole.FREE.value]
        headers = {'Authorization': f'Bearer {generate_token_for_user(user)}'}

        # Create email jobs up to daily limit
        with app.app_context():
            daily_limit = 100
            email_job = EmailJob(
                user_id=user.id,
                recipient_count=daily_limit,
                status='completed',
                subject='Test Subject',
                created_at=datetime.now(timezone.utc)
            )
            db.session.add(email_job)
            db.session.commit()

        # Try to send one more email
        response = client.post('/api/v1/send',
                               json={'template_id': 1,
                                     'recipients': ['test@example.com']},
                               headers=headers)
        assert response.status_code == 403
        assert 'daily limit' in response.json['error'].lower()

    @pytest.mark.parametrize('role,webhook_count,expected_status', [
        (UserRole.FREE, 0, 201),
        (UserRole.FREE, 1, 403),
        (UserRole.PRO, 4, 201),
        (UserRole.PRO, 5, 403),
        (UserRole.ENTERPRISE, 10, 201),
    ])
    def test_webhook_limits(self, app, client, users, role, webhook_count,
                            expected_status):
        """Test webhook endpoint limits for different roles."""
        user = users[role.value]
        headers = {'Authorization': f'Bearer {generate_token_for_user(user)}'}

        # Create webhooks up to test count
        with app.app_context():
            for i in range(webhook_count):
                webhook = Webhook(
                    user_id=user.id,
                    url=f'https://test{i}.com/webhook',
                    events=['email.sent']
                )
                db.session.add(webhook)
            db.session.commit()

        # Try to create one more webhook
        response = client.post('/api/v1/webhooks',
                               json={'url': 'https://test.com/webhook',
                                     'events': ['email.sent']},
                               headers=headers)
        assert response.status_code == expected_status

    def test_template_size_limits(self, app, client, users):
        """Test template size limits for different roles."""
        for role in [UserRole.FREE, UserRole.PRO]:
            user = users[role.value]
            headers = {'Authorization': f'Bearer {
                generate_token_for_user(user)}'}

            # Create large template content
            size_limit = ROLE_CONFIGURATIONS[role.value]['limits'][
                ResourceLimit.TEMPLATE_SIZE.value]
            large_content = 'x' * (size_limit + 1)

            response = client.post('/api/v1/templates',
                                   json={'name': 'Large Template',
                                         'content': large_content},
                                   headers=headers)
            assert response.status_code == 403
            assert 'template size' in response.json['error'].lower()
