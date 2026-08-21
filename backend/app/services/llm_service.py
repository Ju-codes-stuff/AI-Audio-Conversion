"""
LLM Service — Provider chain: Ollama (local) → Gemini → OpenAI → Mock fallback.

Provider priority:
  1. Ollama   — local, free, private (requires: ollama installed + model pulled)
  2. Gemini   — Google AI, free tier 1500 req/day (requires: GEMINI_API_KEY)
  3. OpenAI   — paid, reliable (requires: OPENAI_API_KEY)
  4. Mock     — regex/keyword classifier, always works, used for dev

All real providers produce STRUCTURED JSON output enforced via response schemas
or JSON mode, so no fragile string-parsing is needed.

Setup:
  1. Install Ollama: https://ollama.ai
  2. Pull a model:   ollama pull gemma3:4b
  3. Set in .env:    LLM_USE_MOCK=false
                     OLLAMA_ENABLED=true
"""
from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Optional

from app.config import settings
from app.schemas.audio import StructuredGrievance

logger = logging.getLogger(__name__)

# ── Shared prompt ─────────────────────────────────────────────
SYSTEM_PROMPT = """You are an AI assistant for India's government grievance system.
Your job is to extract structured information from English grievance text.

You MUST respond with valid JSON only — no markdown, no extra text.
The JSON must match this exact schema:
{
  "description": "Clear 1-3 sentence summary of the complaint",
  "category": "One of: Water Supply | Road & Infrastructure | Electricity | Sanitation & Waste | Education | Healthcare | Civil Services | Law & Order | Land Records | Fuel & Energy | Agriculture | Housing | Transport | Employment | General",
  "department": "The specific government department responsible",
  "location_state": "Indian state name or null",
  "location_district": "District name or null",
  "location_city": "City/town/village or null",
  "priority": "One of: LOW | MEDIUM | HIGH | CRITICAL",
  "missing_information": ["list", "of", "missing", "fields"],
  "confidence_score": 0.0 to 1.0
}

Priority guide:
- CRITICAL: life-threatening, disaster, emergency
- HIGH: no water/power >3 days, accident, unsafe structure
- MEDIUM: recurring issue, affects daily life
- LOW: minor inconvenience, first occurrence

Respond with JSON only."""


def _make_user_prompt(text: str) -> str:
    return f"""Extract structured grievance information from this text:

"{text}"

Respond with valid JSON only."""


# ── Grievance categories ──────────────────────────────────────
_CATEGORIES = [
    "Water Supply", "Road & Infrastructure", "Electricity", "Sanitation & Waste",
    "Education", "Healthcare", "Civil Services", "Law & Order", "Land Records",
    "Fuel & Energy", "Agriculture", "Housing", "Transport", "Employment", "General",
]


class BaseLLMProvider(ABC):
    @abstractmethod
    async def classify(self, english_text: str) -> StructuredGrievance:
        ...

    def _parse_json_response(self, raw: str, is_mock: bool = False) -> StructuredGrievance:
        """Parse and validate LLM JSON response into StructuredGrievance."""
        # Strip markdown code fences if present
        cleaned = re.sub(r"```(?:json)?", "", raw).strip()
        # Extract JSON object
        match = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if match:
            cleaned = match.group(0)

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.error("LLM JSON parse error: %s | raw=%s", exc, raw[:300])
            raise ValueError(f"LLM returned invalid JSON: {exc}") from exc

        # Normalise and validate
        category = data.get("category", "General")
        if category not in _CATEGORIES:
            category = "General"

        priority = data.get("priority", "MEDIUM").upper()
        if priority not in ("LOW", "MEDIUM", "HIGH", "CRITICAL"):
            priority = "MEDIUM"

        confidence = float(data.get("confidence_score", 0.75))
        confidence = max(0.0, min(1.0, confidence))

        missing = data.get("missing_information", [])
        if not isinstance(missing, list):
            missing = []

        return StructuredGrievance(
            description=str(data.get("description", ""))[:1000],
            category=category,
            department=str(data.get("department", "General Administration")),
            location_state=data.get("location_state") or None,
            location_district=data.get("location_district") or None,
            location_city=data.get("location_city") or None,
            location_raw=None,
            priority=priority,
            missing_information=missing,
            confidence_score=confidence,
            is_mock=is_mock,
        )


