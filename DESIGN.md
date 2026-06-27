# TAJ — Design Document

> **TAJ** (Arabic: تاج, "crown") is a voice-first language tutor. You *talk to it*,
> it talks back in your target language and dialect, and it corrects you in real
> time. It is deliberately **not** a gamified flashcard app — the goal is the
> fastest realistic path from zero to holding a real conversation.

---

## 1. Product thesis

Most language apps optimize for *engagement* (streaks, points, cartoon
mascots). TAJ optimizes for **acquisition speed**. The fastest way an adult
reaches conversational ability is:

1. **High-volume comprehensible input** at the edge of your level (Krashen's
   *i+1*) — you understand ~80–90% and stretch for the rest.
2. **Lots of speaking** with **immediate, specific correction** — you produce
   language and get told exactly what was off and why.
3. **Spaced repetition** of the words and phrases *you personally* stumbled on —
   not a generic deck.

TAJ fuses all three into one loop: **a spoken conversation with an AI tutor that
corrects you and quietly builds your personal review deck from your own
mistakes.**

### What makes it "better than the competitors"

| Competitor pattern | TAJ |
| --- | --- |
| Tap-to-translate flashcards | Real spoken dialogue, mic in / voice out |
| Generic one-size course | Adapts to *your* errors every turn |
| "Standard" textbook dialect | Pick a **specific dialect** (e.g. Levantine vs MSA) |
| Gamified, slow, "fun" | To-the-point, fast, respectful of your time |
| Corrections after a lesson | Correction **in the moment**, as you speak |

---

## 2. The core loop

```
        ┌──────────────────────────────────────────────────────────┐
        │                     ONE CONVERSATION TURN                   │
        └──────────────────────────────────────────────────────────┘

  🎤  You speak  ──►  STT (Whisper)  ──►  text of what you said
                                            │
                                            ▼
                              Tutor brain (LLM) decides:
                                • Did you make mistakes? → corrections
                                • Reply in-dialect at your level (i+1)
                                • Surface 0–2 new words for your deck
                                            │
                         ┌──────────────────┴───────────────────┐
                         ▼                                       ▼
                 TTS (XTTS) speaks  🔊                 SRS stores your
                 the reply back to you                 mistakes + new words
                         │                                       │
                         └──────────────────┬────────────────────┘
                                            ▼
                                   You respond → loop
```

Out-of-conversation, a lightweight **review mode** drills the SRS deck (the words
TAJ mined from your real conversations) using an SM-2 spaced-repetition schedule.

---

## 3. Architecture

TAJ is a **local web app**: a browser front-end (mic + speakers + UI) talking to
a local Python backend over a WebSocket. This is the key decision that satisfies
*"host locally now, plan for web expansion"* — the exact same codebase runs on
`localhost` today and behind a domain tomorrow. No Electron, no rewrite.

```
┌─────────────────────────────┐         WebSocket          ┌──────────────────────────────┐
│         Browser (UI)        │  ◄──────────────────────►  │      FastAPI backend          │
│  • mic capture (MediaRec.)  │   audio in / events+audio  │                               │
│  • audio playback           │            out             │   Orchestrator (voice loop)   │
│  • transcript + corrections │                            │        │      │      │         │
└─────────────────────────────┘                            │        ▼      ▼      ▼         │
                                                            │      STT    LLM    TTS        │
                                                            │   provider interfaces (swap)  │
                                                            │        │      │      │         │
                                                            │  faster-  Ollama  Coqui        │
                                                            │  whisper  Qwen2.5 XTTS-v2      │
                                                            │                               │
                                                            │   Tutor (pedagogy) · SRS      │
                                                            │   SQLite (progress + deck)    │
                                                            └──────────────────────────────┘
```

### Why these pieces

- **Frontend = web app, not native.** The browser already has first-class mic
  and speaker access (`getUserMedia`, `MediaRecorder`, `<audio>`/Web Audio).
  Serving it locally now and on the web later is a deployment change only.
- **Backend = Python/FastAPI.** Python is where the local-AI ecosystem lives
  (Whisper, Coqui, Ollama clients). FastAPI gives us async + WebSockets cleanly.
- **WebSocket, not REST.** A conversation is bidirectional and latency-sensitive;
  a persistent socket lets us stream audio in and events/audio back.
- **Provider interfaces.** `STTProvider` / `LLMProvider` / `TTSProvider` are
  abstract. Today they point at local models; swapping to a cloud API (or to a
  GPU box when you scale to the web) is a one-line config change.

