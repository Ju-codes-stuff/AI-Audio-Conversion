"""
StatusHistory ORM model — immutable audit trail of grievance state transitions.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.grievance import GrievanceStatus


class StatusHistory(Base):
    __tablename__ = "status_history"

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
    from_status: Mapped[GrievanceStatus | None] = mapped_column(
        Enum(GrievanceStatus), nullable=True
    )
    to_status: Mapped[GrievanceStatus] = mapped_column(
        Enum(GrievanceStatus), nullable=False
    )
    changed_by_user_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    grievance: Mapped["Grievance"] = relationship("Grievance", back_populates="status_history")  # noqa: F821

    def __repr__(self) -> str:
        return f"<StatusHistory {self.from_status}→{self.to_status}>"
