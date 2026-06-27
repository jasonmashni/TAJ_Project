"""Tutor brain via a local Ollama server (default model: Qwen2.5-Instruct).

Install to enable:
    1. Install Ollama: https://ollama.com
    2. Pull the model:  ollama pull qwen2.5:7b-instruct
    3. Set:             TAJ_LLM_PROVIDER=ollama   (or leave on "auto")

Qwen2.5 is chosen because one model handles Arabic *and* Mandarin *and* Japanese
well — matching TAJ's target-language roadmap without juggling per-language models.
"""

from __future__ import annotations

import logging

import httpx

from backend.config import settings
from backend.providers.base import LLMProvider

log = logging.getLogger("taj.llm")


class OllamaLLM(LLMProvider):
    name = "ollama"

    def __init__(self) -> None:
        # Fail fast (→ fallback to mock under "auto") if Ollama isn't reachable.
        try:
            httpx.get(f"{settings.ollama_url}/api/tags", timeout=2.0).raise_for_status()
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"Ollama not reachable at {settings.ollama_url}: {exc}"
            ) from exc
        self._url = settings.ollama_url
        self._model = settings.ollama_model

    async def complete(self, system: str, messages: list[dict]) -> str:
        payload = {
            "model": self._model,
            "stream": False,
            "messages": [{"role": "system", "content": system}, *messages],
            "options": {"temperature": 0.6},
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(f"{self._url}/api/chat", json=payload)
            resp.raise_for_status()
            data = resp.json()
        return (data.get("message") or {}).get("content", "").strip()
