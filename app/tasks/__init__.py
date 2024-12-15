from .celery_app import celery
from .email_tasks import test_task, send_bulk_email

__all__ = ['celery', 'test_task', 'send_bulk_email']
