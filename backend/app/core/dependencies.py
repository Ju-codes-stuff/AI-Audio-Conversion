"""
FastAPI dependency injectors — reused across route handlers.
"""
from __future__ import annotations

from typing import Annotated, AsyncGenerator

from fastapi import Depends, Header
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from app.core.exceptions import UnauthorizedError, ForbiddenError
from app.core.security import decode_token
from app.database import get_db
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_PREFIX}/auth/login")

# Re-export get_db as a typed annotation for cleaner route signatures
DBSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: DBSession,
) -> User:
    """Validate Bearer token and return the authenticated User."""
    try:
        payload = decode_token(token)
        user_id: str = payload.get("sub", "")
        if not user_id or payload.get("type") != "access":
            raise UnauthorizedError()
    except JWTError:
        raise UnauthorizedError("Invalid or expired token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise UnauthorizedError("User not found or inactive")
    return user


async def get_current_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Require the authenticated user to have admin privileges."""
    if not current_user.is_admin:
        raise ForbiddenError("Admin access required")
    return current_user


# Typed annotations for route signatures
CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(get_current_admin)]
