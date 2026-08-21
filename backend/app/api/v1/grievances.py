"""
Grievances API — citizen-facing CRUD + lifecycle endpoints.
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.core.dependencies import CurrentUser, DBSession
from app.core.exceptions import ForbiddenError
from app.schemas.grievance import (
    GrievanceConfirmRequest,
    GrievanceDetail,
    GrievancePaginatedResponse,
    GrievanceSummary,
)
from app.services.grievance_service import grievance_service
from app.services.notification_service import notification_service

router = APIRouter(prefix="/grievances", tags=["Grievances"])


@router.get("/my", response_model=GrievancePaginatedResponse)
async def list_my_grievances(
    current_user: CurrentUser,
    db: DBSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    """Return the authenticated citizen's grievances (paginated)."""
    skip = (page - 1) * page_size
    total, items = await grievance_service.list_for_user(
        db, current_user.id, skip=skip, limit=page_size
    )
    return GrievancePaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[GrievanceSummary.model_validate(g) for g in items],
    )


@router.get("/{identifier}", response_model=GrievanceDetail)
async def get_grievance(
    identifier: str,
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Fetch a grievance by internal UUID or GRV-YYYY-NNNNNN ID.
    Citizens can only view their own grievances; admins see all.
    """
    # Try GRV-... format first, then UUID
    if identifier.startswith("GRV-"):
        g = await grievance_service.get_by_grv_id(db, identifier)
    else:
        g = await grievance_service.get_by_id(db, identifier)

    if g.user_id != current_user.id and not current_user.is_admin:
        raise ForbiddenError()

    return GrievanceDetail.model_validate(g)


@router.put("/{grievance_id}/confirm", response_model=GrievanceDetail)
async def confirm_grievance(
    grievance_id: str,
    body: GrievanceConfirmRequest,
    current_user: CurrentUser,
    db: DBSession,
):
    """
    Citizen reviews AI-generated output and confirms (or corrects) fields.
    Advances status from AI_GENERATED → CONFIRMED.
    Returns the confirmed grievance with the unified GRV ID.
    """
    g = await grievance_service.get_by_id(db, grievance_id)
    if g.user_id != current_user.id:
        raise ForbiddenError()

    g = await grievance_service.confirm(db, g, body, current_user.id)
    
    # Notify confirmation
    await notification_service.notify_submitted(
        db, g.id, g.grievance_id, current_user
    )

    # Serialize to Pydantic model BEFORE flushing/committing to avoid MissingGreenlet on expired attributes
    response_data = GrievanceDetail.model_validate(g)
    
    await db.commit()

    return response_data


@router.get("/{grievance_id}/track", response_model=GrievanceSummary)
async def track_grievance(
    grievance_id: str,
    db: DBSession,
):
    """
    Public tracking endpoint — no auth required.
    Only returns minimal status information (no PII).
    """
    if grievance_id.startswith("GRV-"):
        g = await grievance_service.get_by_grv_id(db, grievance_id)
    else:
        g = await grievance_service.get_by_id(db, grievance_id)
    return GrievanceSummary.model_validate(g)
