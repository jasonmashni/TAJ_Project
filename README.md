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

## Run it (no AI installs needed)

```bash
# Windows
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m backend.main

# Mac / Linux
./run.sh
```

Then open **<http://127.0.0.1:8000>** in **Chrome or Microsoft Edge**, complete
the short English setup (what you speak / want to learn / your level), then
**hold the gold button** (or the spacebar), talk, and release.

**Speech runs inside your browser** — the mic and the spoken voice use the
browser's built-in speech engine, so there is *nothing* to install for hearing
and talking. (Edge has the best built-in Arabic voice.)

The only piece that needs setup is the **tutor brain**. Out of the box it's in
"practice mode" (canned replies). Switch on a real tutor below.

---

## Turn on a real tutor brain

Pick one:

**A) Cloud (easiest, best quality).** A real Claude-powered tutor: one light
`pip install`, paste an API key, done. Works on any Python version; costs per
use. *(Provider lands in the next step — see the project chat.)*

**B) Local Ollama (private, free, offline).** [Install Ollama](https://ollama.com),
run `ollama pull qwen2.5:7b-instruct`, set `TAJ_LLM_PROVIDER=ollama`. A multi-GB
download; runs best with a decent CPU/GPU. Independent of your Python version
(it's a separate app, not a pip package).

> **Optional fully-offline speech** (instead of the browser): the local
> `faster-whisper` (STT) and `Coqui TTS` providers also exist, but they require
> **Python 3.9–3.11** (they don't install on 3.12+). The browser path above
> avoids that entirely and is recommended.

Copy `.env.example` to `.env` to set any of these. The status bar shows what's live.

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
