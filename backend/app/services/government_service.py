"""
Government Service — Phase 3 registry lookup and connector factory.

Architecture follows the Connector Framework described in Phase 3:
  GrievanceService → GovernmentService → BaseConnector → Government API

Connectors:
  • CPGRAMSConnector   — Central CPGRAMS portal (sample implementation)
  • MockConnector      — Always succeeds for dev/test

Add new connectors by subclassing BaseConnector and registering in _CONNECTOR_MAP.
"""
from __future__ import annotations

import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ServiceUnavailableError
from app.models.government_connector import (
    ConnectorType,
    GovernmentConnector,
    ReferenceIDMapping,
)
from app.models.grievance import Grievance, GrievanceStatus
from app.models.service import GovernmentService
from app.schemas.government import UNIFIED_STATUS_MAP

logger = logging.getLogger(__name__)


# ── Base connector interface ──────────────────────────────────

class BaseConnector(ABC):
    """
    Standard interface all government connectors must implement.
    The platform calls only these three operations.
    """

    @abstractmethod
    async def submit_grievance(
        self,
        grievance: Grievance,
        connector: GovernmentConnector,
    ) -> str:
        """
        Submit grievance to the government system.
        Returns the government-issued reference ID.
        """
        ...

    @abstractmethod
    async def get_status(
        self,
        government_ref_id: str,
        connector: GovernmentConnector,
    ) -> str:
        """
        Poll the government system for current status.
        Returns the raw government status string.
        """
        ...

    @abstractmethod
    async def get_updates(
        self,
        government_ref_id: str,
        connector: GovernmentConnector,
    ) -> list[dict]:
        """
        Fetch all status updates / remarks from the government system.
        Returns list of {status, remark, updated_at} dicts.
        """
        ...


# ── CPGRAMS connector ─────────────────────────────────────────

