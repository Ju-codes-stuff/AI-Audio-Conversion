"""
Translation Service — Provider chain: Bhashini → HuggingFace NLLB → Mock fallback.

Provider priority:
  1. Bhashini API   — IndicTrans2-powered, best quality for Indian languages
  2. HuggingFace    — facebook/nllb-200-distilled-600M (supports all 22 languages)
  3. Mock           — instant placeholder, used for dev/testing

Set TRANSLATION_USE_MOCK=false in .env to enable real providers.
"""
from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from typing import Optional

import httpx

from app.config import settings
from app.core.languages import get_language

logger = logging.getLogger(__name__)

ENGLISH_NMT_CODE = "eng_Latn"

# ── Mock English translations ─────────────────────────────────
MOCK_TRANSLATIONS: dict[str, str] = {
    "hi": ("There has been no water supply in my area for the past three days. "
           "The tap is completely shut and the heat is extreme."),
    "ta": "There has been no water supply in my area for three days. The tap is completely closed.",
    "te": "There has been no water supply in our area for three days. The tap is completely closed.",
    "kn": "There has been no water supply in our area for three days. The tap is completely shut.",
    "ml": "There has been no water supply in my area for three days. The tap is completely closed.",
    "bn": "There has been no water supply in my area for three days. The tap is completely off.",
    "mr": "There has been no water supply in my area for three days. The tap is completely closed.",
    "gu": "There has been no water supply in my area for three days. The tap is completely shut.",
    "pa": "There has been no water supply in my area for three days. The tap is completely closed.",
    "or": "There has been no water supply in my area for three days. The tap is completely shut.",
    "as": "There has been no water supply in my area for three days. The tap is completely shut.",
    "ur": "There has been no water supply in my area for three days. The tap is completely shut.",
    "ne": "There has been no water supply in my area for three days. The tap is completely closed.",
    "sa": "There has been no water supply in my area for three days. The tap is completely closed.",
}
DEFAULT_MOCK_ENGLISH = (
    "The citizen is reporting a public service issue in their area requiring government attention."
)

# ── NLLB-200 language code mapping ───────────────────────────
# Facebook's NLLB uses flores_200 codes
NLLB_LANG_MAP: dict[str, str] = {
    "hi":  "hin_Deva",
    "ta":  "tam_Taml",
    "te":  "tel_Telu",
    "kn":  "kan_Knda",
    "ml":  "mal_Mlym",
    "bn":  "ben_Beng",
    "gu":  "guj_Gujr",
    "mr":  "mar_Deva",
    "pa":  "pan_Guru",
    "or":  "ory_Orya",
    "as":  "asm_Beng",
    "ur":  "urd_Arab",
    "ne":  "npi_Deva",
    "sa":  "san_Deva",
    "sd":  "snd_Arab",
    "ks":  "kas_Arab",
    "mai": "mai_Deva",
    "kok": "kok_Deva",
    "doi": "dgo_Deva",
    "brx": "brx_Deva",
    "sat": "sat_Olck",
    "mni": "mni_Mtei",
}


class TranslationResult:
    __slots__ = ("source_text", "translated_text", "source_language",
                 "target_language", "model_version", "processing_time_ms", "is_mock")

    def __init__(self, source_text: str, translated_text: str, source_language: str,
                 target_language: str, model_version: str,
                 processing_time_ms: int, is_mock: bool) -> None:
        self.source_text = source_text
        self.translated_text = translated_text
        self.source_language = source_language
        self.target_language = target_language
        self.model_version = model_version
        self.processing_time_ms = processing_time_ms
        self.is_mock = is_mock


# ── Abstract provider ─────────────────────────────────────────
class BaseTranslationProvider(ABC):
    @abstractmethod
    async def translate(self, text: str, source_language_code: str) -> TranslationResult:
        ...


# ── Provider 1: Bhashini ──────────────────────────────────────
class BhashiniTranslationProvider(BaseTranslationProvider):
    """
    Uses Bhashini's NMT pipeline (IndicTrans2 under the hood).
    Requires: BHASHINI_USER_ID, BHASHINI_ULCA_API_KEY, BHASHINI_INFERENCE_API_KEY
    """

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

    async def translate(self, text: str, source_language_code: str) -> TranslationResult:
        start = time.monotonic()
        payload = {
            "pipelineTasks": [{
                "taskType": "translation",
                "config": {
                    "language": {
                        "sourceLanguage": source_language_code,
                        "targetLanguage": "en",
                    }
                },
            }],
            "inputData": {"input": [{"source": text}]},
        }
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(self.INFERENCE_URL, json=payload, headers=self._headers())
            r.raise_for_status()
            data = r.json()

        translated = (
            data.get("pipelineResponse", [{}])[0]
            .get("output", [{}])[0]
            .get("target", "")
        )
        elapsed = int((time.monotonic() - start) * 1000)
        return TranslationResult(
            source_text=text, translated_text=translated,
            source_language=source_language_code, target_language=ENGLISH_NMT_CODE,
            model_version="bhashini-indictrans2", processing_time_ms=elapsed, is_mock=False,
        )


