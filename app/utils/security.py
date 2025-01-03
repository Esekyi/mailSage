import bcrypt
from uuid import uuid4


def hash_api_key(key: str) -> str:
    """Hash API key using bcrypt."""
    return bcrypt.hashpw(key.encode(), bcrypt.gensalt()).decode()


def verify_api_key(key: str, hashed_key: str) -> bool:
    """Verify API key against stored hash."""
    return bcrypt.checkpw(key.encode(), hashed_key.encode())


def generate_api_key() -> str:
    """Generate a secure API key."""
    return str(uuid4())
