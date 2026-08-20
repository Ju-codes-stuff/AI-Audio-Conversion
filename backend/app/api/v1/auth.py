"""
Auth API — registration, login, and token refresh.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from jose import JWTError
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.dependencies import CurrentUser, DBSession, get_db
from app.core.exceptions import BadRequestError, ConflictError, UnauthorizedError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.user import (
    RefreshRequest,
    TokenResponse,
    UserPublicResponse,
    UserRegisterRequest,
)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserPublicResponse, status_code=201)
async def register(body: UserRegisterRequest, db: DBSession):
    """Register a new citizen account."""
    if not body.phone_number and not body.email:
        raise BadRequestError("Provide at least one of: phone_number, email")

    # Uniqueness check
    conditions = []
    if body.phone_number:
        conditions.append(User.phone_number == body.phone_number)
    if body.email:
        conditions.append(User.email == body.email)

    existing = await db.execute(select(User).where(or_(*conditions)))
    if existing.scalar_one_or_none():
        raise ConflictError("An account with this phone number or email already exists")

    user = User(
        phone_number=body.phone_number,
        email=str(body.email) if body.email else None,
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
        preferred_language=body.preferred_language,
    )
    db.add(user)
    await db.flush()
    return user


@router.post("/login", response_model=TokenResponse)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DBSession,
):
    """
    Login with phone number or email as username, plus password.
    Returns JWT access + refresh tokens.
    """
    identifier = form.username.strip()
    result = await db.execute(
        select(User).where(
            or_(User.phone_number == identifier, User.email == identifier)
        )
    )
    user = result.scalar_one_or_none()

    if user is None or not verify_password(form.password, user.hashed_password):
        raise UnauthorizedError("Invalid credentials")
    if not user.is_active:
        raise UnauthorizedError("Account is disabled")

    access = create_access_token(subject=user.id)
    refresh = create_refresh_token(subject=user.id)

    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(body: RefreshRequest, db: DBSession):
    """Exchange a valid refresh token for a new access token."""
    try:
        payload = decode_token(body.refresh_token)
        if payload.get("type") != "refresh":
            raise UnauthorizedError("Invalid token type")
        user_id: str = payload["sub"]
    except JWTError:
        raise UnauthorizedError("Invalid or expired refresh token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise UnauthorizedError("User not found")

    return TokenResponse(
        access_token=create_access_token(subject=user.id),
        refresh_token=create_refresh_token(subject=user.id),
        expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.get("/me", response_model=UserPublicResponse)
async def get_me(current_user: CurrentUser):
    """Return the currently authenticated user's profile."""
    return current_user
