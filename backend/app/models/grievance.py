"""
Grievance ORM model — core entity of the platform.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.database import Base


class GrievanceStatus(str, enum.Enum):
    CREATED = "CREATED"               # audio uploaded, processing not yet started
    PROCESSING = "PROCESSING"         # Celery task running
    AI_GENERATED = "AI_GENERATED"     # AI output ready, awaiting citizen review
    CONFIRMED = "CONFIRMED"           # citizen reviewed and confirmed
    SUBMITTED = "SUBMITTED"           # submitted to government system
    ACKNOWLEDGED = "ACKNOWLEDGED"     # government acknowledged receipt
    IN_PROGRESS = "IN_PROGRESS"       # under government review
    ACTION_REQUIRED = "ACTION_REQUIRED"  # citizen must provide more info
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"
    FAILED = "FAILED"                 # processing failed


class GrievancePriority(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Grievance(Base):
    __tablename__ = "grievances"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    # Human-readable unique ID like GRV-2026-000142
    grievance_id: Mapped[str | None] = mapped_column(
        String(30), unique=True, index=True, nullable=True
    )
    # Auto-increment sequence per year to build the GRV ID
    year_sequence: Mapped[int | None] = mapped_column(Integer, nullable=True)

    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[GrievanceStatus] = mapped_column(
        Enum(GrievanceStatus, native_enum=False), default=GrievanceStatus.CREATED, nullable=False, index=True
    )
    priority: Mapped[GrievancePriority | None] = mapped_column(
        Enum(GrievancePriority, native_enum=False), nullable=True
    )

    # ── Audio ─────────────────────────────────────────────────
    language_code: Mapped[str] = mapped_column(String(10), nullable=False)
    language_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    audio_storage_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    audio_duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # ── AI outputs ────────────────────────────────────────────
    raw_transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    english_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Structured output produced by the (mock) LLM service:
    # {description, category, department, location, priority, missing_information}
    structured_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # ── Classification ────────────────────────────────────────
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    department_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("departments.id"), nullable=True
    )
    location_state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location_district: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location_raw: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # ── Phase 3 — Government integration ─────────────────────
    government_reference_id: Mapped[str | None] = mapped_column(String(200), nullable=True)
    connector_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("government_connectors.id"), nullable=True
    )

    # ── Timestamps ────────────────────────────────────────────
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # ── Relationships ─────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="grievances")  # noqa: F821
    department: Mapped["Department | None"] = relationship("Department", back_populates="grievances")  # noqa: F821
    transcripts: Mapped[list["Transcript"]] = relationship("Transcript", back_populates="grievance", cascade="all, delete-orphan")  # noqa: F821
    translations: Mapped[list["Translation"]] = relationship("Translation", back_populates="grievance", cascade="all, delete-orphan")  # noqa: F821
    status_history: Mapped[list["StatusHistory"]] = relationship("StatusHistory", back_populates="grievance", cascade="all, delete-orphan", order_by="StatusHistory.created_at")  # noqa: F821
    notifications: Mapped[list["Notification"]] = relationship("Notification", back_populates="grievance", cascade="all, delete-orphan")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Grievance {self.grievance_id or self.id} status={self.status}>"
