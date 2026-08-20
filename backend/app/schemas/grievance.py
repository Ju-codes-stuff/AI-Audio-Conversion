"""
Grievance Pydantic schemas — full lifecycle request/response models.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.models.grievance import GrievancePriority, GrievanceStatus


# ── Nested sub-schemas ────────────────────────────────────────

class TranscriptOut(BaseModel):
    id: str
    language_code: str
    text: str
    confidence_score: Optional[float] = None
    asr_model_version: Optional[str] = None
    is_mock: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class TranslationOut(BaseModel):
    id: str
    source_language: str
    target_language: str
    source_text: str
    translated_text: str
    translation_model_version: Optional[str] = None
    is_mock: bool
    created_at: datetime
    model_config = {"from_attributes": True}


class StatusHistoryOut(BaseModel):
    id: str
    from_status: Optional[str] = None
    to_status: str
    notes: Optional[str] = None
    created_at: datetime
    model_config = {"from_attributes": True}


# ── Grievance responses ───────────────────────────────────────

class GrievanceSummary(BaseModel):
    """Lightweight list-view response."""
    id: str
    grievance_id: Optional[str] = None
    status: GrievanceStatus
    priority: Optional[GrievancePriority] = None
    language_code: str
    language_name: Optional[str] = None
    category: Optional[str] = None
    location_state: Optional[str] = None
    location_district: Optional[str] = None
    created_at: datetime
    model_config = {"from_attributes": True}


class GrievanceDetail(BaseModel):
    """Full grievance detail including AI outputs."""
    id: str
    grievance_id: Optional[str] = None
    user_id: str
    status: GrievanceStatus
    priority: Optional[GrievancePriority] = None
    language_code: str
    language_name: Optional[str] = None
    audio_storage_key: Optional[str] = None
    audio_duration_seconds: Optional[int] = None
    raw_transcript: Optional[str] = None
    english_text: Optional[str] = None
    structured_data: Optional[Dict[str, Any]] = None
    category: Optional[str] = None
    location_state: Optional[str] = None
    location_district: Optional[str] = None
    location_city: Optional[str] = None
    location_raw: Optional[str] = None
    government_reference_id: Optional[str] = None
    transcripts: List[TranscriptOut] = []
    translations: List[TranslationOut] = []
    status_history: List[StatusHistoryOut] = []
    submitted_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


# ── Citizen confirmation ──────────────────────────────────────

class GrievanceConfirmRequest(BaseModel):
    """
    Citizen reviews AI-generated structured data and optionally corrects fields
    before confirming submission.
    """
    description: Optional[str] = Field(None, max_length=2000)
    category: Optional[str] = Field(None, max_length=100)
    location_state: Optional[str] = Field(None, max_length=100)
    location_district: Optional[str] = Field(None, max_length=100)
    location_city: Optional[str] = Field(None, max_length=100)
    priority: Optional[GrievancePriority] = None


# ── Admin ─────────────────────────────────────────────────────

class AdminStatusUpdateRequest(BaseModel):
    status: GrievanceStatus
    notes: Optional[str] = Field(None, max_length=1000)


class GrievancePaginatedResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[GrievanceSummary]


# ── Analytics ─────────────────────────────────────────────────

class DepartmentAnalytics(BaseModel):
    department_name: str
    total: int
    pending: int
    resolved: int
    avg_resolution_days: Optional[float] = None


class AdminDashboardResponse(BaseModel):
    total_grievances: int
    pending: int
    in_progress: int
    resolved: int
    closed: int
    failed: int
    today_new: int
    department_breakdown: List[DepartmentAnalytics]
    category_breakdown: List[Dict[str, Any]]
    language_breakdown: List[Dict[str, Any]]
