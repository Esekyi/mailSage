from typing import Dict, Any
from celery import shared_task
from app.models import EmailJob
from app.services.metrics_service import MetricsService


@shared_task
def update_metrics() -> Dict[str, Any]:
    """Update metrics for all active email jobs."""
    active_jobs = EmailJob.query.filter(
            EmailJob.status.in_(['processing', 'sending'])
        ).all()
    results = {
        'processed': 0,
        'errors': 0
    }
    for job in active_jobs:
        try:
            MetricsService.update_job_metrics(job)
            results['processed'] += 1
        except Exception:
            results['errors'] += 1

    return results
