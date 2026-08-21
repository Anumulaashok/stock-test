"""FastAPI dependencies for authentication — the only place that reads
the `Authorization` header and turns it into a `UserRow`."""

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.service import AuthError, AuthService
from app.core.config import Settings, get_settings
from app.db.base import get_db
from app.db.models import UserRow


def get_auth_service(settings: Settings = Depends(get_settings)) -> AuthService:
    return AuthService(
        secret_key=settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
        expires_minutes=settings.jwt_access_token_expires_minutes,
    )


def _extract_bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return authorization.split(" ", 1)[1].strip()


async def get_current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserRow:
    token = _extract_bearer_token(authorization)
    try:
        return await auth_service.get_current_user(db, token)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=exc.message) from exc


async def get_current_token(authorization: str | None = Header(default=None)) -> str:
    """Used by /auth/logout, which needs the raw token to revoke — not
    the resolved user."""
    return _extract_bearer_token(authorization)
