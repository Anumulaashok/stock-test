"""Thin transport layer for authentication. No business logic here —
this module only translates HTTP <-> `AuthService`, and maps `AuthError`
to a sanitized HTTP response.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_auth_service, get_current_token, get_current_user
from app.auth.service import AuthError, AuthService
from app.db.base import get_db
from app.db.models import UserRow
from app.models.user import LoginRequest, SignupRequest, TokenResponse, UserPublic

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _to_public(user: UserRow) -> UserPublic:
    return UserPublic(id=user.id, email=user.email, created_at=user.created_at.isoformat())


@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(
    request: SignupRequest,
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    try:
        user, token = await auth_service.signup(db, request.email, request.password)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=exc.message) from exc
    return TokenResponse(access_token=token, user=_to_public(user))


@router.post("/login")
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    try:
        user, token = await auth_service.login(db, request.email, request.password)
    except AuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=exc.message) from exc
    return TokenResponse(access_token=token, user=_to_public(user))


@router.get("/me")
async def me(current_user: UserRow = Depends(get_current_user)) -> UserPublic:
    return _to_public(current_user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    token: str = Depends(get_current_token),
    db: AsyncSession = Depends(get_db),
    auth_service: AuthService = Depends(get_auth_service),
) -> None:
    await auth_service.logout(db, token)
