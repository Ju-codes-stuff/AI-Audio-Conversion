"""
Models package — imports all ORM classes so Alembic autodiscovers them.
"""
from app.models.user import User
from app.models.grievance import Grievance, GrievanceStatus, GrievancePriority
from app.models.transcript import Transcript
from app.models.translation import Translation
from app.models.department import Department, Category
from app.models.service import GovernmentService, SubmissionMethod
from app.models.status_history import StatusHistory
from app.models.notification import Notification, NotificationChannel
from app.models.government_connector import (
    GovernmentConnector,
    ReferenceIDMapping,
    ConnectorType,
    ConnectorAuthType,
)

__all__ = [
    "User",
    "Grievance",
    "GrievanceStatus",
    "GrievancePriority",
    "Transcript",
    "Translation",
    "Department",
    "Category",
    "GovernmentService",
    "SubmissionMethod",
    "StatusHistory",
    "Notification",
    "NotificationChannel",
    "GovernmentConnector",
    "ReferenceIDMapping",
    "ConnectorType",
    "ConnectorAuthType",
]
