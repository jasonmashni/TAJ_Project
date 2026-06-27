# TAJ 👑

**A voice-first language tutor. You talk to it; it talks back in your target
language and dialect, and corrects you in real time.**

TAJ is the anti-flashcard app: instead of tapping translations, you hold a
button and *speak*. TAJ replies out loud in your chosen dialect, fixes your
mistakes in the moment, and quietly builds a personal review deck from the words
*you* actually stumble on. The goal is the fastest realistic path to a real
conversation — not streaks and points.

> Default build: **Levantine Arabic** (تاج = "crown"). Mandarin and Japanese
> profiles ship ready to switch on. See [`DESIGN.md`](DESIGN.md) for the full
> architecture and roadmap.

---

## Run it in 30 seconds (mock mode, no models)

```bash
./run.sh
```

Then open <http://127.0.0.1:8000>, **hold the gold button** (or hold the
spacebar), say something, and release. In mock mode you'll get a canned reply and
a beep — proving the full **mic → transcribe → tutor → speak → review** loop
works end to end before you download a single model.

> `run.sh` makes a virtualenv and installs only the small core deps. To run
> manually: `pip install -r requirements.txt && python -m backend.main`.

---

## Turn on the real local AI

TAJ runs fully offline once you install the three local models. Each is opt-in
because they're large.

| Capability | Install | Enable |
| --- | --- | --- |
| **Speech → text** | `pip install faster-whisper` | `TAJ_STT_PROVIDER=whisper` |
| **Tutor brain** | [Install Ollama](https://ollama.com), then `ollama pull qwen2.5:7b-instruct` | `TAJ_LLM_PROVIDER=ollama` |
| **Text → speech** | `pip install TTS` | `TAJ_TTS_PROVIDER=coqui` |

Copy `.env.example` to `.env`, set the providers (or leave them on `auto` — TAJ
uses the real model if present and silently falls back to mock if not), and
restart. The status bar in the UI shows which providers are live.

---

## How it's wired

```
Browser (mic + speakers + UI)  ⇄  WebSocket  ⇄  FastAPI backend
                                                  │
                                   STT ─ LLM ─ TTS  (swappable providers)
                                   Tutor (pedagogy) · SRS deck (SQLite)
```

- **Local now, web later by design.** It's a web app served on `localhost`; the
  same code deploys behind a domain later. Provider interfaces mean swapping a
  local model for a cloud API (or a GPU host at scale) is a config change.
- **Graceful degradation.** Missing a model? That stage falls back to mock and
  the app keeps running. TTS failing never kills a conversation turn.

## Project layout

```
backend/
  main.py            FastAPI app · WebSocket voice loop · REST (SRS, config)
  config.py          env-driven settings
  languages.py       language + dialect registry (Arabic / Mandarin / Japanese)
  tutor.py           prompt building + response parsing (the pedagogy)
  srs.py             SM-2 spaced repetition over SQLite
  providers/
    base.py          STT/LLM/TTS interfaces + auto→mock factory
    stt_whisper.py   faster-whisper
    llm_ollama.py    Ollama / Qwen2.5
    tts_coqui.py     Coqui XTTS-v2
    mock.py          dependency-free providers (instant demo)
frontend/
  index.html · app.js · styles.css     push-to-talk UI
DESIGN.md            product thesis, architecture, pedagogy, roadmap
```

## Configuration

Everything is env-driven (`TAJ_*`) — see [`.env.example`](.env.example). Switch
languages with `TAJ_LANGUAGE` (`ar-LEV`, `ar-MSA`, `zh-CN`, `ja-JP`) and set the
learner level with `TAJ_LEARNER_LEVEL` (`A1`–`C1`).

## Status

Phase 0 skeleton: the complete voice loop, provider abstraction, tutor prompt,
SM-2 deck, and the Arabic-Levantine profile are in place. Next up (see
[`DESIGN.md`](DESIGN.md)): wire the real local models, a placement conversation,
the review-mode UI, and pronunciation scoring.
