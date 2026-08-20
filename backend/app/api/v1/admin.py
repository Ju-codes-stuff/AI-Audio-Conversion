"""
Admin API — dashboard, analytics, and manual status management.
Requires is_admin=True on the authenticated user.
"""
from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, Query
from sqlalchemy import case, func, select

from app.core.dependencies import AdminUser, DBSession
from app.core.exceptions import NotFoundError
from app.models.department import Department
from app.models.grievance import Grievance, GrievanceStatus
from app.schemas.grievance import (
    AdminDashboardResponse,
    AdminStatusUpdateRequest,
    DepartmentAnalytics,
    GrievanceDetail,
    GrievancePaginatedResponse,
    GrievanceSummary,
)
from app.services.grievance_service import grievance_service
from app.services.notification_service import notification_service

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/dashboard", response_model=AdminDashboardResponse)
async def dashboard(admin: AdminUser, db: DBSession):
    """
    Aggregated grievance counts and breakdowns for the admin dashboard.
    """
    from datetime import date, datetime, timezone

    # ── Total counts by status ────────────────────────────────
    counts_result = await db.execute(
        select(Grievance.status, func.count().label("cnt")).group_by(Grievance.status)
    )
    counts: Dict[str, int] = {row.status.value: row.cnt for row in counts_result}

    today_start = datetime.combine(date.today(), datetime.min.time()).replace(tzinfo=timezone.utc)
    today_result = await db.execute(
        select(func.count()).where(Grievance.created_at >= today_start)
    )
    today_new = today_result.scalar_one()

    # ── Department breakdown ───────────────────────────────────
    dept_result = await db.execute(
        select(
            Department.name,
            func.count(Grievance.id).label("total"),
            func.sum(
                case((Grievance.status.in_([
                    GrievanceStatus.CREATED, GrievanceStatus.PROCESSING,
                    GrievanceStatus.AI_GENERATED, GrievanceStatus.CONFIRMED,
                ]), 1), else_=0)
            ).label("pending"),
            func.sum(
                case((Grievance.status == GrievanceStatus.RESOLVED, 1), else_=0)
            ).label("resolved"),
        )
        .join(Grievance, Grievance.department_id == Department.id, isouter=True)
        .group_by(Department.name)
    )
    dept_breakdown = [
        DepartmentAnalytics(
            department_name=row.name,
            total=row.total or 0,
            pending=row.pending or 0,
            resolved=row.resolved or 0,
        )
        for row in dept_result
    ]

    # ── Category breakdown ────────────────────────────────────
    cat_result = await db.execute(
        select(Grievance.category, func.count().label("cnt"))
        .where(Grievance.category.is_not(None))
        .group_by(Grievance.category)
        .order_by(func.count().desc())
        .limit(10)
    )
    cat_breakdown = [{"category": row.category, "count": row.cnt} for row in cat_result]

    # ── Language breakdown ────────────────────────────────────
    lang_result = await db.execute(
        select(Grievance.language_code, Grievance.language_name, func.count().label("cnt"))
        .group_by(Grievance.language_code, Grievance.language_name)
        .order_by(func.count().desc())
    )
    lang_breakdown = [
        {"language_code": r.language_code, "language_name": r.language_name, "count": r.cnt}
        for r in lang_result
    ]

    return AdminDashboardResponse(
        total_grievances=sum(counts.values()),
        pending=counts.get("CREATED", 0) + counts.get("PROCESSING", 0) + counts.get("AI_GENERATED", 0),
        in_progress=counts.get("IN_PROGRESS", 0) + counts.get("ACKNOWLEDGED", 0),
        resolved=counts.get("RESOLVED", 0),
        closed=counts.get("CLOSED", 0),
        failed=counts.get("FAILED", 0),
        today_new=today_new,
        department_breakdown=dept_breakdown,
        category_breakdown=cat_breakdown,
        language_breakdown=lang_breakdown,
    )


@router.get("/grievances", response_model=GrievancePaginatedResponse)
async def list_all_grievances(
    admin: AdminUser,
    db: DBSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: GrievanceStatus | None = Query(None),
    language_code: str | None = Query(None),
    category: str | None = Query(None),
):
    """Paginated list of all grievances with optional filters."""
    query = select(Grievance).order_by(Grievance.created_at.desc())
    count_query = select(func.count()).select_from(Grievance)

    if status:
        query = query.where(Grievance.status == status)
        count_query = count_query.where(Grievance.status == status)
    if language_code:
        query = query.where(Grievance.language_code == language_code)
        count_query = count_query.where(Grievance.language_code == language_code)
    if category:
        query = query.where(Grievance.category == category)
        count_query = count_query.where(Grievance.category == category)

    total = (await db.execute(count_query)).scalar_one()
    skip = (page - 1) * page_size
    items = list((await db.execute(query.offset(skip).limit(page_size))).scalars().all())

    return GrievancePaginatedResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[GrievanceSummary.model_validate(g) for g in items],
    )


@router.put("/grievances/{grievance_id}/status", response_model=GrievanceDetail)
async def update_grievance_status(
    grievance_id: str,
    body: AdminStatusUpdateRequest,
    admin: AdminUser,
    db: DBSession,
):
    """Manually advance or update a grievance status (admin only)."""
    g = await grievance_service.get_by_id(db, grievance_id)
    g = await grievance_service.transition(
        db, g, body.status,
        changed_by=admin.id,
        notes=body.notes or f"Manual update by admin {admin.id}",
    )
    await db.commit()

    # Notify citizen of status change
    from sqlalchemy import select as sa_select
    from app.models.user import User
    user_result = await db.execute(sa_select(User).where(User.id == g.user_id))
    user = user_result.scalar_one_or_none()
    if user:
        await notification_service.notify_status_change(
            db, g.id, g.grievance_id, user, body.status.value
        )
        await db.commit()

    return GrievanceDetail.model_validate(g)
