"""
LLM Service — MOCK ONLY for Phase 1 PoC.

This service is intentionally left as a mock. It applies simple keyword/rule-based
heuristics to produce a StructuredGrievance from English text.

When you are ready to integrate a real LLM (OpenAI, Gemini, local LLaMA):
  1. Set LLM_USE_MOCK=false in .env
  2. Implement _real_classify() below
  3. The rest of the pipeline remains unchanged

The mock uses pattern matching on common Indian grievance keywords to
produce realistic-looking structured output for demo and testing purposes.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

from app.schemas.audio import StructuredGrievance

logger = logging.getLogger(__name__)

# ── Mock classification rules ─────────────────────────────────
# Each entry: (regex pattern, category, department)
_RULES: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"water|supply|tap|pipe|pipeline|bore|well", re.I),
     "Water Supply", "Municipal Water Department"),
    (re.compile(r"road|pothole|street|highway|path|footpath|divider", re.I),
     "Road & Infrastructure", "Public Works Department"),
    (re.compile(r"electric|power|outage|blackout|transformer|wire|voltage", re.I),
     "Electricity", "State Electricity Board"),
    (re.compile(r"garbage|waste|sanitation|drain|sewer|toilet|latrine|open defecation", re.I),
     "Sanitation & Waste", "Municipal Sanitation Department"),
    (re.compile(r"school|teacher|education|mid-day meal|uniform|scholarship", re.I),
     "Education", "Department of Education"),
    (re.compile(r"hospital|health|doctor|medicine|ambulance|clinic|ration", re.I),
     "Healthcare", "Department of Health"),
    (re.compile(r"pension|aadhaar|certificate|birth|death|caste|income|domicile", re.I),
     "Civil Services", "Revenue Department"),
    (re.compile(r"police|crime|theft|assault|harassment|safety|fir", re.I),
     "Law & Order", "Police Department"),
    (re.compile(r"land|property|encroachment|boundary|survey|mutation", re.I),
     "Land Records", "Revenue Department"),
    (re.compile(r"gas|lpg|cylinder|cook|fuel|kerosene", re.I),
     "Fuel & Energy", "Food & Civil Supplies"),
]

_PRIORITY_HIGH = re.compile(
    r"emergency|urgent|critical|dead|death|accident|fire|flood|collaps", re.I
)
_PRIORITY_CRITICAL = re.compile(
    r"life.threaten|disaster|explosion|pandemic|epidemic", re.I
)

_STATES = [
    "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh",
    "Goa", "Gujarat", "Haryana", "Himachal Pradesh", "Jharkhand", "Karnataka",
    "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya", "Mizoram",
    "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Tamil Nadu",
    "Telangana", "Tripura", "Uttar Pradesh", "Uttarakhand", "West Bengal",
    "Delhi", "Jammu & Kashmir", "Ladakh", "Puducherry", "Chandigarh",
]
_STATE_RE = re.compile(
    r"\b(" + "|".join(re.escape(s) for s in _STATES) + r")\b", re.I
)


class LLMService:
    """
    Mock classification service.
    Replace _real_classify with a real LLM call when ready.
    """

    def __init__(self) -> None:
        self.use_mock = True  # Always mock until a real LLM is configured

    async def classify(self, english_text: str) -> StructuredGrievance:
        """
        Extract structured grievance fields from English text.

        Args:
            english_text: English translation of the citizen's spoken grievance.

        Returns:
            StructuredGrievance with inferred category, department, etc.
        """
        if self.use_mock:
            return self._mock_classify(english_text)
        # Future: return await self._real_classify(english_text)

    def _mock_classify(self, text: str) -> StructuredGrievance:
        """Keyword/rule-based mock classification."""
        category = "General"
        department = "General Administration"

        for pattern, cat, dept in _RULES:
            if pattern.search(text):
                category = cat
                department = dept
                break

        # Priority detection
        if _PRIORITY_CRITICAL.search(text):
            priority = "CRITICAL"
        elif _PRIORITY_HIGH.search(text):
            priority = "HIGH"
        elif any(w in text.lower() for w in ["days", "week", "month", "long time"]):
            priority = "MEDIUM"
        else:
            priority = "LOW"

        # Location extraction
        state_match = _STATE_RE.search(text)
        location_state: Optional[str] = state_match.group(1) if state_match else None

        # Build description: first 300 chars cleaned up
        description = text.strip()
        if len(description) > 300:
            description = description[:297] + "..."

        # Check for missing fields
        missing: list[str] = []
        if not location_state:
            missing.append("location_state")
        if "district" not in text.lower() and not any(
            w in text.lower() for w in ["area", "ward", "sector", "block"]
        ):
            missing.append("location_district")

        logger.info(
            "[MOCK LLM] category=%s department=%s priority=%s state=%s",
            category, department, priority, location_state,
        )

        return StructuredGrievance(
            description=description,
            category=category,
            department=department,
            location_state=location_state,
            location_district=None,
            location_city=None,
            location_raw=None,
            priority=priority,
            missing_information=missing,
            confidence_score=0.72,
            is_mock=True,
        )


llm_service = LLMService()
