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
        greeting="مرحبا! أنا تاج، رح ساعدك تتعلم عربي. شو اسمك؟",
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
        greeting="مرحباً! أنا تاج، سأساعدك على تعلّم العربية. ما اسمك؟",
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
        greeting="你好！我是 TAJ，我会帮你学中文。你叫什么名字？",
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
        persona=_JAPANESE_PERSONA,
        rtl=False,
    ),
}

DEFAULT_KEY = "ar-LEV"


def get_profile(key: str | None = None) -> LanguageProfile:
    """Return the profile for ``key`` (or the default), never raising on a bad key."""
    return REGISTRY.get(key or DEFAULT_KEY, REGISTRY[DEFAULT_KEY])
