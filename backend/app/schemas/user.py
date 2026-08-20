"""
User Pydantic schemas — request / response validation.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, field_validator


class UserRegisterRequest(BaseModel):
    phone_number: Optional[str] = Field(None, pattern=r"^\+91[6-9]\d{9}$", examples=["+919876543210"])
    email: Optional[EmailStr] = None
    full_name: Optional[str] = Field(None, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    preferred_language: str = Field("hi", max_length=10)

    @field_validator("phone_number", "email")
    @classmethod
    def at_least_one_contact(cls, v: Optional[str], info) -> Optional[str]:
        # At least one of phone/email must be provided — enforced in service layer
        return v


class UserLoginRequest(BaseModel):
    """Login with phone OR email + password."""
    identifier: str = Field(..., description="Phone number or email")
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class RefreshRequest(BaseModel):
    refresh_token: str


class UserPublicResponse(BaseModel):
    id: str
    phone_number: Optional[str] = None
    email: Optional[str] = None
    full_name: Optional[str] = None
    preferred_language: str
    is_active: bool
    is_admin: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class UserUpdateRequest(BaseModel):
    full_name: Optional[str] = Field(None, max_length=255)
    preferred_language: Optional[str] = Field(None, max_length=10)
    email: Optional[EmailStr] = None
