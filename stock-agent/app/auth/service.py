"""Auth business logic: signup, login, current-user resolution, logout.

Depends on an injected `AsyncSession` per call — no module-level DB
state. Raises `AuthError` for expected failures (bad credentials,
duplicate email, invalid/expired token); the API layer maps that to a
sanitized HTTP response (never leaking whether an internal error is
auth-related vs. a bug).
"""

import re
from datetime import datetime, timezone

import jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import create_access_token, decode_access_token, hash_password, verify_password
from app.db.models import RevokedTokenRow, UserRow

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
_MIN_PASSWORD_LENGTH = 8


class AuthError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


def _validate_email(email: str) -> None:
    if not _EMAIL_RE.match(email):
        raise AuthError("invalid_email", "Enter a valid email address.")


def _validate_password(password: str) -> None:
    if len(password) < _MIN_PASSWORD_LENGTH:
        raise AuthError(
            "weak_password", f"Password must be at least {_MIN_PASSWORD_LENGTH} characters long."
        )


class AuthService:
    def __init__(self, secret_key: str, algorithm: str, expires_minutes: int) -> None:
        self._secret_key = secret_key
        self._algorithm = algorithm
        self._expires_minutes = expires_minutes

    async def signup(self, db: AsyncSession, email: str, password: str) -> tuple[UserRow, str]:
        email = email.strip().lower()
        _validate_email(email)
        _validate_password(password)

        existing = await db.scalar(select(UserRow).where(UserRow.email == email))
        if existing is not None:
            raise AuthError("email_already_registered", "An account with this email already exists.")

        user = UserRow(email=email, password_hash=hash_password(password))
        db.add(user)
        await db.commit()
        await db.refresh(user)

        token, _ = create_access_token(user.id, self._secret_key, self._algorithm, self._expires_minutes)
        return user, token

    async def login(self, db: AsyncSession, email: str, password: str) -> tuple[UserRow, str]:
        email = email.strip().lower()
        user = await db.scalar(select(UserRow).where(UserRow.email == email))
        if user is None or not verify_password(password, user.password_hash):
            # Deliberately identical error for "no such user" and "wrong
            # password" -- never reveal which one it was.
            raise AuthError("invalid_credentials", "Incorrect email or password.")

        token, _ = create_access_token(user.id, self._secret_key, self._algorithm, self._expires_minutes)
        return user, token

    async def get_current_user(self, db: AsyncSession, token: str) -> UserRow:
        try:
            payload = decode_access_token(token, self._secret_key, self._algorithm)
        except jwt.PyJWTError as exc:
            raise AuthError("invalid_token", "Your session is invalid or has expired.") from exc

        jti = payload.get("jti")
        if jti and await db.scalar(select(RevokedTokenRow).where(RevokedTokenRow.jti == jti)) is not None:
            raise AuthError("invalid_token", "Your session is invalid or has expired.")

        user_id = payload.get("sub")
        user = await db.get(UserRow, user_id) if user_id else None
        if user is None:
            raise AuthError("invalid_token", "Your session is invalid or has expired.")
        return user

    async def logout(self, db: AsyncSession, token: str) -> None:
        """Idempotent — an already-invalid/expired token logs out cleanly
        with no error."""
        try:
            payload = decode_access_token(token, self._secret_key, self._algorithm)
        except jwt.PyJWTError:
            return

        jti = payload.get("jti")
        exp = payload.get("exp")
        if not jti:
            return

        expires_at = (
            datetime.fromtimestamp(exp, tz=timezone.utc) if exp else datetime.now(timezone.utc)
        )
        already_revoked = await db.scalar(select(RevokedTokenRow).where(RevokedTokenRow.jti == jti))
        if already_revoked is None:
            db.add(RevokedTokenRow(jti=jti, expires_at=expires_at))
            await db.commit()
