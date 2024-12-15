from celery import Celery
from flask import Flask


def create_celery_app(app: Flask = None) -> Celery:
    """Create and configure Celery instance."""
    celery = Celery(
        app.import_name if app else 'mailsage',
        broker=app.config['CELERY_BROKER_URL'] if app else None,
        backend=app.config['CELERY_RESULT_BACKEND'] if app else None,
        include=['app.tasks']
    )

    # Set additional Celery configurations

    class ContextTask(celery.Task):
        def __call__(self, *args, **kwargs):
            if app:
                with app.app_context():
                    return self.run(*args, **kwargs)
            return self.run(*args, **kwargs)

    celery.Task = ContextTask
    return celery


# Create a default instance
celery = Celery('mailsage')
