"""
Grievance Service — lifecycle orchestration and ID management.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, UnprocessableError
from app.core.languages import get_language
from app.models.grievance import Grievance, GrievancePriority, GrievanceStatus
from app.models.status_history import StatusHistory
from app.schemas.audio import StructuredGrievance
from app.schemas.grievance import GrievanceConfirmRequest
from app.utils.grievance_id import current_year, format_grievance_id

logger = logging.getLogger(__name__)

# Valid status transitions
_ALLOWED_TRANSITIONS: dict[GrievanceStatus, set[GrievanceStatus]] = {
    GrievanceStatus.CREATED: {GrievanceStatus.PROCESSING, GrievanceStatus.FAILED},
    GrievanceStatus.PROCESSING: {GrievanceStatus.AI_GENERATED, GrievanceStatus.FAILED},
    GrievanceStatus.AI_GENERATED: {GrievanceStatus.CONFIRMED, GrievanceStatus.FAILED},
    GrievanceStatus.CONFIRMED: {GrievanceStatus.SUBMITTED, GrievanceStatus.FAILED},
    GrievanceStatus.SUBMITTED: {GrievanceStatus.ACKNOWLEDGED, GrievanceStatus.FAILED},
    GrievanceStatus.ACKNOWLEDGED: {GrievanceStatus.IN_PROGRESS},
    GrievanceStatus.IN_PROGRESS: {
        GrievanceStatus.ACTION_REQUIRED,
        GrievanceStatus.RESOLVED,
        GrievanceStatus.FAILED,
    },
    GrievanceStatus.ACTION_REQUIRED: {GrievanceStatus.IN_PROGRESS, GrievanceStatus.CLOSED},
    GrievanceStatus.RESOLVED: {GrievanceStatus.CLOSED},
    GrievanceStatus.CLOSED: set(),
    GrievanceStatus.FAILED: {GrievanceStatus.CREATED},  # allow retry
}


class GrievanceService:
    # ── Creation ─────────────────────────────────────────────

    async def create(
        self,
        db: AsyncSession,
        user_id: str,
        language_code: str,
        audio_storage_key: str | None = None,
    ) -> Grievance:
        """Create a new grievance in CREATED status."""
        lang = get_language(language_code)
        if lang is None:
            raise UnprocessableError(f"Unsupported language: {language_code}")

        grievance = Grievance(
            user_id=user_id,
            language_code=language_code,
            language_name=lang.name_en,
            audio_storage_key=audio_storage_key,
            status=GrievanceStatus.CREATED,
        )
        db.add(grievance)
        await db.flush()  # assigns ID without committing

        # Assign GRV-YYYY-NNNNNN after obtaining the DB-generated UUID
        grievance.grievance_id = await self._next_grievance_id(db)

        await self._record_transition(db, grievance, None, GrievanceStatus.CREATED)
        logger.info("Created grievance %s for user %s", grievance.grievance_id, user_id)
        return grievance

    async def _next_grievance_id(self, db: AsyncSession) -> str:
        """Generate the next sequential GRV ID for the current year."""
        year = current_year()
        result = await db.execute(
            select(func.count()).where(
                Grievance.grievance_id.like(f"GRV-{year}-%")
            )
        )
        count = result.scalar_one() or 0
        return format_grievance_id(year, count + 1)

    # ── Status transitions ────────────────────────────────────

    async def transition(
        self,
        db: AsyncSession,
        grievance: Grievance,
        to_status: GrievanceStatus,
        changed_by: str | None = None,
        notes: str | None = None,
    ) -> Grievance:
        """Apply a validated status transition."""
        allowed = _ALLOWED_TRANSITIONS.get(grievance.status, set())
        if to_status not in allowed:
            raise UnprocessableError(
                f"Cannot transition from {grievance.status.value} to {to_status.value}. "
                f"Allowed: {[s.value for s in allowed]}"
            )

        from_status = grievance.status
        grievance.status = to_status

        # Set lifecycle timestamps
        now = datetime.now(timezone.utc)
        if to_status == GrievanceStatus.SUBMITTED:
            grievance.submitted_at = now
        elif to_status == GrievanceStatus.RESOLVED:
            grievance.resolved_at = now
        elif to_status == GrievanceStatus.CLOSED:
            grievance.closed_at = now

        await self._record_transition(db, grievance, from_status, to_status, changed_by, notes)
        logger.info(
            "Grievance %s: %s → %s",
            grievance.grievance_id,
            from_status.value,
            to_status.value,
        )
        return grievance

    async def _record_transition(
        self,
        db: AsyncSession,
        grievance: Grievance,
        from_status: GrievanceStatus | None,
        to_status: GrievanceStatus,
        changed_by: str | None = None,
        notes: str | None = None,
    ) -> None:
        history = StatusHistory(
            grievance_id=grievance.id,
            from_status=from_status,
            to_status=to_status,
            changed_by_user_id=changed_by,
            notes=notes,
        )
        db.add(history)

    # ── AI result attachment ──────────────────────────────────

    async def attach_ai_results(
        self,
        db: AsyncSession,
        grievance: Grievance,
        structured: StructuredGrievance,
        raw_transcript: str,
        english_text: str,
    ) -> Grievance:
        """Store AI pipeline outputs and advance to AI_GENERATED."""
        grievance.raw_transcript = raw_transcript
        grievance.english_text = english_text
        grievance.structured_data = structured.model_dump()
        grievance.category = structured.category
        grievance.location_state = structured.location_state
        grievance.location_district = structured.location_district
        grievance.location_city = structured.location_city
        grievance.location_raw = structured.location_raw

        try:
            priority = GrievancePriority(structured.priority)
        except ValueError:
            priority = GrievancePriority.MEDIUM
        grievance.priority = priority

        await self.transition(db, grievance, GrievanceStatus.AI_GENERATED, notes="AI pipeline complete")
        return grievance

    # ── Citizen confirmation ──────────────────────────────────

    async def confirm(
        self,
        db: AsyncSession,
        grievance: Grievance,
        data: GrievanceConfirmRequest,
        user_id: str,
    ) -> Grievance:
        """Citizen reviews and confirms AI-generated fields."""
        if grievance.status != GrievanceStatus.AI_GENERATED:
            raise UnprocessableError(
                f"Grievance must be in AI_GENERATED status to confirm (current: {grievance.status.value})"
            )

        # Apply any citizen corrections
        if data.description and grievance.structured_data:
            grievance.structured_data["description"] = data.description
        if data.category:
            grievance.category = data.category
            if grievance.structured_data:
                grievance.structured_data["category"] = data.category
        if data.location_state:
            grievance.location_state = data.location_state
        if data.location_district:
            grievance.location_district = data.location_district
        if data.location_city:
            grievance.location_city = data.location_city
        if data.priority:
            grievance.priority = data.priority

        await self.transition(
            db, grievance, GrievanceStatus.CONFIRMED,
            changed_by=user_id, notes="Confirmed by citizen"
        )
        return grievance

    # ── Retrieval helpers ──────────────────────────────────────

    async def get_by_id(self, db: AsyncSession, grievance_id: str) -> Grievance:
        """Fetch by internal UUID."""
        result = await db.execute(
            select(Grievance)
            .where(Grievance.id == grievance_id)
            .options(
                selectinload(Grievance.transcripts),
                selectinload(Grievance.translations),
                selectinload(Grievance.status_history),
            )
        )
        obj = result.scalar_one_or_none()
        if obj is None:
            raise NotFoundError("Grievance")
        return obj

    async def get_by_grv_id(self, db: AsyncSession, grv_id: str) -> Grievance:
        """Fetch by human-readable GRV-YYYY-NNNNNN ID."""
        result = await db.execute(
            select(Grievance)
            .where(Grievance.grievance_id == grv_id)
            .options(
                selectinload(Grievance.transcripts),
                selectinload(Grievance.translations),
                selectinload(Grievance.status_history),
            )
        )
        obj = result.scalar_one_or_none()
        if obj is None:
            raise NotFoundError("Grievance")
        return obj

    async def list_for_user(
        self,
        db: AsyncSession,
        user_id: str,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[int, list[Grievance]]:
        """Paginated list of grievances for a citizen."""
        count_result = await db.execute(
            select(func.count()).where(Grievance.user_id == user_id)
        )
        total = count_result.scalar_one()

        result = await db.execute(
            select(Grievance)
            .where(Grievance.user_id == user_id)
            .order_by(Grievance.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        return total, list(result.scalars().all())


grievance_service = GrievanceService()
