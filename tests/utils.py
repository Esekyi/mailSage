from flask_jwt_extended import create_access_token
from app.models import User
from app.extensions import db
from flask import current_app

def generate_token_for_user(user: User) -> str:
    """Generate a JWT token for testing."""
    with current_app.app_context():
        db.session.add(user)
        token = create_access_token(identity=str(user.id))
        db.session.expunge_all()  # Remove objects from session
        return token
