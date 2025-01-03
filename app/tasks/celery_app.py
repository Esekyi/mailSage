from celery import Celery
from flask import Flask
from app.config import Config


def create_celery_app(flask_app: Flask = None) -> Celery:
    """Create and configure Celery instance."""
    # Create Flask app if not provided
    if not flask_app:
        flask_app = Flask(__name__)
        flask_app.config.from_object(Config)

    celery = Celery(
        'app',  # Use a fixed name instead of app.import_name
        broker=flask_app.config['CELERY_BROKER_URL'],
        backend=flask_app.config['CELERY_RESULT_BACKEND']
    )

    # Update Celery config from Flask config
    celery.conf.update(flask_app.config)

    class ContextTask(celery.Task):
        abstract = True  # This makes it a base class for all tasks

        def __call__(self, *args, **kwargs):
            with flask_app.app_context():
                return self.run(*args, **kwargs)

    celery.Task = ContextTask

    # Import tasks here to avoid circular imports
    from app.tasks import email_tasks  # noqa

    return celery


# Initialize Flask app
flask_app = Flask(__name__)
flask_app.config.from_object(Config)

# Create Celery instance
celery = create_celery_app(flask_app)
