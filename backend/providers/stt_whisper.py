"""Speech-to-text via faster-whisper (local, CPU or GPU).

Install to enable:  pip install faster-whisper
Then set:           TAJ_STT_PROVIDER=whisper   (or leave on "auto")
"""

from __future__ import annotations

import asyncio
import logging

from backend.config import settings
from backend.providers.base import STTProvider

log = logging.getLogger("taj.stt")


class WhisperSTT(STTProvider):
    name = "whisper"

    def __init__(self) -> None:
        # Imported here (not at module top) so the app runs without the dep.
        from faster_whisper import WhisperModel

        log.info(
            "Loading faster-whisper model=%s device=%s compute=%s",
            settings.whisper_model,
            settings.whisper_device,
            settings.whisper_compute_type,
        )
        self._model = WhisperModel(
            settings.whisper_model,
            device=settings.whisper_device,
            compute_type=settings.whisper_compute_type,
        )

    async def transcribe(self, audio_path: str, language: str) -> str:
        # faster-whisper is sync/CPU-bound; run it off the event loop.
        return await asyncio.to_thread(self._transcribe_sync, audio_path, language)

    def _transcribe_sync(self, audio_path: str, language: str) -> str:
        segments, _info = self._model.transcribe(
            audio_path,
            language=language,
            vad_filter=True,  # drop silence/noise around the utterance
            beam_size=5,
        )
        return "".join(seg.text for seg in segments).strip()
