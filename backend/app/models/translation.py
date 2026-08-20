"""
Translation ORM model — IndicTrans2 output (native → English).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Translation(Base):
    __tablename__ = "translations"

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
    source_language: Mapped[str] = mapped_column(String(20), nullable=False)   # IndicTrans2 NMT code
    target_language: Mapped[str] = mapped_column(String(20), nullable=False)   # "eng_Latn"
    source_text: Mapped[str] = mapped_column(Text, nullable=False)
    translated_text: Mapped[str] = mapped_column(Text, nullable=False)
    translation_model_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    processing_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_mock: Mapped[bool] = mapped_column(default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    grievance: Mapped["Grievance"] = relationship("Grievance", back_populates="translations")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Translation {self.source_language}→{self.target_language} grievance={self.grievance_id}>"
