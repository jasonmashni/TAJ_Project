"""Provider interfaces + a factory with graceful local→mock fallback.

The rest of TAJ depends only on these three abstract interfaces. Today they
resolve to local models (faster-whisper, Ollama, Coqui); swapping in a cloud API
or a GPU-hosted backend for web scale is a new subclass + a config value, nothing
more.
"""

from __future__ import annotations

import abc
import logging

from backend.config import settings

log = logging.getLogger("taj.providers")


class STTProvider(abc.ABC):
    """Speech-to-text."""

    name: str = "base"

    @abc.abstractmethod
    async def transcribe(self, audio_path: str, language: str) -> str:
        """Return the recognized text for the audio file at ``audio_path``."""


class LLMProvider(abc.ABC):
    """The tutor brain."""

    name: str = "base"

    @abc.abstractmethod
    async def complete(self, system: str, messages: list[dict]) -> str:
        """Return the model's text completion given a system prompt + chat history.

        ``messages`` is a list of ``{"role": "user"|"assistant", "content": str}``.
        """


class TTSProvider(abc.ABC):
    """Text-to-speech. Always returns WAV bytes so the browser can play it."""

    name: str = "base"

    @abc.abstractmethod
    async def synthesize(self, text: str, language: str) -> bytes:
        """Return WAV (PCM) bytes speaking ``text`` in ``language``."""


# --------------------------------------------------------------------------- #
# Factory
# --------------------------------------------------------------------------- #
def _resolve(kind: str, choice: str):
    """Construct a provider, honoring ``choice`` ("auto" | "mock" | explicit name).

    "auto" tries the real local provider and falls back to the mock (with a log
    line) if its dependencies or backing service are unavailable — so a fresh
    checkout always runs.
    """
    from backend.providers import mock

    mocks = {
        "stt": mock.MockSTT,
        "llm": mock.MockLLM,
        "tts": mock.MockTTS,
    }

    if choice == "mock":
        return mocks[kind]()

    try:
        if kind == "stt" and choice in ("auto", "whisper"):
            from backend.providers.stt_whisper import WhisperSTT

            return WhisperSTT()
        if kind == "llm" and choice == "claude":
            from backend.providers.llm_claude import ClaudeLLM

            return ClaudeLLM()
        if kind == "llm" and choice == "auto":
            # Smart default: use cloud Claude if a key is present, else try
            # local Ollama, else fall through to mock.
            import os

            if settings.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY"):
                from backend.providers.llm_claude import ClaudeLLM

                return ClaudeLLM()
            from backend.providers.llm_ollama import OllamaLLM

            return OllamaLLM()
        if kind == "llm" and choice == "ollama":
            from backend.providers.llm_ollama import OllamaLLM

            return OllamaLLM()
        if kind == "tts" and choice in ("auto", "coqui"):
            from backend.providers.tts_coqui import CoquiTTS

            return CoquiTTS()
    except Exception as exc:  # noqa: BLE001 - any failure → safe fallback
        if choice != "auto":
            # The user explicitly asked for a real provider; surface the reason.
            log.error("Provider %s/%s failed to load: %s", kind, choice, exc)
            raise
        log.warning(
            "Provider %s/%s unavailable (%s); falling back to mock. "
            "Install the model/deps to enable it.",
            kind,
            choice,
            exc,
        )

    return mocks[kind]()


def get_stt() -> STTProvider:
    return _resolve("stt", settings.stt_provider)


def get_llm() -> LLMProvider:
    return _resolve("llm", settings.llm_provider)


def get_tts() -> TTSProvider:
    return _resolve("tts", settings.tts_provider)
