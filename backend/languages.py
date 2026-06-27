"""Language + dialect registry.

Each profile bundles everything the rest of the app needs to behave correctly
for one target language *and dialect*: the ISO codes the models expect, display
metadata, the opening line TAJ speaks, and a persona block injected into the
tutor's system prompt.

Adding a language is just adding an entry here — the voice loop, SRS, and UI are
all profile-driven.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LanguageProfile:
    key: str            # registry key, e.g. "ar-LEV"
    name: str           # English display name, e.g. "Arabic (Levantine)"
    native_name: str    # endonym, e.g. "العربية الشامية"
    dialect: str        # human label of the dialect
    whisper_lang: str   # ISO-639-1 code Whisper expects (e.g. "ar")
    tts_lang: str       # language code XTTS expects (e.g. "ar")
    greeting: str       # first line TAJ speaks when a session opens
    greeting_en: str    # English translation of the greeting (shown to beginners)
    persona: str        # injected into the tutor system prompt
    rtl: bool = False   # right-to-left script (affects UI direction)


_LEVANTINE_PERSONA = """\
You are speaking COLLOQUIAL LEVANTINE ARABIC (اللهجة الشامية), the everyday spoken
dialect of Syria/Lebanon/Jordan/Palestine — NOT Modern Standard Arabic (الفصحى).
Use natural Levantine words and grammar (e.g. say "شو" not "ماذا", "هلق" not
"الآن", "بدي" not "أريد", "كيفك" not "كيف حالك"). Keep it warm and conversational,
the way a friendly local would actually talk."""

_MSA_PERSONA = """\
You are speaking MODERN STANDARD ARABIC (الفصحى). Use clear, correct standard
forms suitable for formal speech, news, and writing."""

_MANDARIN_PERSONA = """\
You are speaking STANDARD MANDARIN CHINESE (普通话). Use natural everyday Mainland
usage. When you surface vocab, always include pinyin with tone marks."""

_JAPANESE_PERSONA = """\
You are speaking STANDARD JAPANESE (標準語). Default to polite (です/ます) register
for a learner. When you surface vocab, always include the reading in hiragana
(furigana-style) plus romaji."""


REGISTRY: dict[str, LanguageProfile] = {
    "ar-LEV": LanguageProfile(
        key="ar-LEV",
        name="Arabic (Levantine)",
        native_name="العربية الشامية",
        dialect="Levantine (Shami)",
        whisper_lang="ar",
        tts_lang="ar",
        greeting="مرحبا! أنا تاج. رح ساعدك تتعلم عربي. شو اسمك؟",
        greeting_en="Hi! I'm TAJ. I'll help you learn Arabic. What's your name?",
        persona=_LEVANTINE_PERSONA,
        rtl=True,
    ),
    "ar-MSA": LanguageProfile(
        key="ar-MSA",
        name="Arabic (Modern Standard)",
        native_name="العربية الفصحى",
        dialect="Modern Standard Arabic",
        whisper_lang="ar",
        tts_lang="ar",
        greeting="مرحباً! أنا تاج. سأساعدك على تعلّم العربية. ما اسمك؟",
        greeting_en="Hello! I'm TAJ. I'll help you learn Arabic. What's your name?",
        persona=_MSA_PERSONA,
        rtl=True,
    ),
    # --- Fast-follow languages (profiles ready; flip TAJ_LANGUAGE to use) ---
    "zh-CN": LanguageProfile(
        key="zh-CN",
        name="Mandarin Chinese",
        native_name="普通话",
        dialect="Standard Mainland Mandarin",
        whisper_lang="zh",
        tts_lang="zh-cn",
        greeting="你好！我是 TAJ。我会帮你学中文。你叫什么名字？",
        greeting_en="Hello! I'm TAJ. I'll help you learn Chinese. What's your name?",
        persona=_MANDARIN_PERSONA,
        rtl=False,
    ),
    "ja-JP": LanguageProfile(
        key="ja-JP",
        name="Japanese",
        native_name="日本語",
        dialect="Standard Japanese",
        whisper_lang="ja",
        tts_lang="ja",
        greeting="こんにちは！TAJ です。日本語の練習を手伝います。お名前は？",
        greeting_en="Hello! I'm TAJ. I'll help you practice Japanese. What's your name?",
        persona=_JAPANESE_PERSONA,
        rtl=False,
    ),
}

DEFAULT_KEY = "ar-LEV"

# The learner's own language — used so the tutor translates/explains in a
# language they already understand. Codes are arbitrary internal keys.
NATIVE_LANGUAGES: dict[str, str] = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "hi": "Hindi",
    "ur": "Urdu",
}

# CEFR-ish levels offered in onboarding, with plain-English labels.
LEVELS: dict[str, str] = {
    "A1": "Beginner — just starting out",
    "A2": "Elementary — some basics",
    "B1": "Intermediate — can hold simple conversations",
    "B2": "Upper-intermediate — fairly comfortable",
    "C1": "Advanced — fluent-ish, polishing",
}


def get_profile(key: str | None = None) -> LanguageProfile:
    """Return the profile for ``key`` (or the default), never raising on a bad key."""
    return REGISTRY.get(key or DEFAULT_KEY, REGISTRY[DEFAULT_KEY])


def native_name(code: str | None) -> str:
    """English display name for a native-language code (defaults to English)."""
    return NATIVE_LANGUAGES.get(code or "en", "English")
