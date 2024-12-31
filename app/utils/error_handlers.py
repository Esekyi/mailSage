from flask import jsonify
from app.extensions import db
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException


def register_error_handlers(app):
    @app.errorhandler(404)
    def not_found_error(error):
        return jsonify({
            "error": "Resource not found",
            "message": str(error),
            "code": "NOT_FOUND"
        }), 404

    @app.errorhandler(401)
    def unauthorized_error(error):
        return jsonify({
            "error": "Unauthorized",
            "message": "Please log in to access this resource",
            "code": "UNAUTHORIZED"
        }), 401

    @app.errorhandler(403)
    def forbidden_error(error):
        return jsonify({
            "error": "Forbidden",
            "message": str(error),
            "code": "FORBIDDEN"
        }), 403

    @app.errorhandler(SQLAlchemyError)
    def database_error(error):
        db.session.rollback()
        app.logger.error(f"Database error: {str(error)}")
        return jsonify({
            "error": "Internal server error",
            "message": "A database error occurred",
            "code": "DATABASE_ERROR"
        }), 500

    @app.errorhandler(Exception)
    def unhandled_exception(error):
        if isinstance(error, HTTPException):
            return jsonify({
                "error": error.name,
                "message": error.description,
                "code": error.name.upper().replace(' ', '_')
            }), error.code

        app.logger.error(f"Unhandled exception: {str(error)}")
        return jsonify({
            "error": "Internal server error",
            "message": "An unexpected error occurred",
            "code": "INTERNAL_SERVER_ERROR"
        }), 500
