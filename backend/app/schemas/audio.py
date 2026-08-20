"""
Audio upload and processing Pydantic schemas.
"""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class AudioUploadResponse(BaseModel):
    """Returned immediately after an audio file is accepted."""
    grievance_id: str = Field(..., description="Internal UUID of the newly-created grievance")
    job_id: str = Field(..., description="Celery task ID to poll for status")
    language_code: str
    language_name: str
    message: str = "Audio uploaded. Processing has started."


class AudioProcessingStatus(BaseModel):
    """Polling response for the async processing pipeline."""
    grievance_id: str
    job_id: str
    status: str                   # Celery task state: PENDING / STARTED / SUCCESS / FAILURE
    grievance_status: str         # GrievanceStatus enum value
    progress_percent: Optional[int] = None
    error: Optional[str] = None


class StructuredGrievance(BaseModel):
    """
    Structured output from the (mock) LLM classification step.
    Stored as JSONB in the grievances table.
    """
    description: str = Field(..., description="Cleaned English description of the complaint")
    category: str = Field(..., description="Detected category (e.g. 'Water Supply')")
    department: str = Field(..., description="Suggested government department")
    location_state: Optional[str] = None
    location_district: Optional[str] = None
    location_city: Optional[str] = None
    location_raw: Optional[str] = None
    priority: str = Field("MEDIUM", description="LOW | MEDIUM | HIGH | CRITICAL")
    missing_information: list[str] = Field(
        default_factory=list,
        description="List of fields the AI could not determine",
    )
    confidence_score: float = Field(0.0, ge=0.0, le=1.0)
    is_mock: bool = False
