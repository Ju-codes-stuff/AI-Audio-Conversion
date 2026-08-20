"""
Application configuration — all settings sourced from environment variables.
Copy .env.example → .env and fill in your values.
"""
from __future__ import annotations

import json
from functools import lru_cache
from typing import Any, List

from pydantic import AnyHttpUrl, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ───────────────────────────────────────────
    APP_ENV: str = "development"
    APP_NAME: str = "Unified Multilingual Grievance Platform"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    SECRET_KEY: str = "CHANGE_ME_TO_A_LONG_RANDOM_SECRET"

    # ── API ───────────────────────────────────────────────────
    API_V1_PREFIX: str = "/api/v1"
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:8000"]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v: Any) -> List[str]:
        if isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [i.strip() for i in v.split(",")]
        return v

    # ── Database ──────────────────────────────────────────────
    DATABASE_URL: str = (
        "postgresql+asyncpg://grievance:grievance@localhost:5432/grievance_db"
    )

    # ── Redis / Celery ────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # ── Object Storage ────────────────────────────────────────
    STORAGE_ENDPOINT_URL: str = "http://localhost:9000"
    STORAGE_ACCESS_KEY: str = "minioadmin"
    STORAGE_SECRET_KEY: str = "minioadmin"
    STORAGE_BUCKET_AUDIO: str = "grievance-audio"
    STORAGE_BUCKET_DOCS: str = "grievance-docs"
    STORAGE_USE_SSL: bool = False

    # ── JWT ───────────────────────────────────────────────────
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ── AI Services ───────────────────────────────────────────
    ASR_SERVICE_URL: str = "http://localhost:8001"
    ASR_SERVICE_TIMEOUT: int = 60
    ASR_USE_MOCK: bool = True

    TRANSLATION_SERVICE_URL: str = "http://localhost:8002"
    TRANSLATION_SERVICE_TIMEOUT: int = 60
    TRANSLATION_USE_MOCK: bool = True

    LLM_USE_MOCK: bool = True
    LLM_SERVICE_URL: str = "http://localhost:8003"

    # ── Notifications ─────────────────────────────────────────
    SMS_PROVIDER: str = "mock"
    SMS_API_KEY: str = ""
    SMS_SENDER_ID: str = "GRIEVNC"

    WHATSAPP_PROVIDER: str = "mock"
    WHATSAPP_API_KEY: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""

    EMAIL_PROVIDER: str = "mock"
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    EMAIL_FROM: str = "noreply@grievance.gov.in"

    FCM_SERVER_KEY: str = ""
    FCM_USE_MOCK: bool = True

    # ── Audio / FFmpeg ────────────────────────────────────────
    FFMPEG_PATH: str = "ffmpeg"
    AUDIO_TMP_DIR: str = "/tmp/grievance_audio"

    # ── Phase 3 ───────────────────────────────────────────────
    REGISTRY_SEED_ON_STARTUP: bool = True

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