# ── Provider 1: Ollama (local) ────────────────────────────────
class OllamaLLMProvider(BaseLLMProvider):
    """
    Uses Ollama's OpenAI-compatible REST API at localhost:11434.
    Zero cost, full privacy, works offline.
    Install: https://ollama.ai
    Model:   ollama pull gemma3:4b   (or llama3.2:3b / mistral:7b)
    """

    def available(self) -> bool:
        return settings.OLLAMA_ENABLED

    async def classify(self, english_text: str) -> StructuredGrievance:
        try:
            from openai import AsyncOpenAI  # lazy import
        except ImportError:
            raise RuntimeError("openai package not installed. Run: pip install openai")

        client = AsyncOpenAI(
            base_url=settings.OLLAMA_BASE_URL,
            api_key="ollama",   # Ollama accepts any string here
            timeout=settings.OLLAMA_TIMEOUT,
        )

        response = await client.chat.completions.create(
            model=settings.OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _make_user_prompt(english_text)},
            ],
            response_format={"type": "json_object"},  # Ollama JSON mode
            temperature=0.1,   # Low temperature for consistent classification
        )

        raw = response.choices[0].message.content or ""
        logger.info("Ollama response: model=%s tokens=%s",
                    settings.OLLAMA_MODEL,
                    response.usage.total_tokens if response.usage else "?")
        return self._parse_json_response(raw, is_mock=False)


# ── Provider 2: Google Gemini ─────────────────────────────────
class GeminiLLMProvider(BaseLLMProvider):
    """
    Uses Google Gemini API with JSON response mode.
    Free tier: 1500 requests/day with gemini-2.5-flash.
    Get key: https://aistudio.google.com/apikey
    """

    def available(self) -> bool:
        return bool(settings.GEMINI_API_KEY)

    async def classify(self, english_text: str) -> StructuredGrievance:
        try:
            import google.generativeai as genai  # lazy import
        except ImportError:
            raise RuntimeError("google-generativeai not installed. Run: pip install google-generativeai")

        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel(
            model_name=settings.GEMINI_MODEL,
            system_instruction=SYSTEM_PROMPT,
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.1,
            ),
        )
        response = await model.generate_content_async(_make_user_prompt(english_text))
        raw = response.text
        logger.info("Gemini response: model=%s chars=%d", settings.GEMINI_MODEL, len(raw))
        return self._parse_json_response(raw, is_mock=False)


# ── Provider 3: OpenAI ────────────────────────────────────────
class OpenAILLMProvider(BaseLLMProvider):
    """
    Uses OpenAI API with JSON mode.
    Get key: https://platform.openai.com/api-keys
    """

    def available(self) -> bool:
        return bool(settings.OPENAI_API_KEY)

    async def classify(self, english_text: str) -> StructuredGrievance:
        try:
            from openai import AsyncOpenAI  # lazy import
        except ImportError:
            raise RuntimeError("openai package not installed. Run: pip install openai")

        client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        response = await client.chat.completions.create(
            model=settings.OPENAI_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _make_user_prompt(english_text)},
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
        )
        raw = response.choices[0].message.content or ""
        logger.info("OpenAI response: model=%s tokens=%s",
                    settings.OPENAI_MODEL,
                    response.usage.total_tokens if response.usage else "?")
        return self._parse_json_response(raw, is_mock=False)


