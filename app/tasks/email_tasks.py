from .celery_app import celery
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)


@celery.task
def test_task(x: int, y: int) -> int:
	"""Simple test task to verify Celery is working."""
	logger.info(f"Adding {x} + {y}")
	return x + y


@celery.task
def send_bulk_email(send_request_id):
    """Send email to multiple recipients."""
    logger.info(f"Processing send request: {send_request_id}")

    # Implement logic here

    return True
