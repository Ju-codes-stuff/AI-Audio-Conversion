"""
Notification Service — multi-channel delivery with mock providers for dev.

Channels:
  • SMS        (MSG91 / Twilio — mock for dev)
  • WhatsApp   (Meta Cloud API — mock for dev)
  • Email      (SMTP / SendGrid — mock for dev)
  • Push       (FCM — mock for dev)
  • In-App     (stored in DB, picked up by frontend polling)

All providers implement the NotificationChannel abstract base.
Set *_PROVIDER=mock in .env to use console-only mock output.
"""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.notification import Notification, NotificationChannel

logger = logging.getLogger(__name__)


# ── Abstract base ─────────────────────────────────────────────

class BaseNotificationChannel(ABC):
    @abstractmethod
    async def send(self, recipient: str, title: str, message: str) -> bool:
        """Send a notification. Returns True on success."""
        ...


# ── Mock channels ─────────────────────────────────────────────

class MockSMSChannel(BaseNotificationChannel):
    async def send(self, recipient: str, title: str, message: str) -> bool:
        logger.info("[MOCK SMS] To:%s | %s — %s", recipient, title, message)
        return True


class MockWhatsAppChannel(BaseNotificationChannel):
    async def send(self, recipient: str, title: str, message: str) -> bool:
        logger.info("[MOCK WhatsApp] To:%s | %s — %s", recipient, title, message)
        return True


class MockEmailChannel(BaseNotificationChannel):
    async def send(self, recipient: str, title: str, message: str) -> bool:
        logger.info("[MOCK Email] To:%s | Subject:%s\n%s", recipient, title, message)
        return True


class MockPushChannel(BaseNotificationChannel):
    async def send(self, recipient: str, title: str, message: str) -> bool:
        logger.info("[MOCK Push] Token:%s | %s — %s", recipient, title, message)
        return True


# ── Factory ───────────────────────────────────────────────────

def _get_channel(channel: NotificationChannel) -> BaseNotificationChannel:
    # Extend this factory when adding real providers
    return {
        NotificationChannel.SMS: MockSMSChannel(),
        NotificationChannel.WHATSAPP: MockWhatsAppChannel(),
        NotificationChannel.EMAIL: MockEmailChannel(),
        NotificationChannel.PUSH: MockPushChannel(),
        NotificationChannel.IN_APP: MockPushChannel(),  # In-app stored in DB only
    }[channel]


# ── Notification Service ──────────────────────────────────────

class NotificationService:
    async def send_and_store(
        self,
        db: AsyncSession,
        user_id: str,
        title: str,
        message: str,
        channel: NotificationChannel,
        recipient_address: Optional[str],  # phone / email / fcm token
        grievance_id: Optional[str] = None,
    ) -> Notification:
        """Send a notification via the specified channel and persist to DB."""
        sent_at: Optional[datetime] = None
        if recipient_address:
            provider = _get_channel(channel)
            success = await provider.send(recipient_address, title, message)
            if success:
                sent_at = datetime.now(timezone.utc)

        notification = Notification(
            user_id=user_id,
            grievance_id=grievance_id,
            channel=channel,
            title=title,
            message=message,
            sent_at=sent_at,
        )
        db.add(notification)
        await db.flush()
        return notification

    async def notify_grievance_created(
        self, db: AsyncSession, grievance_id: str, grv_id: str, user
    ) -> None:
        title = "Grievance Received"
        message = (
            f"Your grievance {grv_id} has been received and is being processed. "
            "You will be notified once the AI analysis is complete."
        )
        await self._notify_all_channels(db, user, title, message, grievance_id)

    async def notify_ai_ready(
        self, db: AsyncSession, grievance_id: str, grv_id: str, user
    ) -> None:
        title = "Please Review Your Complaint"
        message = (
            f"AI has analysed your grievance {grv_id}. "
            "Please review and confirm the details before submission."
        )
        await self._notify_all_channels(db, user, title, message, grievance_id)

    async def notify_submitted(
        self, db: AsyncSession, grievance_id: str, grv_id: str, user
    ) -> None:
        title = "Grievance Submitted"
        message = (
            f"Your grievance {grv_id} has been submitted to the concerned department. "
            "Track status using your grievance ID."
        )
        await self._notify_all_channels(db, user, title, message, grievance_id)

    async def notify_status_change(
        self, db: AsyncSession, grievance_id: str, grv_id: str, user, new_status: str
    ) -> None:
        title = "Status Update"
        message = f"Grievance {grv_id} status has been updated to: {new_status}."
        await self._notify_all_channels(db, user, title, message, grievance_id)

    async def _notify_all_channels(
        self, db: AsyncSession, user, title: str, message: str, grievance_id: str
    ) -> None:
        """Fan-out notification to all relevant channels for a user."""
        if user.phone_number:
            await self.send_and_store(
                db, user.id, title, message,
                NotificationChannel.SMS, user.phone_number, grievance_id
            )
            await self.send_and_store(
                db, user.id, title, message,
                NotificationChannel.WHATSAPP, user.phone_number, grievance_id
            )
        if user.email:
            await self.send_and_store(
                db, user.id, title, message,
                NotificationChannel.EMAIL, user.email, grievance_id
            )
        # Always store in-app notification
        await self.send_and_store(
            db, user.id, title, message,
            NotificationChannel.IN_APP, None, grievance_id
        )


notification_service = NotificationService()
