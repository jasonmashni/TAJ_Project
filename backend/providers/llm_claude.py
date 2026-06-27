"""Tutor brain via the Claude API (cloud) — the easiest way to a genuinely smart
tutor, with no large local downloads and no Python-version constraints.

Enable:
    1. pip install anthropic
    2. put your key in .env:  ANTHROPIC_API_KEY=sk-ant-...
    3. set:                   TAJ_LLM_PROVIDER=claude

Defaults to claude-opus-4-8. For snappier, cheaper replies in a fast back-and-
forth voice chat, set TAJ_CLAUDE_MODEL=claude-haiku-4-5.
"""

from __future__ import annotations

import logging
import os

from backend.config import settings
from backend.providers.base import LLMProvider

log = logging.getLogger("taj.llm")


class ClaudeLLM(LLMProvider):
    name = "claude"

    def __init__(self) -> None:
        # Imported lazily so the app runs without the dep installed.
        from anthropic import AsyncAnthropic

        key = settings.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError(
                "No Anthropic API key found. Add ANTHROPIC_API_KEY=sk-ant-... to "
                "your .env file (see .env.example)."
            )
        self._client = AsyncAnthropic(api_key=key)
        self._model = settings.claude_model
        log.info("Claude tutor brain ready (model=%s)", self._model)

    async def complete(self, system: str, messages: list[dict]) -> str:
        # Short, conversational replies — no extended thinking, to keep the
        # voice turn-around fast. The tutor prompt already enforces brevity and
        # the structured output format.
        resp = await self._client.messages.create(
            model=self._model,
            max_tokens=800,
            system=system,
            messages=messages,
        )
        return "".join(
            block.text for block in resp.content if getattr(block, "type", None) == "text"
        ).strip()
