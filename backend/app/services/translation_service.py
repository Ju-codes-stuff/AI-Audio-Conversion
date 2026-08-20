"""
Translation Service — IndicTrans2 wrapper with mock fallback.

Real mode: POST native text to a running IndicTrans2 microservice.
Mock mode: Return an English placeholder for dev/testing.

Set TRANSLATION_USE_MOCK=true in .env (default for Phase 1 PoC).
"""
from __future__ import annotations

import logging
import time

import httpx

from app.config import settings
from app.core.languages import get_language

logger = logging.getLogger(__name__)

ENGLISH_NMT_CODE = "eng_Latn"

# Mock English translations matching the mock ASR transcripts
MOCK_TRANSLATIONS: dict[str, str] = {
    "hi": (
        "There has been no water supply in my area for the past three days. "
        "The tap is completely shut and the heat is extreme."
    ),
    "ta": (
        "There has been no water supply in my area for three days. "
        "The tap is completely closed."
    ),
    "te": (
        "There has been no water supply in our area for three days. "
        "The tap is completely closed."
    ),
    "kn": (
        "There has been no water supply in our area for three days. "
        "The tap is completely shut."
    ),
    "ml": (
        "There has been no water supply in my area for three days. "
        "The tap is completely closed."
    ),
    "bn": (
        "There has been no water supply in my area for three days. "
        "The tap is completely off."
    ),
    "mr": (
        "There has been no water supply in my area for three days. "
        "The tap is completely closed."
    ),
    "gu": (
        "There has been no water supply in my area for three days. "
        "The tap is completely shut."
    ),
    "pa": (
        "There has been no water supply in my area for three days. "
        "The tap is completely closed."
    ),
    "or": (
        "There has been no water supply in my area for three days. "
        "The tap is completely shut."
    ),
    "as": (
        "There has been no water supply in my area for three days. "
        "The tap is completely shut."
    ),
    "ur": (
        "There has been no water supply in my area for three days. "
        "The tap is completely shut."
    ),
}
DEFAULT_MOCK_ENGLISH = (
    "The citizen is reporting a public service issue in their area requiring government attention."
)


class TranslationResult:
    def __init__(
        self,
        source_text: str,
        translated_text: str,
        source_language: str,   # IndicTrans2 NMT code
        target_language: str,
        model_version: str,
        processing_time_ms: int,
        is_mock: bool,
    ) -> None:
        self.source_text = source_text
        self.translated_text = translated_text
        self.source_language = source_language
        self.target_language = target_language
        self.model_version = model_version
        self.processing_time_ms = processing_time_ms
        self.is_mock = is_mock


class TranslationService:
    def __init__(self) -> None:
        self.use_mock = settings.TRANSLATION_USE_MOCK
        self.service_url = settings.TRANSLATION_SERVICE_URL.rstrip("/")
        self.timeout = settings.TRANSLATION_SERVICE_TIMEOUT

    async def translate_to_english(
        self, text: str, source_language_code: str
    ) -> TranslationResult:
        """
        Translate native-language text to English.

        Args:
            text:                   Native language transcript.
            source_language_code:   BCP-47 language code (e.g. 'hi').

        Returns:
            TranslationResult with English text and metadata.
        """
        lang = get_language(source_language_code)
        if lang is None:
            raise ValueError(f"Unsupported language code: {source_language_code}")

        # Skip translation for English input
        if source_language_code == "en":
            return TranslationResult(
                source_text=text,
                translated_text=text,
                source_language="eng_Latn",
                target_language=ENGLISH_NMT_CODE,
                model_version="passthrough",
                processing_time_ms=0,
                is_mock=False,
            )

        if self.use_mock:
            return self._mock_translate(text, source_language_code, lang.nmt_code)

        return await self._real_translate(text, lang.nmt_code)

    def _mock_translate(
        self, source_text: str, language_code: str, nmt_code: str
    ) -> TranslationResult:
        english = MOCK_TRANSLATIONS.get(language_code, DEFAULT_MOCK_ENGLISH)
        logger.info("[MOCK TRANSLATE] %s → English, length=%d", language_code, len(english))
        return TranslationResult(
            source_text=source_text,
            translated_text=english,
            source_language=nmt_code,
            target_language=ENGLISH_NMT_CODE,
            model_version="mock-v1.0",
            processing_time_ms=100,
            is_mock=True,
        )

    async def _real_translate(self, text: str, nmt_source_code: str) -> TranslationResult:
        """Call the IndicTrans2 microservice."""
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.service_url}/translate",
                    json={
                        "text": text,
                        "src_lang": nmt_source_code,
                        "tgt_lang": ENGLISH_NMT_CODE,
                    },
                )
                response.raise_for_status()
                data = response.json()
        except httpx.HTTPError as exc:
            logger.error("Translation service error: %s", exc)
            raise RuntimeError(f"Translation service unavailable: {exc}") from exc

        elapsed_ms = int((time.monotonic() - start) * 1000)
        return TranslationResult(
            source_text=text,
            translated_text=data["translation"],
            source_language=nmt_source_code,
            target_language=ENGLISH_NMT_CODE,
            model_version=data.get("model_version", "indictrans2-1B"),
            processing_time_ms=elapsed_ms,
            is_mock=False,
        )


translation_service = TranslationService()
