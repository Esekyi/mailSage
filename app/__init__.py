from flask import Flask
from app.extensions import db, migrate
from app.config import DevConfig
from app.tasks.celery_app import create_celery_app
from app.tasks.schedule import CELERY_CONFIG
from flask_jwt_extended import JWTManager
from app.utils.logging import setup_logger
import logging


def create_app(config_class=DevConfig):
    """Create and configure the app factory to flask app"""
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)

    # Initialize extensions db, migrate, celery, jwt
    from app.models import User, AuditLog, EmailDelivery, Template, EmailJob, \
        APIKey

    migrate.init_app(app, db)

    jwt = JWTManager(app)

    app.logger = setup_logger(
        name=app.name,
        log_file=app.config.get('LOG_FILE'),
        level=app.config.get('LOG_LEVEL', logging.INFO)
    )

    # Initialize Celery
    global celery
    celery = create_celery_app(app)
    celery.conf.update(CELERY_CONFIG)

    # Register blueprints
    # from app.routes import auth, templates, send, admin
    # app.register_blueprint(auth.bp)
    # app.register_blueprint(templates.bp)
    # app.register_blueprint(send.bp)
    # app.register_blueprint(admin.bp)

    return app
