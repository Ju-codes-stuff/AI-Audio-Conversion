"""
Custom FastAPI HTTP exceptions with consistent JSON error bodies.
"""
from __future__ import annotations

from fastapi import HTTPException, status


class BadRequestError(HTTPException):
    def __init__(self, detail: str = "Bad request"):
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


class UnauthorizedError(HTTPException):
    def __init__(self, detail: str = "Not authenticated"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            headers={"WWW-Authenticate": "Bearer"},
        )


class ForbiddenError(HTTPException):
    def __init__(self, detail: str = "Permission denied"):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


class NotFoundError(HTTPException):
    def __init__(self, resource: str = "Resource"):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{resource} not found",
        )


class ConflictError(HTTPException):
    def __init__(self, detail: str = "Conflict"):
        super().__init__(status_code=status.HTTP_409_CONFLICT, detail=detail)


class UnprocessableError(HTTPException):
    def __init__(self, detail: str = "Cannot process request"):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
        )


class ServiceUnavailableError(HTTPException):
    def __init__(self, service: str = "AI service"):
        super().__init__(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{service} is temporarily unavailable",
        )


class UnsupportedLanguageError(BadRequestError):
    def __init__(self, code: str):
        super().__init__(
            detail=f"Language '{code}' is not supported. "
            "See /api/v1/languages for the full list."
        )
