"""
ASR Service — IndicConformer / IndicASR wrapper with mock fallback.

Real mode: POST normalized WAV to a running IndicConformer microservice.
Mock mode: Return a human-readable placeholder transcript for dev/testing.

Set ASR_USE_MOCK=true in .env to use mock mode (default for Phase 1 PoC).
"""
from __future__ import annotations

import logging
import time
from typing import Optional

import httpx

from app.config import settings
from app.core.languages import get_language

logger = logging.getLogger(__name__)

# Mock transcripts per language for quick local testing
MOCK_TRANSCRIPTS: dict[str, str] = {
    "hi": "मेरे इलाके में पिछले तीन दिनों से पानी नहीं आ रहा है। नल बिल्कुल बंद है और गर्मी बहुत ज्यादा है।",
    "ta": "என் பகுதியில் மூன்று நாட்களாக தண்ணீர் வருவதில்லை. குழாய் முழுமையாக மூடப்பட்டுள்ளது.",
    "te": "మా ప్రాంతంలో మూడు రోజులుగా నీరు రావడం లేదు. నల్లా పూర్తిగా మూసివేయబడింది.",
    "kn": "ನಮ್ಮ ಪ್ರದೇಶದಲ್ಲಿ ಮೂರು ದಿನಗಳಿಂದ ನೀರು ಬರುತ್ತಿಲ್ಲ. ನಲ್ಲಿ ಸಂಪೂರ್ಣವಾಗಿ ಮುಚ್ಚಲ್ಪಟ್ಟಿದೆ.",
    "ml": "എന്റെ പ്രദേശത്ത് മൂന്ന് ദിവസമായി വെള്ളം വരുന്നില്ല. ടാപ്പ് പൂർണ്ണമായും അടഞ്ഞുകിടക്കുകയാണ്.",
    "bn": "আমার এলাকায় তিন দিন ধরে পানি আসছে না। কলটি সম্পূর্ণ বন্ধ।",
    "mr": "माझ्या परिसरात तीन दिवसांपासून पाणी येत नाही. नळ पूर्णपणे बंद आहे.",
    "gu": "મારા વિસ્તારમાં ત્રણ દિવસથી પાણી આવતું નથી. નળ સંપૂર્ણ બંધ છે.",
    "pa": "ਮੇਰੇ ਇਲਾਕੇ ਵਿੱਚ ਤਿੰਨ ਦਿਨਾਂ ਤੋਂ ਪਾਣੀ ਨਹੀਂ ਆ ਰਿਹਾ। ਨਲਕਾ ਪੂਰੀ ਤਰ੍ਹਾਂ ਬੰਦ ਹੈ।",
    "or": "ମୋ ଅଞ୍ଚଳରେ ତିନି ଦିନ ଧରି ପାଣି ଆସୁ ନାହିଁ। ନଳ ସଂପୂର୍ଣ ବନ୍ଦ।",
    "as": "মোৰ অঞ্চলত তিনি দিনৰ পৰা পানী অহা নাই। টেপ সম্পূৰ্ণৰূপে বন্ধ।",
    "ur": "میرے علاقے میں تین دنوں سے پانی نہیں آ رہا۔ نل بالکل بند ہے۔",
}
DEFAULT_MOCK = "The citizen is reporting a public service issue in their area. Details need clarification."


class ASRResult:
    def __init__(
        self,
        text: str,
        language_code: str,
        confidence: float,
        model_version: str,
        processing_time_ms: int,
        is_mock: bool,
    ) -> None:
        self.text = text
        self.language_code = language_code
        self.confidence = confidence
        self.model_version = model_version
        self.processing_time_ms = processing_time_ms
        self.is_mock = is_mock


class ASRService:
    def __init__(self) -> None:
        self.use_mock = settings.ASR_USE_MOCK
        self.service_url = settings.ASR_SERVICE_URL.rstrip("/")
        self.timeout = settings.ASR_SERVICE_TIMEOUT

    async def transcribe(self, audio_bytes: bytes, language_code: str) -> ASRResult:
        """
        Transcribe audio to native-language text.

        Args:
            audio_bytes:   Normalized 16kHz mono WAV bytes.
            language_code: BCP-47 language code (e.g. 'hi', 'ta').

        Returns:
            ASRResult with transcript and metadata.
        """
        lang = get_language(language_code)
        if lang is None:
            raise ValueError(f"Unsupported language code: {language_code}")

        if self.use_mock:
            return self._mock_transcribe(language_code)

        return await self._real_transcribe(audio_bytes, lang.asr_code)

    def _mock_transcribe(self, language_code: str) -> ASRResult:
        """Return a canned transcript for the given language."""
        text = MOCK_TRANSCRIPTS.get(language_code, DEFAULT_MOCK)
        logger.info("[MOCK ASR] language=%s text_length=%d", language_code, len(text))
        return ASRResult(
            text=text,
            language_code=language_code,
            confidence=0.95,
            model_version="mock-v1.0",
            processing_time_ms=250,
            is_mock=True,
        )

    async def _real_transcribe(self, audio_bytes: bytes, asr_code: str) -> ASRResult:
        """Call the IndicConformer microservice."""
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.service_url}/transcribe",
                    files={"audio": ("audio.wav", audio_bytes, "audio/wav")},
                    data={"language": asr_code},
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            logger.error("ASR service error: %s", exc)
            raise RuntimeError(f"ASR service unavailable: {exc}") from exc

        elapsed_ms = int((time.monotonic() - start) * 1000)
        return ASRResult(
            text=data["transcript"],
            language_code=asr_code,
            confidence=data.get("confidence", 0.0),
            model_version=data.get("model_version", "indic-conformer"),
            processing_time_ms=elapsed_ms,
            is_mock=False,
        )


asr_service = ASRService()
