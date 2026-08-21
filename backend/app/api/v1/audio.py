"""
Audio Upload API — accept, store, and enqueue grievance audio.
"""
from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile

from app.core.dependencies import CurrentUser, DBSession
from app.core.exceptions import BadRequestError, UnsupportedLanguageError
from app.core.languages import is_supported
from app.schemas.audio import AudioProcessingStatus, AudioUploadResponse
from app.services.grievance_service import grievance_service
from app.services.notification_service import notification_service
from app.services.storage_service import storage_service

router = APIRouter(prefix="/audio", tags=["Audio"])

MAX_FILE_SIZE_MB = 50


@router.post("/upload", response_model=AudioUploadResponse, status_code=202)
async def upload_audio(
    current_user: CurrentUser,
    db: DBSession,
    language_code: str = Form(..., description="BCP-47 language code, e.g. 'hi', 'ta'"),
    audio: UploadFile = File(..., description="Audio file (WAV/MP3/OGG/M4A/FLAC/WebM)"),
):
    """
    Accept an audio file from the citizen, store it, and enqueue the processing pipeline.

    Immediately returns a grievance ID and job ID for status polling.
    Processing happens asynchronously via Celery worker.
    """
    # Validate language
    if not is_supported(language_code):
        raise UnsupportedLanguageError(language_code)

    # Validate file
    if audio.content_type and not audio.content_type.startswith("audio/"):
        raise BadRequestError(f"File must be an audio file, got: {audio.content_type}")

    # Read and size-check
    audio_bytes = await audio.read()
    size_mb = len(audio_bytes) / (1024 * 1024)
    if size_mb > MAX_FILE_SIZE_MB:
        raise BadRequestError(f"File too large ({size_mb:.1f} MB). Maximum is {MAX_FILE_SIZE_MB} MB.")

    if len(audio_bytes) == 0:
        raise BadRequestError("Uploaded file is empty")

    # Upload to object storage
    extension = (audio.filename or "upload.wav").rsplit(".", 1)[-1].lower()
    storage_key = storage_service.upload_audio(audio_bytes, extension)

    # Create grievance record
    g = await grievance_service.create(
        db=db,
        user_id=current_user.id,
        language_code=language_code,
        audio_storage_key=storage_key,
    )
    await db.flush()

    # Notify citizen
    await notification_service.notify_grievance_created(
        db, g.id, g.grievance_id, current_user
    )
    await db.flush()

    # Enqueue Celery task
    from app.workers.tasks import process_audio_grievance
    task = process_audio_grievance.delay(g.id)

    from app.core.languages import get_language
    lang = get_language(language_code)

    return AudioUploadResponse(
        grievance_id=g.id,
        job_id=task.id,
        language_code=language_code,
        language_name=lang.name_en if lang else language_code,
    )


@router.get("/{grievance_id}/status", response_model=AudioProcessingStatus)
async def get_processing_status(
    grievance_id: str,
    current_user: CurrentUser,
    db: DBSession,
):
    """Poll the current processing status of an audio grievance."""
    g = await grievance_service.get_by_id(db, grievance_id)

    # Ownership check
    if g.user_id != current_user.id and not current_user.is_admin:
        from app.core.exceptions import ForbiddenError
        raise ForbiddenError()

    # Try to get Celery job state (best-effort)
    job_state = "UNKNOWN"
    try:
        from celery.result import AsyncResult
        from app.workers.celery_app import celery_app
        # We don't store job_id in the grievance row yet — return grievance status
        job_state = "SUCCESS" if g.status.value not in ("CREATED", "PROCESSING") else "PENDING"
    except Exception:
        pass

    return AudioProcessingStatus(
        grievance_id=g.id,
        job_id="",  # stored in Celery backend, not in DB
        status=job_state,
        grievance_status=g.status.value,
    )
