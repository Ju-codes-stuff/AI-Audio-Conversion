"""
ASR Service — Provider chain: HuggingFace Whisper → Mock fallback.

Provider priority (first available wins):
  1. Bhashini API       — best quality for Indian languages (requires registration)
  2. HuggingFace        — openai/whisper-large-v3 (free, good quality)
  3. Mock               — instant, deterministic, used for dev/testing

Set ASR_USE_MOCK=false in .env to enable real providers.
HuggingFace token is optional but gives higher rate limits.
"""
from __future__ import annotations

import base64
import io
import logging
import time
from abc import ABC, abstractmethod
from typing import Optional

import httpx

from app.config import settings
from app.core.languages import get_language

logger = logging.getLogger(__name__)

# ── Mock transcripts (kept for dev/test) ─────────────────────
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
    "ne": "मेरो क्षेत्रमा तीन दिनदेखि पानी आएको छैन। धारा पूर्णतः बन्द छ।",
    "sa": "मम क्षेत्रे त्रिदिनेभ्यः जलं नागच्छति। नलः पूर्णतः बद्धः।",
}
DEFAULT_MOCK = "The citizen is reporting a public service issue in their area. Details need clarification."

# ── Whisper language code mapping ────────────────────────────
# Whisper uses shorter codes; most match BCP-47 directly
WHISPER_LANG_MAP: dict[str, str] = {
    "hi": "hi", "ta": "ta", "te": "te", "kn": "kn", "ml": "ml",
    "bn": "bn", "gu": "gu", "mr": "mr", "pa": "pa", "or": "or",
    "as": "as", "ur": "ur", "ne": "ne", "sa": "sa", "sd": "sd",
    "ks": "ks", "mai": "mai", "kok": "kok", "doi": "doi",
    # Less-resourced languages — Whisper may not support natively;
    # it will still attempt transcription but quality may vary
    "brx": "brx", "sat": "sat", "mni": "mni",
}


class ASRResult:
    __slots__ = ("text", "language_code", "confidence", "model_version",
                 "processing_time_ms", "is_mock")

    def __init__(self, text: str, language_code: str, confidence: float,
                 model_version: str, processing_time_ms: int, is_mock: bool) -> None:
        self.text = text
        self.language_code = language_code
        self.confidence = confidence
        self.model_version = model_version
        self.processing_time_ms = processing_time_ms
        self.is_mock = is_mock


# ── Abstract provider ─────────────────────────────────────────
class BaseASRProvider(ABC):
    @abstractmethod
    async def transcribe(self, audio_bytes: bytes, language_code: str) -> ASRResult:
        ...


# ── Provider 1: Bhashini ──────────────────────────────────────
class BhashiniASRProvider(BaseASRProvider):
    """
    Uses Bhashini's pipeline inference API (IndicConformer underneath).
    Requires: BHASHINI_USER_ID, BHASHINI_ULCA_API_KEY, BHASHINI_INFERENCE_API_KEY
    """

    PIPELINE_CONFIG_URL = "https://meity-auth.ulcacontrib.org/ulca/apis/v0/model/getModelsPipeline"
    INFERENCE_URL = "https://dhruva-api.bhashini.gov.in/services/inference/pipeline"

    def _headers(self) -> dict:
        return {
            "userID": settings.BHASHINI_USER_ID,
            "ulcaApiKey": settings.BHASHINI_ULCA_API_KEY,
            "Authorization": settings.BHASHINI_INFERENCE_API_KEY,
            "Content-Type": "application/json",
        }

    def available(self) -> bool:
        return bool(settings.BHASHINI_USER_ID and settings.BHASHINI_ULCA_API_KEY
                    and settings.BHASHINI_INFERENCE_API_KEY)

    async def transcribe(self, audio_bytes: bytes, language_code: str) -> ASRResult:
        start = time.monotonic()
        audio_b64 = base64.b64encode(audio_bytes).decode()
        payload = {
            "pipelineTasks": [{"taskType": "asr", "config": {"language": {"sourceLanguage": language_code}}}],
            "inputData": {"audio": [{"audioContent": audio_b64}]},
        }
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(self.INFERENCE_URL, json=payload, headers=self._headers())
            r.raise_for_status()
            data = r.json()

        transcript = (
            data.get("pipelineResponse", [{}])[0]
            .get("output", [{}])[0]
            .get("source", "")
        )
        elapsed = int((time.monotonic() - start) * 1000)
        return ASRResult(
            text=transcript, language_code=language_code,
            confidence=0.88, model_version="bhashini-indic-conformer",
            processing_time_ms=elapsed, is_mock=False,
        )


