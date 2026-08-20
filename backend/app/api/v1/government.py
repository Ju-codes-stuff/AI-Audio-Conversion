"""
Government API — Phase 3 registry lookup, submission, and status sync.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.dependencies import AdminUser, CurrentUser, DBSession
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.government_connector import GovernmentConnector
from app.models.grievance import GrievanceStatus
from app.models.service import GovernmentService
from app.schemas.government import (
    ConnectorOut,
    GovernmentServiceOut,
    GovernmentStatusSyncResponse,
    GovernmentSubmitRequest,
    GovernmentSubmitResponse,
    ServiceLookupRequest,
    ServiceLookupResponse,
)
from app.services.government_service import government_registry_service
from app.services.grievance_service import grievance_service
from app.services.notification_service import notification_service

router = APIRouter(prefix="/government", tags=["Government (Phase 3)"])


@router.get("/registry", response_model=List[GovernmentServiceOut])
async def list_registry(
    db: DBSession,
    category: str | None = Query(None),
    state: str | None = Query(None),
):
    """List government services in the registry, with optional filters."""
    query = select(GovernmentService).where(GovernmentService.is_active == True)  # noqa: E712
    if category:
        query = query.where(GovernmentService.category_code == category)
    if state:
        query = query.where(GovernmentService.state == state)
    result = await db.execute(query.order_by(GovernmentService.service_name))
    return list(result.scalars().all())


@router.post("/registry/lookup", response_model=ServiceLookupResponse)
async def lookup_service(body: ServiceLookupRequest, db: DBSession):
    """
    Find the best-matching government service(s) for a grievance category + geography.
    Returns ranked list and a recommended primary service.
    """
    services = await government_registry_service.find_services(
        db, body.category, body.state, body.district
    )
    return ServiceLookupResponse(
        services=[GovernmentServiceOut.model_validate(s) for s in services],
        recommended=GovernmentServiceOut.model_validate(services[0]) if services else None,
    )


@router.get("/connectors", response_model=List[ConnectorOut])
async def list_connectors(admin: AdminUser, db: DBSession):
    """List all registered government connectors (admin only)."""
    result = await db.execute(
        select(GovernmentConnector).order_by(GovernmentConnector.connector_name)
    )
    return list(result.scalars().all())


@router.post("/submit", response_model=GovernmentSubmitResponse)
async def submit_to_government(
    body: GovernmentSubmitRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Submit a CONFIRMED grievance to the specified government service.
    Creates a ReferenceIDMapping and returns the government reference ID.
    """
    g = await grievance_service.get_by_id(db, body.grievance_id)
    if g.user_id != current_user.id and not current_user.is_admin:
        raise ForbiddenError()

    if g.status != GrievanceStatus.CONFIRMED:
        from app.core.exceptions import UnprocessableError
        raise UnprocessableError(
            f"Grievance must be in CONFIRMED status to submit (current: {g.status.value})"
        )

    gov_ref_id = await government_registry_service.submit_to_government(
        db, g, body.service_code
    )

    # Advance to SUBMITTED
    await grievance_service.transition(
        db, g, GrievanceStatus.SUBMITTED,
        changed_by=current_user.id,
        notes=f"Submitted to government service {body.service_code}",
    )
    await db.commit()

    # Notify citizen
    await notification_service.notify_submitted(db, g.id, g.grievance_id, current_user)
    await db.commit()

    # Get connector type for response
    from sqlalchemy import select as sa_select
    conn_result = await db.execute(
        sa_select(GovernmentConnector).where(GovernmentConnector.id == g.connector_id)
    )
    connector = conn_result.scalar_one_or_none()

    return GovernmentSubmitResponse(
        platform_id=g.grievance_id,
        government_reference_id=gov_ref_id,
        connector_type=connector.connector_type.value if connector else "UNKNOWN",
        submitted_at=g.submitted_at or datetime.now(timezone.utc),
        message=f"Grievance {g.grievance_id} submitted. Government reference: {gov_ref_id}",
    )


@router.post("/{grievance_id}/sync-status", response_model=GovernmentStatusSyncResponse)
async def sync_government_status(
    grievance_id: str,
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Poll the government system for the latest status and sync it to the platform.
    """
    g = await grievance_service.get_by_id(db, grievance_id)
    if g.user_id != current_user.id and not current_user.is_admin:
        raise ForbiddenError()

    raw_status, normalized_status = await government_registry_service.sync_status(db, g)

    # Apply normalized status if it advances the grievance
    try:
        new_status = GrievanceStatus(normalized_status)
        await grievance_service.transition(
            db, g, new_status,
            notes=f"Status synced from government: {raw_status}",
        )
        await db.commit()
    except Exception:
        pass  # No transition needed if status unchanged

    return GovernmentStatusSyncResponse(
        platform_id=g.grievance_id,
        government_reference_id=g.government_reference_id or "",
        government_raw_status=raw_status,
        normalized_status=normalized_status,
        last_synced_at=datetime.now(timezone.utc),
    )
