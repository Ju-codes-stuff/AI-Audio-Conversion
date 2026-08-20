"""
Registry of all 22 scheduled Indian languages with BCP-47 codes,
native names, and IndicConformer / IndicTrans2 model identifiers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class Language:
    code: str          # BCP-47 / ISO 639-1 or 639-3
    name_en: str       # English name
    name_native: str   # Native script name
    script: str        # Unicode script name
    asr_code: str      # Code used by IndicASR / IndicConformer
    nmt_code: str      # Code used by IndicTrans2


# All 22 constitutionally scheduled Indian languages
LANGUAGES: List[Language] = [
    Language("as",    "Assamese",   "অসমীয়া",    "Bengali",     "as",    "asm_Beng"),
    Language("bn",    "Bengali",    "বাংলা",       "Bengali",     "bn",    "ben_Beng"),
    Language("brx",   "Bodo",       "बड़ो",        "Devanagari",  "brx",   "brx_Deva"),
    Language("doi",   "Dogri",      "डोगरी",       "Devanagari",  "doi",   "doi_Deva"),
    Language("gu",    "Gujarati",   "ગુજરાતી",     "Gujarati",    "gu",    "guj_Gujr"),
    Language("hi",    "Hindi",      "हिन्दी",       "Devanagari",  "hi",    "hin_Deva"),
    Language("kn",    "Kannada",    "ಕನ್ನಡ",       "Kannada",     "kn",    "kan_Knda"),
    Language("ks",    "Kashmiri",   "کٲشُر",       "Arabic",      "ks",    "kas_Arab"),
    Language("kok",   "Konkani",    "कोंकणी",      "Devanagari",  "kok",   "kok_Deva"),
    Language("mai",   "Maithili",   "मैथिली",      "Devanagari",  "mai",   "mai_Deva"),
    Language("ml",    "Malayalam",  "മലയാളം",      "Malayalam",   "ml",    "mal_Mlym"),
    Language("mni",   "Manipuri",   "ꯃꯤꯇꯩꯂꯣꯟ",  "Meitei Mayek","mni",  "mni_Mtei"),
    Language("mr",    "Marathi",    "मराठी",       "Devanagari",  "mr",    "mar_Deva"),
    Language("ne",    "Nepali",     "नेपाली",      "Devanagari",  "ne",    "npi_Deva"),
    Language("or",    "Odia",       "ଓଡ଼ିଆ",       "Oriya",       "or",    "ory_Orya"),
    Language("pa",    "Punjabi",    "ਪੰਜਾਬੀ",      "Gurmukhi",    "pa",    "pan_Guru"),
    Language("sa",    "Sanskrit",   "संस्कृतम्",   "Devanagari",  "sa",    "san_Deva"),
    Language("sat",   "Santali",    "ᱥᱟᱱᱛᱟᱲᱤ",  "Ol Chiki",    "sat",   "sat_Olck"),
    Language("sd",    "Sindhi",     "سنڌي",        "Arabic",      "sd",    "snd_Arab"),
    Language("ta",    "Tamil",      "தமிழ்",       "Tamil",       "ta",    "tam_Taml"),
    Language("te",    "Telugu",     "తెలుగు",      "Telugu",      "te",    "tel_Telu"),
    Language("ur",    "Urdu",       "اُردُو",       "Arabic",      "ur",    "urd_Arab"),
]

LANGUAGE_MAP: Dict[str, Language] = {lang.code: lang for lang in LANGUAGES}
LANGUAGE_NMT_MAP: Dict[str, Language] = {lang.nmt_code: lang for lang in LANGUAGES}
SUPPORTED_LANGUAGE_CODES: List[str] = [lang.code for lang in LANGUAGES]


def get_language(code: str) -> Language | None:
    """Look up a language by BCP-47 code (case-insensitive)."""
    return LANGUAGE_MAP.get(code.lower())


def get_language_by_nmt_code(nmt_code: str) -> Language | None:
    """Look up a language by IndicTrans2 NMT code."""
    return LANGUAGE_NMT_MAP.get(nmt_code)


def is_supported(code: str) -> bool:
    return code.lower() in LANGUAGE_MAP
