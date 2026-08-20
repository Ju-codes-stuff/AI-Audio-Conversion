"""
Government Connector ORM models — Phase 3.

GovernmentConnector: represents a specific integration adapter
  (e.g. CPGRAMS, State portal, Municipal API).

ReferenceIDMapping: bidirectional mapping between internal GRV IDs
  and government-issued reference numbers.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from app.database import Base


class ConnectorType(str, enum.Enum):
    CPGRAMS = "CPGRAMS"               # Central CPGRAMS portal
    STATE_PORTAL = "STATE_PORTAL"     # State-specific grievance portal
    MUNICIPAL = "MUNICIPAL"           # City/municipal corporation
    CUSTOM_API = "CUSTOM_API"         # Arbitrary REST API
    EMAIL_GATEWAY = "EMAIL_GATEWAY"   # Email-based submission
    MOCK = "MOCK"                     # Used in development / testing


class ConnectorAuthType(str, enum.Enum):
    NONE = "NONE"
    API_KEY = "API_KEY"
    OAUTH2 = "OAUTH2"
    BASIC = "BASIC"
    CERTIFICATE = "CERTIFICATE"


class GovernmentConnector(Base):
    """
    An integration adapter for a specific government system.
    auth_config is stored as JSONB (encrypt sensitive fields at application layer).
    """
    __tablename__ = "government_connectors"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    connector_name: Mapped[str] = mapped_column(String(255), nullable=False)
    connector_type: Mapped[ConnectorType] = mapped_column(
        Enum(ConnectorType), nullable=False
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    auth_type: Mapped[ConnectorAuthType] = mapped_column(
        Enum(ConnectorAuthType), default=ConnectorAuthType.NONE, nullable=False
    )
    # Encrypted at application level before storage
    auth_config: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    # Status normalization map: gov_status → platform_status
    status_map: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    services: Mapped[list["GovernmentService"]] = relationship(  # noqa: F821
        "GovernmentService", back_populates="connector"
    )
    reference_mappings: Mapped[list["ReferenceIDMapping"]] = relationship(
        "ReferenceIDMapping", back_populates="connector", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<GovernmentConnector type={self.connector_type} name={self.connector_name}>"


class ReferenceIDMapping(Base):
    """
    Maps internal GRV-YYYY-NNNNNN → government-issued reference number.
    Supports bidirectional status sync.
    """
    __tablename__ = "reference_id_mappings"

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )
    grievance_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("grievances.id", ondelete="CASCADE"), index=True
    )
    platform_id: Mapped[str] = mapped_column(String(30), index=True, nullable=False)   # GRV-...
    government_reference_id: Mapped[str] = mapped_column(String(200), index=True, nullable=False)
    connector_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False), ForeignKey("government_connectors.id"), nullable=False
    )
    mapped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    connector: Mapped["GovernmentConnector"] = relationship(
        "GovernmentConnector", back_populates="reference_mappings"
    )

    def __repr__(self) -> str:
        return f"<ReferenceIDMapping {self.platform_id} ↔ {self.government_reference_id}>"
