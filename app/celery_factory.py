from celery import Celery

celery = Celery()


def init_celery(app):
    """Initialize Celery with Flask app."""
    celery.conf.update(
        app.config,
        broker=app.config['CELERY_BROKER_URL'],
        backend=app.config['CELERY_RESULT_BACKEND'],
        task_serializer='json',
        result_serializer='json',
        accept_content=['json'],
        timezone='UTC',
        enable_utc=True,
        CELERY_IMPORTS=[
            "app.tasks.email_tasks"
        ]
    )

    class ContextTask(celery.Task):
        """Ensure Celery tasks have Flask application context."""
        abstract = True

        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery
