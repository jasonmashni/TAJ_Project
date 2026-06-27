"""The pedagogy engine: build the tutor prompt, call the LLM, parse the result.

The tutor returns a lightly-structured response (delimited tags) so we can split
the *spoken reply* from the *corrections*, *translation*, and *mined vocab*. The
parser is deliberately forgiving: if a small local model ignores the format, the
whole output becomes the spoken reply and the loop keeps working.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from backend.languages import LanguageProfile

# How much target-language immersion to use, by level.
_LEVEL_GUIDANCE = {
    "A1": "The learner is a near-total beginner. Keep sentences very short and "
    "simple. You may use some English to scaffold, and always give an English "
    "translation of your reply.",
    "A2": "The learner is an advanced beginner. Use simple target-language "
    "sentences; give an English translation. Minimal English explanation.",
    "B1": "The learner is intermediate. Speak almost entirely in the target "
    "language; translate only difficult phrases.",
    "B2": "The learner is upper-intermediate. Speak in the target language; "
    "translate rarely.",
    "C1": "The learner is advanced. Speak entirely in the target language; do "
    "not translate unless asked.",
}


@dataclass
class TutorResponse:
    reply: str                       # what TAJ says out loud
    corrections: list[dict] = field(default_factory=list)  # {error, fix, why}
    translation: str = ""            # English gloss of the reply
    vocab: list[dict] = field(default_factory=list)        # {front, reading, back}
    raw: str = ""                    # the model's raw output (debugging)


def build_system_prompt(profile: LanguageProfile, level: str) -> str:
    level_note = _LEVEL_GUIDANCE.get(level, _LEVEL_GUIDANCE["A1"])
    return f"""\
You are TAJ, a patient, efficient, voice-based language tutor. You are having a
SPOKEN conversation, so your replies are read aloud — keep them SHORT and natural,
never essay-length.

TARGET LANGUAGE: {profile.name} ({profile.native_name}).
DIALECT: {profile.dialect}.
{profile.persona}

LEARNER LEVEL: {level}. {level_note}

YOUR JOB EVERY TURN:
1. Reply naturally in the target language at the learner's level (i+1: mostly
   understandable, slightly stretching).
2. If the learner made mistakes, correct them SPECIFICALLY and KINDLY — name the
   error and the fix in one short line each. Do not nitpick tiny things for
   beginners; focus on what matters most.
3. Surface 0-2 useful vocabulary items from this exchange for their review deck.
4. Keep the conversation moving — usually end with a simple question.

OUTPUT FORMAT — respond using EXACTLY these tags, nothing else:
<reply>your spoken reply in the target language</reply>
<corrections>
- what they said -> corrected version : one-line reason
(omit this section entirely if there were no mistakes)
</corrections>
<translation>English translation of your reply</translation>
<vocab>
word | reading or transliteration | English meaning
(0-2 lines; omit the section if nothing worth saving)
</vocab>"""


def build_messages(history: list[dict], user_text: str) -> list[dict]:
    """History is a list of {role, content}; append the new user utterance."""
    return [*history, {"role": "user", "content": user_text}]


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #
_TAG = lambda name: re.compile(  # noqa: E731
    rf"<{name}>(.*?)</{name}>", re.DOTALL | re.IGNORECASE
)


def parse_response(raw: str) -> TutorResponse:
    reply = _extract(raw, "reply")
    translation = _extract(raw, "translation")
    corrections = _parse_corrections(_extract(raw, "corrections"))
    vocab = _parse_vocab(_extract(raw, "vocab"))

    if not reply:
        # Model ignored the format — treat the whole thing as the spoken reply.
        reply = raw.strip()

    return TutorResponse(
        reply=reply,
        corrections=corrections,
        translation=translation,
        vocab=vocab,
        raw=raw,
    )


def _extract(raw: str, name: str) -> str:
    m = _TAG(name).search(raw)
    return m.group(1).strip() if m else ""


def _parse_corrections(block: str) -> list[dict]:
    out: list[dict] = []
    for line in block.splitlines():
        line = line.strip().lstrip("-").strip()
        if not line or "->" not in line:
            continue
        left, _, rest = line.partition("->")
        fix, _, why = rest.partition(":")
        out.append(
            {"error": left.strip(), "fix": fix.strip(), "why": why.strip()}
        )
    return out


def _parse_vocab(block: str) -> list[dict]:
    out: list[dict] = []
    for line in block.splitlines():
        line = line.strip().lstrip("-").strip()
        if not line or "|" not in line:
            continue
        parts = [p.strip() for p in line.split("|")]
        front = parts[0] if len(parts) > 0 else ""
        reading = parts[1] if len(parts) > 1 else ""
        back = parts[2] if len(parts) > 2 else ""
        if front:
            out.append({"front": front, "reading": reading, "back": back})
    return out
