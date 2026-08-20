"""
Government Service Registry — Phase 3 model.
Maps grievance categories + geography → specific government portals / connectors.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.database import Base


class SubmissionMethod(str, enum.Enum):
    API = "API"
    FORM = "FORM"
    EMAIL = "EMAIL"
    MANUAL = "MANUAL"


class GovernmentService(Base):
    """
    Registry entry linking a grievance type to a government submission endpoint.
    Scoped by category + state/district so the correct portal is chosen.
    """
    __tablename__ = "government_services"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    service_name: Mapped[str] = mapped_column(String(255), nullable=False)
    service_code: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Targeting
    category_code: Mapped[str | None] = mapped_column(String(50), index=True, nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), index=True, nullable=True)   # NULL = all states
    district: Mapped[str | None] = mapped_column(String(100), nullable=True)            # NULL = all districts

    department_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("departments.id"), nullable=True
    )
    connector_id: Mapped[str | None] = mapped_column(
        UUID(as_uuid=False), ForeignKey("government_connectors.id"), nullable=True
    )

    # Portal metadata
    portal_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    submission_method: Mapped[SubmissionMethod] = mapped_column(
        Enum(SubmissionMethod), default=SubmissionMethod.API, nullable=False
    )
    # JSON schema of fields required before submission
    required_fields: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    department: Mapped["Department | None"] = relationship("Department", back_populates="government_services")  # noqa: F821
    connector: Mapped["GovernmentConnector | None"] = relationship("GovernmentConnector", back_populates="services")  # noqa: F821

    def __repr__(self) -> str:
        return f"<GovernmentService code={self.service_code}>"