# ── Provider 2: HuggingFace NLLB-200 ─────────────────────────
class HuggingFaceTranslationProvider(BaseTranslationProvider):
    """
    Uses facebook/nllb-200-distilled-600M via HuggingFace Inference API.
    Supports all 22 Indian languages. Free without token (rate-limited).
    """

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if settings.HUGGINGFACE_API_KEY:
            h["Authorization"] = f"Bearer {settings.HUGGINGFACE_API_KEY}"
        return h

    def _url(self) -> str:
        return f"https://router.huggingface.co/hf-inference/models/{settings.HUGGINGFACE_MT_MODEL}"

    async def translate(self, text: str, source_language_code: str) -> TranslationResult:
        start = time.monotonic()
        nllb_src = NLLB_LANG_MAP.get(source_language_code, f"{source_language_code}_Deva")
        nllb_tgt = "eng_Latn"

        payload = {
            "inputs": text,
            "parameters": {
                "src_lang": nllb_src,
                "tgt_lang": nllb_tgt,
            },
        }
        async with httpx.AsyncClient(timeout=settings.HUGGINGFACE_TIMEOUT) as client:
            r = await client.post(self._url(), json=payload, headers=self._headers())
            r.raise_for_status()
            data = r.json()

        # NLLB returns a list of dicts with "translation_text"
        if isinstance(data, list) and data:
            translated = data[0].get("translation_text", "")
        elif isinstance(data, dict):
            translated = data.get("translation_text", data.get("generated_text", ""))
        else:
            translated = str(data)

        if not translated:
            raise ValueError("HuggingFace translation returned empty result")

        elapsed = int((time.monotonic() - start) * 1000)
        return TranslationResult(
            source_text=text, translated_text=translated,
            source_language=nllb_src, target_language=nllb_tgt,
            model_version=f"hf/{settings.HUGGINGFACE_MT_MODEL}",
            processing_time_ms=elapsed, is_mock=False,
        )


# ── Provider 3: Ollama ──────────────────────────────────────────
class OllamaTranslationProvider(BaseTranslationProvider):
    async def translate(self, text: str, source_language_code: str) -> TranslationResult:
        start = time.monotonic()
        prompt = f"Translate the following text to English. Output strictly ONLY the English translation with no other text, comments, or quotes. Text to translate:\n\n{text}"
        payload = {
            "model": "gemma3:4b",
            "prompt": prompt,
            "stream": False
        }
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post("http://localhost:11434/api/generate", json=payload)
            r.raise_for_status()
            data = r.json()
        
        translated = data.get("response", "").strip()
        elapsed = int((time.monotonic() - start) * 1000)
        return TranslationResult(
            source_text=text, translated_text=translated,
            source_language=source_language_code, target_language="en",
            model_version="gemma3:4b", processing_time_ms=elapsed, is_mock=False
        )

# ── Provider 4: Mock ────────────────────────────────────────────
class MockTranslationProvider(BaseTranslationProvider):
    async def translate(self, text: str, source_language_code: str) -> TranslationResult:
        english = MOCK_TRANSLATIONS.get(source_language_code, DEFAULT_MOCK_ENGLISH)
        logger.info("[MOCK TRANSLATE] %s → English length=%d", source_language_code, len(english))
        return TranslationResult(
            source_text=text, translated_text=english,
            source_language=NLLB_LANG_MAP.get(source_language_code, source_language_code),
            target_language=ENGLISH_NMT_CODE,
            model_version="mock-v1.0", processing_time_ms=100, is_mock=True,
        )


# ── Service orchestrator ──────────────────────────────────────────
class TranslationService:
    """
    Tries providers in order; falls back to next on error.
    """

    def __init__(self) -> None:
        self.use_mock = settings.TRANSLATION_USE_MOCK
        self._providers: list[BaseTranslationProvider] = []

        if not self.use_mock:
            bhashini = BhashiniTranslationProvider()
            if bhashini.available():
                self._providers.append(bhashini)
                logger.info("Translation: Bhashini provider enabled")

            self._providers.append(HuggingFaceTranslationProvider())
            logger.info("Translation: HuggingFace NLLB-200 provider enabled")

            self._providers.append(OllamaTranslationProvider())
            logger.info("Translation: Ollama (gemma3:4b) provider enabled")

        self._providers.append(MockTranslationProvider())

    async def translate_to_english(
        self, text: str, source_language_code: str
    ) -> TranslationResult:
        """
        Translate native-language text to English.

        Args:
            text:                 Native language transcript.
            source_language_code: BCP-47 language code (e.g. 'hi').

        Returns:
            TranslationResult with English text and metadata.
        """
        lang = get_language(source_language_code)
        if lang is None:
            raise ValueError(f"Unsupported language code: {source_language_code}")

        # English is a passthrough
        if source_language_code == "en":
            return TranslationResult(
                source_text=text, translated_text=text,
                source_language="eng_Latn", target_language=ENGLISH_NMT_CODE,
                model_version="passthrough", processing_time_ms=0, is_mock=False,
            )

        last_error: Optional[Exception] = None
        for provider in self._providers:
            try:
                result = await provider.translate(text, source_language_code)
                logger.info(
                    "Translation success via %s: %s → en is_mock=%s",
                    type(provider).__name__, source_language_code, result.is_mock,
                )
                return result
            except Exception as exc:
                logger.warning("Translation provider %s failed: %s", type(provider).__name__, exc)
                last_error = exc
                continue

        raise RuntimeError(f"All translation providers failed. Last error: {last_error}")


translation_service = TranslationService()
