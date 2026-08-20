"""
Notifications API — citizen notification inbox.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, Query
from pydantic import BaseModel
from sqlalchemy import select, update

from app.core.dependencies import CurrentUser, DBSession
from app.models.notification import Notification, NotificationChannel


class NotificationOut(BaseModel):
    id: str
    grievance_id: str | None = None
    channel: NotificationChannel
    title: str
    message: str
    is_read: bool
    sent_at: datetime | None = None
    read_at: datetime | None = None
    created_at: datetime
    model_config = {"from_attributes": True}


router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("/my", response_model=List[NotificationOut])
async def get_my_notifications(
    current_user: CurrentUser,
    db: DBSession,
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
):
    """Return the current user's notifications, newest first."""
    query = (
        select(Notification)
        .where(Notification.user_id == current_user.id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
    )
    if unread_only:
        query = query.where(Notification.is_read == False)  # noqa: E712

    result = await db.execute(query)
    return list(result.scalars().all())


@router.put("/{notification_id}/read", response_model=NotificationOut)
async def mark_as_read(
    notification_id: str,
    current_user: CurrentUser,
    db: DBSession,
):
    """Mark a single notification as read."""
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id,
            Notification.user_id == current_user.id,
        )
    )
    n = result.scalar_one_or_none()
    if n is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Notification")

    n.is_read = True
    n.read_at = datetime.now(timezone.utc)
    return n


@router.put("/my/read-all")
async def mark_all_read(current_user: CurrentUser, db: DBSession):
    """Mark all of the user's unread notifications as read."""
    now = datetime.now(timezone.utc)
    await db.execute(
        update(Notification)
        .where(
            Notification.user_id == current_user.id,
            Notification.is_read == False,  # noqa: E712
        )
        .values(is_read=True, read_at=now)
    )
    return {"message": "All notifications marked as read"}