# ── Provider 2: HuggingFace Whisper ──────────────────────────
class HuggingFaceASRProvider(BaseASRProvider):
    """
    Uses openai/whisper-large-v3 via the HuggingFace Inference API.
    Free without token (rate-limited). Add HF token for higher limits.
    """

    def _headers(self) -> dict:
        h = {"Content-Type": "audio/wav"}
        if settings.HUGGINGFACE_API_KEY:
            h["Authorization"] = f"Bearer {settings.HUGGINGFACE_API_KEY}"
        return h

    def _url(self) -> str:
        return f"https://router.huggingface.co/hf-inference/models/{settings.HUGGINGFACE_ASR_MODEL}"

    async def transcribe(self, audio_bytes: bytes, language_code: str) -> ASRResult:
        start = time.monotonic()
        whisper_lang = WHISPER_LANG_MAP.get(language_code, language_code)

        # HF Inference API: send raw audio bytes, get transcript back
        async with httpx.AsyncClient(timeout=settings.HUGGINGFACE_TIMEOUT) as client:
            r = await client.post(
                self._url(),
                content=audio_bytes,
                headers={**self._headers(), "Content-Type": "audio/wav"}
            )
            r.raise_for_status()
            data = r.json()

        transcript = data.get("text", "").strip()
        if not transcript:
            raise ValueError("HuggingFace ASR returned empty transcript")

        elapsed = int((time.monotonic() - start) * 1000)
        return ASRResult(
            text=transcript, language_code=language_code,
            confidence=0.82, model_version=f"hf/{settings.HUGGINGFACE_ASR_MODEL}",
            processing_time_ms=elapsed, is_mock=False,
        )


# ── Provider 3: Mock ──────────────────────────────────────────
class MockASRProvider(BaseASRProvider):
    async def transcribe(self, audio_bytes: bytes, language_code: str) -> ASRResult:
        text = MOCK_TRANSCRIPTS.get(language_code, DEFAULT_MOCK)
        logger.info("[MOCK ASR] language=%s chars=%d", language_code, len(text))
        return ASRResult(
            text=text, language_code=language_code,
            confidence=0.95, model_version="mock-v1.0",
            processing_time_ms=250, is_mock=True,
        )


# ── Service orchestrator ──────────────────────────────────────
class ASRService:
    """
    Tries providers in order; falls back to next on any error.
    The mock is always the last resort so development never breaks.
    """

    def __init__(self) -> None:
        self.use_mock = settings.ASR_USE_MOCK
        self._providers: list[BaseASRProvider] = []

        if not self.use_mock:
            bhashini = BhashiniASRProvider()
            if bhashini.available():
                self._providers.append(bhashini)
                logger.info("ASR: Bhashini provider enabled")

            self._providers.append(HuggingFaceASRProvider())
            logger.info("ASR: HuggingFace Whisper provider enabled")

        self._providers.append(MockASRProvider())

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

        last_error: Optional[Exception] = None
        for provider in self._providers:
            try:
                result = await provider.transcribe(audio_bytes, language_code)
                logger.info(
                    "ASR success via %s: lang=%s chars=%d is_mock=%s",
                    type(provider).__name__, language_code, len(result.text), result.is_mock,
                )
                return result
            except Exception as exc:
                logger.warning("ASR provider %s failed: %s", type(provider).__name__, exc)
                last_error = exc
                continue

        # Should never reach here since Mock never fails
        raise RuntimeError(f"All ASR providers failed. Last error: {last_error}")


asr_service = ASRService()
