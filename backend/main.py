"""TAJ backend entry point.

Serves the front-end, exposes the SRS REST endpoints, and runs the realtime
voice loop over a WebSocket:

    client --(binary: one spoken utterance, e.g. webm/opus)--> server
    server --(json: user transcript)--> client
    server --(json: tutor reply + corrections + translation + vocab)--> client
    server --(json: base64 WAV of the spoken reply)--> client

Run:  python -m backend.main   (or use ./run.sh)
"""

from __future__ import annotations

import base64
import logging
import os
import tempfile

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend import srs, tutor
from backend.config import settings
from backend.languages import (
    LEVELS,
    NATIVE_LANGUAGES,
    REGISTRY,
    get_profile,
    native_name,
)
from backend.providers import get_llm, get_stt, get_tts
from backend.schemas import ConfigResponse, ReviewRequest

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("taj")

app = FastAPI(title="TAJ", version="0.1.0")

_FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")

# Providers are constructed once at startup (loading a Whisper/XTTS model is
# expensive). Under "auto" these gracefully fall back to mocks.
_stt = None
_llm = None
_tts = None


@app.on_event("startup")
def _startup() -> None:
    global _stt, _llm, _tts
    srs.init_db()
    _stt = get_stt()
    _llm = get_llm()
    _tts = get_tts()
    log.info(
        "TAJ ready — language=%s providers: stt=%s llm=%s tts=%s",
        settings.language,
        _stt.name,
        _llm.name,
        _tts.name,
    )


# --------------------------------------------------------------------------- #
# REST
# --------------------------------------------------------------------------- #
@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": app.version}


@app.get("/api/config", response_model=ConfigResponse)
def config() -> ConfigResponse:
    p = get_profile(settings.language)
    return ConfigResponse(
        language=p.key,
        name=p.name,
        native_name=p.native_name,
        dialect=p.dialect,
        rtl=p.rtl,
        level=settings.learner_level,
        providers={
            "stt": _stt.name if _stt else "?",
            "llm": _llm.name if _llm else "?",
            "tts": _tts.name if _tts else "?",
        },
    )


@app.get("/api/languages")
def languages() -> dict:
    """Everything the onboarding screen needs to populate its dropdowns."""
    return {
        "targets": [
            {
                "key": p.key,
                "name": p.name,
                "native_name": p.native_name,
                "dialect": p.dialect,
                "rtl": p.rtl,
            }
            for p in REGISTRY.values()
        ],
        "levels": [{"key": k, "label": v} for k, v in LEVELS.items()],
        "natives": [{"key": k, "label": v} for k, v in NATIVE_LANGUAGES.items()],
        "providers": {
            "stt": _stt.name if _stt else "?",
            "llm": _llm.name if _llm else "?",
            "tts": _tts.name if _tts else "?",
        },
    }


@app.get("/api/srs/due")
def srs_due(lang: str | None = None) -> dict:
    p = get_profile(lang or settings.language)
    return {"items": srs.due_items(p.key), "counts": srs.count(p.key)}


@app.post("/api/srs/review")
def srs_review(req: ReviewRequest) -> dict:
    updated = srs.review(req.item_id, req.quality)
    if updated is None:
        return {"ok": False, "error": "item not found"}
    return {"ok": True, "item": updated}


# --------------------------------------------------------------------------- #
# WebSocket voice loop
# --------------------------------------------------------------------------- #
@app.websocket("/ws")
async def ws(websocket: WebSocket) -> None:
    await websocket.accept()

    # The learner's choices arrive as query params from the onboarding screen,
    # e.g. /ws?lang=ar-LEV&level=A1&native=en. Fall back to server defaults.
    params = websocket.query_params
    profile = get_profile(params.get("lang") or settings.language)
    level = params.get("level") or settings.learner_level
    native = native_name(params.get("native") or settings.native_language)
    system = tutor.build_system_prompt(profile, level, native)
    history: list[dict] = []

    # In "browser" speech mode the browser does speech-to-text and speaks the
    # reply itself (zero installs) — so the server skips its own TTS.
    server_tts = params.get("speech") != "browser"

    # Greet first — speak it AND show the native-language translation, so an
    # English speaker immediately understands what's happening.
    await _send_assistant(
        websocket,
        profile,
        history,
        reply=profile.greeting,
        corrections=[],
        translation=profile.greeting_en,
        vocab=[],
        send_audio=server_tts,
    )

    try:
        while True:
            message = await websocket.receive()

            if message.get("type") == "websocket.disconnect":
                break

            audio = message.get("bytes")
            if audio is None:
                # Text control messages (e.g. typed input) — optional path.
                text = message.get("text")
                if not text:
                    continue
                user_text = text
            else:
                user_text = await _transcribe(audio, profile.whisper_lang)

            if not user_text.strip():
                await websocket.send_json(
                    {"type": "error", "message": "Didn't catch that — try again."}
                )
                continue

            await websocket.send_json(
                {"type": "transcript", "role": "user", "text": user_text}
            )

            # Run the tutor brain.
            messages = tutor.build_messages(history, user_text)
            raw = await _llm.complete(system, messages)
            resp = tutor.parse_response(raw)

            # Persist conversation + mine the deck.
            history.append({"role": "user", "content": user_text})
            history.append({"role": "assistant", "content": resp.reply})
            _store_deck(profile.key, resp)

            await _send_assistant(
                websocket,
                profile,
                history,
                reply=resp.reply,
                corrections=resp.corrections,
                translation=resp.translation,
                vocab=resp.vocab,
                send_audio=server_tts,
            )
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001 - keep the socket from 500-ing silently
        log.exception("voice loop error")
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
        except Exception:  # noqa: BLE001
            pass


async def _transcribe(audio: bytes, whisper_lang: str) -> str:
    # Whisper decodes via ffmpeg, which wants a file; write to a temp path.
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as tmp:
        tmp.write(audio)
        path = tmp.name
    try:
        return await _stt.transcribe(path, whisper_lang)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


async def _send_assistant(
    websocket: WebSocket,
    profile,
    history: list[dict],
    *,
    reply: str,
    corrections: list[dict],
    translation: str,
    vocab: list[dict],
    send_audio: bool = True,
) -> None:
    await websocket.send_json(
        {
            "type": "message",
            "role": "assistant",
            "text": reply,
            "corrections": corrections,
            "translation": translation,
            "vocab": vocab,
        }
    )
    # In browser-speech mode the browser speaks the reply itself; skip server TTS.
    if not send_audio:
        return
    # Synthesize and stream the spoken reply.
    try:
        wav = await _tts.synthesize(reply, profile.tts_lang)
        await websocket.send_json(
            {
                "type": "audio",
                "format": "wav",
                "data": base64.b64encode(wav).decode("ascii"),
            }
        )
    except Exception as exc:  # noqa: BLE001 - TTS failure shouldn't kill the turn
        log.warning("TTS failed: %s", exc)


def _store_deck(lang: str, resp: tutor.TutorResponse) -> None:
    for v in resp.vocab:
        srs.add_item(lang, v["front"], v.get("reading", ""), v.get("back", ""))
    for c in resp.corrections:
        if c.get("fix"):
            srs.add_item(lang, c["fix"], "", c.get("why", ""))


# --------------------------------------------------------------------------- #
# Static front-end (mounted last so /api and /ws take precedence)
# --------------------------------------------------------------------------- #
@app.get("/")
def index() -> FileResponse:
    return FileResponse(os.path.join(_FRONTEND_DIR, "index.html"))


app.mount("/", StaticFiles(directory=_FRONTEND_DIR), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )
