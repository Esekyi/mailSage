from celery import shared_task
from app.services.quota_service import QuotaService


@shared_task
def reset_monthly_quotas_task():
    """Celery task to reset monthly quotas."""
    return QuotaService.reset_monthly_quotas()
