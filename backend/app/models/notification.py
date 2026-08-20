"""
Notification ORM model — multi-channel delivery records.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.database import Base


class NotificationChannel(str, enum.Enum):
    SMS = "SMS"
    WHATSAPP = "WHATSAPP"
    EMAIL = "EMAIL"
    PUSH = "PUSH"
    IN_APP = "IN_APP"


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    user_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    grievance_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("grievances.id", ondelete="SET NULL"), nullable=True, index=True
    )
    channel: Mapped[NotificationChannel] = mapped_column(
        Enum(NotificationChannel), nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped["User"] = relationship("User", back_populates="notifications")  # noqa: F821
    grievance: Mapped["Grievance | None"] = relationship("Grievance", back_populates="notifications")  # noqa: F821

    def __repr__(self) -> str:
        return f"<Notification channel={self.channel} user={self.user_id}>"
