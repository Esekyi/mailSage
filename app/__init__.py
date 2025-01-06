from flask import Flask
from flask_cors import CORS
from app.extensions import db, migrate, redis_client
from app.config import DevConfig
from app.tasks.celery_app import create_celery_app
from app.tasks.schedule import CELERY_CONFIG
from flask_jwt_extended import JWTManager
from app.utils.logging import setup_logger
from app.utils.error_handlers import register_error_handlers
import logging

# Create celery instance first
celery = create_celery_app()

def create_app(config_class=DevConfig):
    """Create and configure the app factory to flask app"""
    app = Flask(__name__, template_folder='../templates')
    app.config.from_object(config_class)

    # Verify SMTP configuration
    required_smtp_configs = [
        'SYSTEM_SMTP_HOST',
        'SYSTEM_SMTP_PORT',
        'SYSTEM_SMTP_USERNAME',
        'SYSTEM_SMTP_PASSWORD',
        'SYSTEM_SMTP_FROM_EMAIL'
    ]

    missing_configs = [
        config for config in required_smtp_configs if not app.config.get(config)
    ]

    if missing_configs:
        app.logger.error(
            f"Missing SMTP configuration: {', '.join(missing_configs)}")
        raise ValueError(
            f"Missing SMTP configuration: {', '.join(missing_configs)}")

    app.logger.info("SMTP Configuration loaded successfully")

    # Initialize CORS
    CORS(app, resources={
        r"/api/*": {
            "origins": app.config['CORS_ORIGINS'],
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
            "expose_headers": ["Content-Range", "X-Content-Range"],
            "supports_credentials": True,
        }
    })

    # Initialize extensions
    db.init_app(app)
    jwt = JWTManager(app)
    redis_client.init_app(app)

    # Initialize extensions db, migrate, celery, jwt
    migrate.init_app(app, db)
    jwt.init_app(app)

    app.logger = setup_logger(
        name=app.name,
        log_file=app.config.get('LOG_FILE'),
        level=app.config.get('LOG_LEVEL', logging.INFO)
    )

    # Initialize Celery
    global celery
    celery = create_celery_app(app)
    celery.conf.update(CELERY_CONFIG)

    # Register blueprints for internal routes
    from app.api.internal import (
        auth, templates, analytics, send, smtp, dashboard,
        user_routes, job_control, api_keys, docs
    )
    from app.routes import admin

    app.register_blueprint(auth.auth_bp)
    app.register_blueprint(templates.templates_bp)
    app.register_blueprint(analytics.analytics_bp)
    app.register_blueprint(send.send_bp)
    app.register_blueprint(smtp.smtp_bp)
    app.register_blueprint(admin.admin_bp)
    app.register_blueprint(dashboard.dashboard_bp)
    app.register_blueprint(user_routes.profile_bp)
    app.register_blueprint(job_control.job_control_bp)
    app.register_blueprint(api_keys.api_keys_bp)
    app.register_blueprint(docs.docs_bp)

    # Register blueprints for Public API
    from app.api.emails import emails_bp
    app.register_blueprint(emails_bp)

    @app.after_request
    def after_request(response):
        response.headers.add('Access-Control-Allow-Headers',
                             'Content-Type, Authorization')
        response.headers.add('Access-Control-Allow-Methods',
                             'GET, POST, PUT, DELETE, OPTIONS')
        return response

    register_error_handlers(app)

    return app
