"""Dependency-free providers so the full voice loop runs with zero model downloads.

This is what makes a fresh checkout demoable in seconds: canned STT, a templated
tutor reply (in the correct delimited format so the parser exercises its real
path), and a synthesized sine-wave "beep" as the spoken audio.
"""

from __future__ import annotations

import io
import math
import struct
import wave

from backend.providers.base import LLMProvider, STTProvider, TTSProvider


class MockSTT(STTProvider):
    name = "mock"

    async def transcribe(self, audio_path: str, language: str) -> str:
        # We can't actually recognize speech without a model, so return a
        # placeholder the tutor can react to. Swap to WhisperSTT for real input.
        return "[mock] (install faster-whisper to transcribe real speech)"


class MockLLM(LLMProvider):
    name = "mock"

    async def complete(self, system: str, messages: list[dict]) -> str:
        last_user = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"),
            "",
        )
        # Emit the exact delimited format the real tutor uses, so tutor.py's
        # parser runs its genuine code path even in mock mode.
        return (
            "<reply>تمام! (this is a mock reply — connect Ollama for a real tutor) "
            "سمعت إنك قلت شي. حاول كمان مرة.</reply>\n"
            "<corrections>\n"
            f"- {last_user[:40]} -> (mock has no real correction) : "
            "enable the Ollama provider for live feedback\n"
            "</corrections>\n"
            "<translation>Great! I heard you say something. Try again.</translation>\n"
            "<vocab>تمام | tamaam | okay / great</vocab>"
        )


class MockTTS(TTSProvider):
    name = "mock"

    async def synthesize(self, text: str, language: str) -> bytes:
        """Return a short, pleasant two-tone WAV so playback is audibly working."""
        return _beep_wav()


def _beep_wav(duration_s: float = 0.5, sample_rate: int = 16000) -> bytes:
    """Pure-stdlib WAV: a soft 440→660 Hz chirp. No numpy, no models."""
    n = int(duration_s * sample_rate)
    frames = bytearray()
    for i in range(n):
        t = i / sample_rate
        freq = 440 + (220 * i / n)  # gentle rise
        # fade in/out to avoid clicks
        env = min(1.0, t / 0.05, (duration_s - t) / 0.05)
        sample = int(0.3 * env * 32767 * math.sin(2 * math.pi * freq * t))
        frames += struct.pack("<h", max(-32768, min(32767, sample)))

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)  # 16-bit
        wav.setframerate(sample_rate)
        wav.writeframes(bytes(frames))
    return buf.getvalue()
