"""Password hashing and JWT issuance/verification.

Uses `bcrypt` directly (no passlib layer — avoids a known passlib/bcrypt
version-compatibility footgun) and `PyJWT` for stateless bearer tokens.
"""

import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(
    user_id: str, secret_key: str, algorithm: str, expires_minutes: int
) -> tuple[str, str]:
    """Returns `(token, jti)`."""
    jti = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "jti": jti,
        "iat": now,
        "exp": now + timedelta(minutes=expires_minutes),
    }
    token = jwt.encode(payload, secret_key, algorithm=algorithm)
    return token, jti


def decode_access_token(token: str, secret_key: str, algorithm: str) -> dict:
    """Raises `jwt.PyJWTError` (or a subclass) on an invalid/expired token."""
    return jwt.decode(token, secret_key, algorithms=[algorithm])
