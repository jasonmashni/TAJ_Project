"""Runtime configuration for TAJ.

All settings can be overridden via environment variables prefixed with ``TAJ_``
or a local ``.env`` file. See ``.env.example``.
"""

from __future__ import annotations

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

# Load .env into the process environment too, so the Anthropic SDK (which reads
# the standard ANTHROPIC_API_KEY var) picks it up from the same file.
load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="TAJ_", env_file=".env", extra="ignore"
    )

    # --- server ---
    host: str = "127.0.0.1"
    port: int = 8000

    # --- active language/dialect (key into backend.languages.REGISTRY) ---
    # These are defaults only — the onboarding screen lets the learner choose,
    # and the choice is passed per-connection on the WebSocket.
    language: str = "ar-LEV"
    learner_level: str = "A1"  # CEFR-ish: A1 A2 B1 B2 C1
    native_language: str = "en"  # the learner's own language (for translations)

    # --- provider selection ---
    # "auto"  -> try the real local provider, fall back to "mock" if unavailable
    # "mock"  -> force the dependency-free mock (great for a first run / demo)
    # or the explicit provider name (e.g. "whisper", "ollama", "coqui")
    stt_provider: str = "auto"
    llm_provider: str = "auto"
    tts_provider: str = "auto"

    # --- faster-whisper (STT) ---
    whisper_model: str = "small"       # tiny | base | small | medium | large-v3
    whisper_device: str = "auto"       # cpu | cuda | auto
    whisper_compute_type: str = "int8"  # int8 (cpu) | float16 (gpu)

    # --- Ollama (local LLM tutor brain) ---
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b-instruct"

    # --- Claude (cloud LLM tutor brain) ---
    # The SDK also reads the standard ANTHROPIC_API_KEY env var; either works.
    anthropic_api_key: str | None = None
    claude_model: str = "claude-opus-4-8"  # set to claude-haiku-4-5 for speed/cost

    # --- Coqui XTTS (TTS) ---
    coqui_model: str = "tts_models/multilingual/multi-dataset/xtts_v2"
    tts_speaker_wav: str | None = None  # path to a reference clip for voice cloning

    # --- storage ---
    data_dir: str = "./data"


settings = Settings()