class CPGRAMSConnector(BaseConnector):
    """
    Connector for the Central Public Grievance Redress and Monitoring System.
    Replace the stub methods with actual CPGRAMS API calls when approved.
    """

    async def submit_grievance(
        self, grievance: Grievance, connector: GovernmentConnector
    ) -> str:
        logger.info(
            "[CPGRAMS] Submitting grievance %s to %s",
            grievance.grievance_id,
            connector.base_url,
        )
        # TODO: implement real CPGRAMS API call once integration is approved
        # For now, generate a plausible reference ID
        return f"CPGRAMS-{datetime.now(timezone.utc).year}-{uuid.uuid4().hex[:8].upper()}"

    async def get_status(self, government_ref_id: str, connector: GovernmentConnector) -> str:
        # TODO: implement real CPGRAMS status API call
        return "registered"

    async def get_updates(
        self, government_ref_id: str, connector: GovernmentConnector
    ) -> list[dict]:
        return [
            {
                "status": "registered",
                "remark": "Grievance has been registered in CPGRAMS.",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ]


# ── Mock connector ────────────────────────────────────────────

class MockConnector(BaseConnector):
    """Always succeeds — used for dev and testing."""

    async def submit_grievance(
        self, grievance: Grievance, connector: GovernmentConnector
    ) -> str:
        ref_id = f"MOCK-{uuid.uuid4().hex[:10].upper()}"
        logger.info("[MOCK GOV CONNECTOR] Submitted %s → %s", grievance.grievance_id, ref_id)
        return ref_id

    async def get_status(self, government_ref_id: str, connector: GovernmentConnector) -> str:
        return "registered"

    async def get_updates(
        self, government_ref_id: str, connector: GovernmentConnector
    ) -> list[dict]:
        return [
            {
                "status": "registered",
                "remark": "Mock grievance registered.",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ]


# ── Connector factory ─────────────────────────────────────────

_CONNECTOR_MAP: dict[ConnectorType, type[BaseConnector]] = {
    ConnectorType.CPGRAMS: CPGRAMSConnector,
    ConnectorType.MOCK: MockConnector,
    ConnectorType.STATE_PORTAL: MockConnector,    # Replace each when implemented
    ConnectorType.MUNICIPAL: MockConnector,
    ConnectorType.CUSTOM_API: MockConnector,
    ConnectorType.EMAIL_GATEWAY: MockConnector,
}


def get_connector(connector_type: ConnectorType) -> BaseConnector:
    cls = _CONNECTOR_MAP.get(connector_type, MockConnector)
    return cls()


# ── Government Service (business logic) ───────────────────────

class GovernmentRegistryService:
    # ── Registry lookup ───────────────────────────────────────

    async def find_services(
        self,
        db: AsyncSession,
        category: str,
        state: Optional[str] = None,
        district: Optional[str] = None,
    ) -> list[GovernmentService]:
        """
        Find matching government services from registry.
        Most-specific match first (state + district > state > all).
        """
        query = (
            select(GovernmentService)
            .where(
                GovernmentService.is_active == True,  # noqa: E712
                GovernmentService.category_code == category,
            )
            .order_by(GovernmentService.state.nulls_last())
        )
        result = await db.execute(query)
        services = list(result.scalars().all())

        # Filter by geography preference
        if state:
            specific = [s for s in services if s.state and s.state.lower() == state.lower()]
            fallback = [s for s in services if s.state is None]
            services = specific or fallback

        return services

    # ── Submission ────────────────────────────────────────────

    async def submit_to_government(
        self,
        db: AsyncSession,
        grievance: Grievance,
        service_code: str,
    ) -> str:
        """
        Route a confirmed grievance to the appropriate government system.
        Returns the government reference ID.
        """
        # Lookup service in registry
        svc_result = await db.execute(
            select(GovernmentService).where(GovernmentService.service_code == service_code)
        )
        service = svc_result.scalar_one_or_none()
        if service is None:
            raise NotFoundError(f"Government service '{service_code}'")

        if not service.connector_id:
            raise ServiceUnavailableError(f"No connector configured for service {service_code}")

        # Load connector config
        conn_result = await db.execute(
            select(GovernmentConnector).where(GovernmentConnector.id == service.connector_id)
        )
        connector = conn_result.scalar_one_or_none()
        if connector is None or not connector.is_active:
            raise ServiceUnavailableError("Government connector is inactive")

        # Submit via correct adapter
        adapter = get_connector(connector.connector_type)
        gov_ref_id = await adapter.submit_grievance(grievance, connector)

        # Persist mapping
        mapping = ReferenceIDMapping(
            grievance_id=grievance.id,
            platform_id=grievance.grievance_id,
            government_reference_id=gov_ref_id,
            connector_id=connector.id,
        )
        db.add(mapping)

        # Update grievance
        grievance.government_reference_id = gov_ref_id
        grievance.connector_id = connector.id

        logger.info(
            "Grievance %s submitted to government → ref:%s",
            grievance.grievance_id,
            gov_ref_id,
        )
        return gov_ref_id

    # ── Status sync ───────────────────────────────────────────

    async def sync_status(
        self, db: AsyncSession, grievance: Grievance
    ) -> tuple[str, str]:
        """
        Poll the government system and normalize status.
        Returns (raw_gov_status, normalized_platform_status).
        """
        if not grievance.government_reference_id or not grievance.connector_id:
            raise UnprocessableError("Grievance has not been submitted to a government system")

        conn_result = await db.execute(
            select(GovernmentConnector).where(GovernmentConnector.id == grievance.connector_id)
        )
        connector = conn_result.scalar_one_or_none()
        if connector is None:
            raise NotFoundError("Government connector")

        adapter = get_connector(connector.connector_type)
        raw_status = await adapter.get_status(grievance.government_reference_id, connector)

        # Normalize using connector-specific map, fallback to global map
        status_map: dict = connector.status_map or {}
        normalized = (
            status_map.get(raw_status.lower())
            or UNIFIED_STATUS_MAP.get(raw_status.lower())
            or GrievanceStatus.IN_PROGRESS.value
        )

        # Update last synced timestamp in mapping
        await db.execute(
            select(ReferenceIDMapping).where(
                ReferenceIDMapping.grievance_id == grievance.id,
                ReferenceIDMapping.government_reference_id == grievance.government_reference_id,
            )
        )

        return raw_status, normalized


government_registry_service = GovernmentRegistryService()


# ── Import guard ──────────────────────────────────────────────
def _ensure_import() -> None:
    from app.core.exceptions import UnprocessableError  # noqa: F401
