"""
Transcript ORM model — native-language ASR output.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Transcript(Base):
    __tablename__ = "transcripts"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    grievance_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("grievances.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    language_code: Mapped[str] = mapped_column(String(10), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    asr_model_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    processing_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_mock: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    grievance: Mapped["Grievance"] = relationship("Grievance", back_populates="transcripts")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Transcript lang={self.language_code} grievance={self.grievance_id}>"
