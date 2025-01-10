from flask import Flask
from app.config import Config
from app.celery_factory import celery, init_celery
from app.tasks import email_tasks



def create_celery_app(flask_app: Flask = None):
    """Create and configure Celery instance."""
    # Create Flask app if not provided
    if not flask_app:
        from app import create_app
        flask_app = create_app()

    celery = init_celery(flask_app)

    # Update Celery config from Flask config
    celery.conf.update(flask_app.config)


    return celery
