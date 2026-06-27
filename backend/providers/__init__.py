"""Pluggable STT / LLM / TTS providers (local now, cloud-swappable later)."""

from backend.providers.base import get_llm, get_stt, get_tts

__all__ = ["get_stt", "get_llm", "get_tts"]
