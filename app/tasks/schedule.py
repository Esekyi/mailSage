from celery.schedules import crontab

CELERYBEAT_SCHEDULE = {
    'reset-monthly-quotas': {
        'task': 'app.tasks.quota_tasks.reset_monthly_quotas',
        # Midnight on 1st of month
        'schedule': crontab(0, 0, day_of_month='1'),
    },
    'update-metrics': {
        'task': 'app.tasks.metrics_tasks.update_metrics',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },
}

# Additional Celery configurations
CELERY_CONFIG = {
    'task_serializer': 'json',
    'accept_content': ['json'],
    'result_serializer': 'json',
    'timezone': 'UTC',
    'beat_schedule': CELERYBEAT_SCHEDULE,
}