# ── Provider 4: Mock (regex/keyword) ─────────────────────────
_RULES: list[tuple[re.Pattern, str, str]] = [
    (re.compile(r"water|supply|tap|pipe|pipeline|bore|well", re.I),
     "Water Supply", "Municipal Water Department"),
    (re.compile(r"road|pothole|street|highway|path|footpath|divider", re.I),
     "Road & Infrastructure", "Public Works Department"),
    (re.compile(r"electric|power|outage|blackout|transformer|wire|voltage", re.I),
     "Electricity", "State Electricity Board"),
    (re.compile(r"garbage|waste|sanitation|drain|sewer|toilet|latrine", re.I),
     "Sanitation & Waste", "Municipal Sanitation Department"),
    (re.compile(r"school|teacher|education|mid.day meal|uniform|scholarship", re.I),
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
_PRIO_CRITICAL = re.compile(r"life.threaten|disaster|explosion|pandemic|epidemic", re.I)
_PRIO_HIGH = re.compile(r"emergency|urgent|critical|dead|death|accident|fire|flood|collaps", re.I)
_STATES = re.compile(
    r"\b(Andhra Pradesh|Arunachal Pradesh|Assam|Bihar|Chhattisgarh|Goa|Gujarat|Haryana|"
    r"Himachal Pradesh|Jharkhand|Karnataka|Kerala|Madhya Pradesh|Maharashtra|Manipur|"
    r"Meghalaya|Mizoram|Nagaland|Odisha|Punjab|Rajasthan|Sikkim|Tamil Nadu|Telangana|"
    r"Tripura|Uttar Pradesh|Uttarakhand|West Bengal|Delhi|Jammu & Kashmir|Ladakh|"
    r"Puducherry|Chandigarh)\b", re.I,
)


class MockLLMProvider(BaseLLMProvider):
    async def classify(self, english_text: str) -> StructuredGrievance:
        category, department = "General", "General Administration"
        for pattern, cat, dept in _RULES:
            if pattern.search(english_text):
                category, department = cat, dept
                break

        if _PRIO_CRITICAL.search(english_text):
            priority = "CRITICAL"
        elif _PRIO_HIGH.search(english_text):
            priority = "HIGH"
        elif any(w in english_text.lower() for w in ["days", "week", "month", "long time"]):
            priority = "MEDIUM"
        else:
            priority = "LOW"

        state_m = _STATES.search(english_text)
        location_state = state_m.group(1).title() if state_m else None

        desc = english_text.strip()
        if len(desc) > 500:
            desc = desc[:497] + "..."

        missing: list[str] = []
        if not location_state:
            missing.append("location_state")
        if "district" not in english_text.lower():
            missing.append("location_district")

        logger.info("[MOCK LLM] category=%s priority=%s state=%s", category, priority, location_state)

        return StructuredGrievance(
            description=desc, category=category, department=department,
            location_state=location_state, location_district=None, location_city=None,
            location_raw=None, priority=priority, missing_information=missing,
            confidence_score=0.72, is_mock=True,
        )


# ── Service orchestrator ──────────────────────────────────────
class LLMService:
    """
    Classifies English grievance text into structured output.
    Tries providers in order; falls back to next on error.
    """

    def __init__(self) -> None:
        self.use_mock = settings.LLM_USE_MOCK
        self._providers: list[BaseLLMProvider] = []

        if not self.use_mock:
            ollama = OllamaLLMProvider()
            if ollama.available():
                self._providers.append(ollama)
                logger.info("LLM: Ollama provider enabled (model=%s)", settings.OLLAMA_MODEL)

            gemini = GeminiLLMProvider()
            if gemini.available():
                self._providers.append(gemini)
                logger.info("LLM: Gemini provider enabled (model=%s)", settings.GEMINI_MODEL)

            openai_p = OpenAILLMProvider()
            if openai_p.available():
                self._providers.append(openai_p)
                logger.info("LLM: OpenAI provider enabled (model=%s)", settings.OPENAI_MODEL)

        self._providers.append(MockLLMProvider())

        if len(self._providers) == 1:
            logger.warning(
                "LLM: No real providers configured — using mock only. "
                "Set LLM_USE_MOCK=false and configure OLLAMA_ENABLED=true or an API key."
            )

    async def classify(self, english_text: str) -> StructuredGrievance:
        """
        Extract structured grievance fields from English text.

        Args:
            english_text: English translation of the citizen's spoken grievance.

        Returns:
            StructuredGrievance with category, department, location, priority, etc.
        """
        last_error: Optional[Exception] = None
        for provider in self._providers:
            try:
                result = await provider.classify(english_text)
                logger.info(
                    "LLM success via %s: category=%s priority=%s confidence=%.2f is_mock=%s",
                    type(provider).__name__, result.category, result.priority,
                    result.confidence_score, result.is_mock,
                )
                return result
            except Exception as exc:
                logger.warning("LLM provider %s failed: %s", type(provider).__name__, exc)
                last_error = exc
                continue

        raise RuntimeError(f"All LLM providers failed. Last error: {last_error}")


llm_service = LLMService()