### The local-AI stack (chosen for the Arabic / Mandarin / Japanese path)

| Stage | Tool | Why |
| --- | --- | --- |
| Speech → text | **faster-whisper** (`large-v3` for quality, `small` for speed) | Best open STT; strong Arabic, Mandarin, Japanese; runs on CPU or GPU |
| Tutor brain | **Ollama** running **Qwen2.5-Instruct** | Best open-weight multilingual model for Arabic *and* CJK; one model covers all three target languages |
| Text → speech | **Coqui XTTS-v2** | Multilingual neural TTS incl. Arabic/Chinese/Japanese; supports voice cloning from a short reference clip |

> **Mock mode.** Every provider has a dependency-free `Mock*` implementation so
> the whole loop runs *now* with no model downloads (canned transcript, templated
> reply, a synthesized beep for audio). Flip `TAJ_*_PROVIDER` to the real
> provider once you've installed the models. See `README.md`.

---

## 4. The pedagogy engine (`tutor.py`)

The tutor is a carefully prompted LLM, not a hand-written rules engine. Each turn
it receives: the learner's CEFR-ish **level**, the **dialect profile**, the
**conversation history**, and the **new utterance**. It returns a structured
response:

```
<reply>      … natural, in-dialect, short (it's spoken aloud) …       </reply>
<corrections>
- <what you said> -> <corrected> : <one-line why>
</corrections>
<translation> … English gloss of the reply, for beginners …          </translation>
<vocab> word | reading/translit | meaning </vocab>
```

Design rules baked into the system prompt:

- **Speak mostly in the target language**, scaled to the learner's level
  (more native language for beginners, almost none for advanced).
- **Correct gently but specifically** — name the error and the fix, don't lecture.
- **Keep replies short** — this is a *spoken* conversation, not an essay.
- **Stay in the chosen dialect** — Levantine ≠ MSA; the persona enforces it.
- **Mine 0–2 vocab items per turn** for the SRS deck.

Robust parsing: if a local model ignores the format, the whole output is treated
as the spoken reply (graceful degradation), so the loop never breaks.

---

## 5. Spaced repetition (`srs.py`)

A minimal, proven **SM-2** scheduler over SQLite. Items are created from the
tutor's `<vocab>` and `<corrections>` output — i.e. **your** gaps, not a generic
deck. Review mode asks for recall, you self-grade 0–5, and the interval grows.

This is what makes TAJ compounding: the more you talk, the more precisely it
knows what *you* need to drill.

---

## 6. Data model (SQLite, local)

```
learner(id, name, native_lang, target_lang, level, created_at)
session(id, learner_id, started_at, ended_at)
turn(id, session_id, role, text, audio_ms, created_at)
srs_item(id, learner_id, lang, front, back, reading,
         ease, interval_days, reps, due_at, created_at)
```

On the web, swap SQLite → Postgres (the repository layer is the only thing that
changes). User accounts + auth land at that stage.

---

## 7. Roadmap

**Phase 0 — Skeleton (this repo).** Full voice loop end-to-end in mock mode;
provider interfaces; tutor prompt; SRS engine; Arabic-Levantine profile;
Mandarin/Japanese stubs.

**Phase 1 — Real local models.** Wire faster-whisper + Ollama/Qwen2.5 + XTTS-v2.
Tune the Levantine persona. Latency pass (stream partial STT, chunk TTS).

**Phase 2 — Learning depth.** Placement conversation → auto level. SRS review UI.
Pronunciation scoring (phoneme alignment). Per-learner persistence.

**Phase 3 — Breadth.** Turn on Mandarin + Japanese profiles. Dialect picker UI.
Lesson "tracks" (travel, business) layered on top of free conversation.

**Phase 4 — Web.** Deploy backend to a GPU host, Postgres, accounts/billing,
multi-tenant. Same frontend, same provider interfaces — cloud providers optional.

---

## 8. Open decisions (your call)

1. **Dialect default** — currently Levantine (Shami). MSA / Egyptian / Gulf?
2. **Voice** — generic XTTS speaker, or clone a specific reference voice for TAJ?
3. **Latency vs quality** — Whisper `small` (fast) vs `large-v3` (accurate) as the
   default; depends on your machine.
4. **Push-to-talk vs always-listening** — skeleton ships push-to-talk (most
   reliable); voice-activity detection is a Phase 1 add.
