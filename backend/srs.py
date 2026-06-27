"""Spaced repetition (SM-2) over SQLite.

The deck is built from the learner's OWN conversations — the vocab TAJ surfaces
and the corrections it makes — so review time is always spent on the learner's
actual gaps, not a generic word list. That personalization is the compounding
advantage over flashcard apps.
"""

from __future__ import annotations

import os
import sqlite3
import time
from contextlib import contextmanager

from backend.config import settings

_DB_PATH = os.path.join(settings.data_dir, "taj.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS srs_item (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    lang        TEXT NOT NULL,
    front       TEXT NOT NULL,
    reading     TEXT DEFAULT '',
    back        TEXT DEFAULT '',
    ease        REAL NOT NULL DEFAULT 2.5,
    interval_d  REAL NOT NULL DEFAULT 0,
    reps        INTEGER NOT NULL DEFAULT 0,
    due_at      REAL NOT NULL,
    created_at  REAL NOT NULL,
    UNIQUE(lang, front)
);
"""


def init_db() -> None:
    os.makedirs(settings.data_dir, exist_ok=True)
    with _connect() as conn:
        conn.executescript(_SCHEMA)


@contextmanager
def _connect():
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def add_item(lang: str, front: str, reading: str = "", back: str = "") -> None:
    """Insert a new card, or leave an existing one untouched (idempotent)."""
    now = time.time()
    with _connect() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO srs_item
               (lang, front, reading, back, due_at, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (lang, front.strip(), reading.strip(), back.strip(), now, now),
        )


def due_items(lang: str, limit: int = 20) -> list[dict]:
    now = time.time()
    with _connect() as conn:
        rows = conn.execute(
            """SELECT * FROM srs_item
               WHERE lang = ? AND due_at <= ?
               ORDER BY due_at ASC LIMIT ?""",
            (lang, now, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def review(item_id: int, quality: int) -> dict | None:
    """Apply one SM-2 review. ``quality`` is 0-5 (0 = blackout, 5 = perfect)."""
    quality = max(0, min(5, quality))
    with _connect() as conn:
        row = conn.execute(
            "SELECT * FROM srs_item WHERE id = ?", (item_id,)
        ).fetchone()
        if row is None:
            return None

        ease = row["ease"]
        interval = row["interval_d"]
        reps = row["reps"]

        if quality < 3:
            # Lapse: reset the schedule, keep the (slightly reduced) ease.
            reps = 0
            interval = 0  # due again today
        else:
            reps += 1
            if reps == 1:
                interval = 1
            elif reps == 2:
                interval = 6
            else:
                interval = round(interval * ease, 2)

        # SM-2 ease adjustment, floored at 1.3.
        ease = max(
            1.3,
            ease + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02)),
        )

        due_at = time.time() + interval * 86400
        conn.execute(
            """UPDATE srs_item
               SET ease = ?, interval_d = ?, reps = ?, due_at = ?
               WHERE id = ?""",
            (round(ease, 3), interval, reps, due_at, item_id),
        )
        updated = conn.execute(
            "SELECT * FROM srs_item WHERE id = ?", (item_id,)
        ).fetchone()
    return dict(updated)


def count(lang: str) -> dict:
    now = time.time()
    with _connect() as conn:
        total = conn.execute(
            "SELECT COUNT(*) AS c FROM srs_item WHERE lang = ?", (lang,)
        ).fetchone()["c"]
        due = conn.execute(
            "SELECT COUNT(*) AS c FROM srs_item WHERE lang = ? AND due_at <= ?",
            (lang, now),
        ).fetchone()["c"]
    return {"total": total, "due": due}
