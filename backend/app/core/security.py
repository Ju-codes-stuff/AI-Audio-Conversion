"""
JWT token creation/verification and password hashing utilities.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

# ── Password hashing ──────────────────────────────────────────
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── JWT ───────────────────────────────────────────────────────
def _create_token(data: Dict[str, Any], expires_delta: timedelta) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(subject: str, extra: Optional[Dict[str, Any]] = None) -> str:
    data: Dict[str, Any] = {"sub": subject, "type": "access"}
    if extra:
        data.update(extra)
    return _create_token(
        data,
        timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(subject: str) -> str:
    return _create_token(
        {"sub": subject, "type": "refresh"},
        timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str) -> Dict[str, Any]:
    """Decode and verify a JWT. Raises jose.JWTError on failure."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
