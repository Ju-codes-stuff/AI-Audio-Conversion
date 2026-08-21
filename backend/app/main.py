"""
FastAPI application entrypoint.

Registers all v1 routers and configures:
  • CORS
  • Global exception handlers
  • Startup/shutdown lifespan events
  • OpenAPI metadata
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan (startup / shutdown) ────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting %s v%s [%s]", settings.APP_NAME, settings.APP_VERSION, settings.APP_ENV)

    # Ensure object storage buckets exist
    try:
        from app.services.storage_service import storage_service
        storage_service.ensure_buckets()
        logger.info("Object storage buckets ready")
    except Exception as exc:
        logger.warning("Storage init failed (non-fatal): %s", exc)

    yield

    logger.info("Shutting down")


# ── App factory ───────────────────────────────────────────────
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "Unified Multilingual Government Grievance Platform — "
        "AI-powered grievance submission in 22 Indian languages."
    ),
    contact={
        "name": "Platform Team",
        "email": "tech@grievance.gov.in",
    },
    license_info={"name": "MIT"},
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Global exception handlers ─────────────────────────────────
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception: %s %s | %s", request.method, request.url, exc, exc_info=True)
    import traceback
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred. Please try again later.", "traceback": "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))},
    )


# ── Routers ───────────────────────────────────────────────────
from app.api.v1 import auth, audio, grievances, departments, notifications, admin, government  # noqa: E402

prefix = settings.API_V1_PREFIX

app.include_router(auth.router, prefix=prefix)
app.include_router(audio.router, prefix=prefix)
app.include_router(grievances.router, prefix=prefix)
app.include_router(departments.router, prefix=prefix)
app.include_router(notifications.router, prefix=prefix)
app.include_router(admin.router, prefix=prefix)
app.include_router(government.router, prefix=prefix)


# ── Health & languages endpoints ──────────────────────────────
@app.get("/health", tags=["System"])
async def health():
    return {"status": "ok", "version": settings.APP_VERSION, "env": settings.APP_ENV}


@app.get(f"{prefix}/languages", tags=["System"])
async def list_languages():
    """Return all 22 supported Indian language codes and names."""
    from app.core.languages import LANGUAGES
    return [
        {
            "code": lang.code,
            "name_en": lang.name_en,
            "name_native": lang.name_native,
            "script": lang.script,
        }
        for lang in LANGUAGES
    ]
