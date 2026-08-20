"""
Government registry and connector Pydantic schemas — Phase 3.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.models.government_connector import ConnectorType, ConnectorAuthType
from app.models.service import SubmissionMethod


# ── Service Registry ─────────────────────────────────────────

class GovernmentServiceOut(BaseModel):
    id: str
    service_name: str
    service_code: str
    description: Optional[str] = None
    category_code: Optional[str] = None
    state: Optional[str] = None
    district: Optional[str] = None
    portal_url: Optional[str] = None
    submission_method: SubmissionMethod
    required_fields: Optional[Dict[str, Any]] = None
    is_active: bool
    model_config = {"from_attributes": True}


class ServiceLookupRequest(BaseModel):
    """Find matching government services for a structured grievance."""
    category: str
    state: Optional[str] = None
    district: Optional[str] = None


class ServiceLookupResponse(BaseModel):
    services: List[GovernmentServiceOut]
    recommended: Optional[GovernmentServiceOut] = None


# ── Connector ────────────────────────────────────────────────

class ConnectorOut(BaseModel):
    id: str
    connector_name: str
    connector_type: ConnectorType
    description: Optional[str] = None
    base_url: Optional[str] = None
    auth_type: ConnectorAuthType
    is_active: bool
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Submission & Status Sync ──────────────────────────────────

class GovernmentSubmitRequest(BaseModel):
    """Trigger Phase 3 submission to a specific government service."""
    grievance_id: str = Field(..., description="Internal UUID of the confirmed grievance")
    service_code: str = Field(..., description="Target government service code")


class GovernmentSubmitResponse(BaseModel):
    platform_id: str            # GRV-YYYY-NNNNNN
    government_reference_id: str
    connector_type: str
    submitted_at: datetime
    message: str


class GovernmentStatusSyncResponse(BaseModel):
    """Result of polling the government system for a status update."""
    platform_id: str
    government_reference_id: str
    government_raw_status: str
    normalized_status: str      # Platform GrievanceStatus enum value
    last_synced_at: datetime


# ── Status normalization map ──────────────────────────────────
# Canonical mapping: raw government statuses → platform statuses
UNIFIED_STATUS_MAP: Dict[str, str] = {
    # CPGRAMS-style
    "registered": "SUBMITTED",
    "assigned": "ACKNOWLEDGED",
    "under review": "IN_PROGRESS",
    "pending": "IN_PROGRESS",
    "action taken": "RESOLVED",
    "resolved": "RESOLVED",
    "closed": "CLOSED",
    # Generic patterns
    "open": "SUBMITTED",
    "in progress": "IN_PROGRESS",
    "done": "RESOLVED",
}
