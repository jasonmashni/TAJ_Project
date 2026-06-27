"""Text-to-speech via Coqui XTTS-v2 (local, multilingual, voice-cloning capable).

Install to enable:  pip install TTS
Then set:           TAJ_TTS_PROVIDER=coqui   (or leave on "auto")

Optionally set TAJ_TTS_SPEAKER_WAV to a short (~6-10s) reference clip to clone a
specific voice for TAJ. XTTS supports Arabic, Mandarin, Japanese, and more.
"""

from __future__ import annotations

import asyncio
import io
import logging
import wave

from backend.config import settings
from backend.providers.base import TTSProvider

log = logging.getLogger("taj.tts")


class CoquiTTS(TTSProvider):
    name = "coqui"

    def __init__(self) -> None:
        from TTS.api import TTS  # imported lazily so the app runs without the dep

        log.info("Loading Coqui model=%s", settings.coqui_model)
        self._tts = TTS(settings.coqui_model)
        self._speaker_wav = settings.tts_speaker_wav

    async def synthesize(self, text: str, language: str) -> bytes:
        return await asyncio.to_thread(self._synthesize_sync, text, language)

    def _synthesize_sync(self, text: str, language: str) -> bytes:
        # XTTS returns a list[float] waveform at the model's sample rate.
        kwargs = {"text": text, "language": language}
        if self._speaker_wav:
            kwargs["speaker_wav"] = self._speaker_wav
        wav = self._tts.tts(**kwargs)
        sample_rate = getattr(self._tts.synthesizer, "output_sample_rate", 24000)
        return _floats_to_wav(wav, sample_rate)


def _floats_to_wav(samples, sample_rate: int) -> bytes:
    """Convert a float waveform in [-1, 1] to 16-bit PCM WAV bytes."""
    import struct

    frames = bytearray()
    for s in samples:
        v = int(max(-1.0, min(1.0, float(s))) * 32767)
        frames += struct.pack("<h", v)

    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(bytes(frames))
    return buf.getvalue()
