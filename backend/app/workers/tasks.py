"""
Celery tasks — async audio processing pipeline.

Pipeline stages:
  1. Download audio from object storage
  2. FFmpeg normalization (16kHz mono WAV)
  3. ASR → native-language transcript
  4. IndicTrans2 → English translation
  5. (Mock) LLM → structured grievance
  6. Persist results to PostgreSQL
  7. Fire notifications to citizen

The task is idempotent: re-running with the same grievance_id
checks current status and skips already-completed stages.
"""
from __future__ import annotations

import asyncio
import logging

from celery import shared_task
from celery.utils.log import get_task_logger

from app.workers.celery_app import celery_app

logger = get_task_logger(__name__)


def _run_async(coro):
    """Run an async coroutine from a Celery task (sync context)."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(
    bind=True,
    name="tasks.process_audio_grievance",
    max_retries=3,
    default_retry_delay=30,
    acks_late=True,
)
def process_audio_grievance(self, grievance_id: str) -> dict:
    """
    Main async processing pipeline for a submitted audio grievance.

    Args:
        grievance_id: Internal UUID of the Grievance row.

    Returns:
        dict with keys: grievance_id, grv_id, status, transcript_length, translated_length
    """
    return _run_async(_process(self, grievance_id))


async def _process(task, grievance_id: str) -> dict:
    """Async implementation of the processing pipeline."""
    from app.database import get_async_session
    from app.models.grievance import Grievance, GrievanceStatus
    from app.models.transcript import Transcript
    from app.models.translation import Translation
    from app.services.audio_service import audio_service
    from app.services.asr_service import asr_service
    from app.services.translation_service import translation_service
    from app.services.llm_service import llm_service
    from app.services.grievance_service import grievance_service
    from app.services.notification_service import notification_service
    from app.services.storage_service import storage_service
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    logger.info("Processing grievance: %s", grievance_id)

    async with get_async_session() as db:
        # ── Fetch grievance ───────────────────────────────────
        result = await db.execute(
            select(Grievance)
            .where(Grievance.id == grievance_id)
            .options(selectinload(Grievance.user))
        )
        grievance = result.scalar_one_or_none()
        if grievance is None:
            logger.error("Grievance %s not found", grievance_id)
            return {"error": "not_found"}

        if grievance.status not in (GrievanceStatus.CREATED, GrievanceStatus.FAILED):
            logger.warning(
                "Grievance %s already in status %s — skipping",
                grievance_id,
                grievance.status,
            )
            return {"skipped": True, "status": grievance.status.value}

        # ── Stage 1: Transition to PROCESSING ────────────────
        try:
            await grievance_service.transition(db, grievance, GrievanceStatus.PROCESSING)
            await db.commit()
        except Exception as exc:
            logger.error("Failed to transition to PROCESSING: %s", exc)
            raise task.retry(exc=exc)

        language_code = grievance.language_code

        try:
            # ── Stage 2: Download audio ───────────────────────
            audio_bytes: bytes
            if grievance.audio_storage_key:
                logger.info("Downloading audio from storage: %s", grievance.audio_storage_key)
                audio_bytes = storage_service.download_audio(grievance.audio_storage_key)
            else:
                # No audio (text-only path) — skip ASR
                audio_bytes = b""

            normalized_bytes = b""
            duration = 0

            if audio_bytes:
                # ── Stage 3: FFmpeg normalization ─────────────
                logger.info("Normalizing audio (%d bytes)", len(audio_bytes))
                normalized_bytes, duration = await audio_service.normalize(
                    audio_bytes, "upload.wav"
                )
                grievance.audio_duration_seconds = duration
                await db.commit()

                # ── Stage 4: ASR ──────────────────────────────
                logger.info("Running ASR for language: %s", language_code)
                asr_result = await asr_service.transcribe(normalized_bytes, language_code)

                transcript = Transcript(
                    grievance_id=grievance.id,
                    language_code=asr_result.language_code,
                    text=asr_result.text,
                    confidence_score=asr_result.confidence,
                    asr_model_version=asr_result.model_version,
                    processing_time_ms=asr_result.processing_time_ms,
                    is_mock=asr_result.is_mock,
                )
                db.add(transcript)
                raw_transcript = asr_result.text
            else:
                raw_transcript = grievance.raw_transcript or ""

            # ── Stage 5: Translation ──────────────────────────
            logger.info("Translating to English")
            translation_result = await translation_service.translate_to_english(
                raw_transcript, language_code
            )

            translation = Translation(
                grievance_id=grievance.id,
                source_language=translation_result.source_language,
                target_language=translation_result.target_language,
                source_text=translation_result.source_text,
                translated_text=translation_result.translated_text,
                translation_model_version=translation_result.model_version,
                processing_time_ms=translation_result.processing_time_ms,
                is_mock=translation_result.is_mock,
            )
            db.add(translation)
            english_text = translation_result.translated_text

            # ── Stage 6: LLM classification (mock) ───────────
            logger.info("Running (mock) LLM classification")
            structured = await llm_service.classify(english_text)

            # ── Stage 7: Attach AI results ────────────────────
            await grievance_service.attach_ai_results(
                db, grievance, structured, raw_transcript, english_text
            )
            await db.commit()

            # ── Stage 8: Notify citizen ───────────────────────
            user = grievance.user
            await notification_service.notify_ai_ready(
                db, grievance.id, grievance.grievance_id, user
            )
            await db.commit()

            logger.info(
                "Pipeline complete for %s | transcript=%d chars | english=%d chars",
                grievance.grievance_id,
                len(raw_transcript),
                len(english_text),
            )

            return {
                "grievance_id": grievance.id,
                "grv_id": grievance.grievance_id,
                "status": GrievanceStatus.AI_GENERATED.value,
                "transcript_length": len(raw_transcript),
                "translated_length": len(english_text),
            }

        except Exception as exc:
            logger.error("Pipeline failed for %s: %s", grievance_id, exc, exc_info=True)
            async with get_async_session() as err_db:
                err_result = await err_db.execute(
                    select(Grievance).where(Grievance.id == grievance_id)
                )
                g = err_result.scalar_one_or_none()
                if g and g.status == GrievanceStatus.PROCESSING:
                    await grievance_service.transition(
                        err_db, g, GrievanceStatus.FAILED,
                        notes=f"Pipeline error: {exc}"
                    )
                    await err_db.commit()
            raise task.retry(exc=exc)
