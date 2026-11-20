"""Persistent long-term memory for the LLM.

Stores a single rolling "what I remember about the user" summary in a small
SQLite database, kept separate from the CV/emotion memory in
``ioModules/vision/memory/``. The summary is loaded into the system prompt on
wake and rewritten at the end of each session (see ``module.py``).

All access is best-effort: failures return ``""`` / no-op rather than raising,
so a memory problem can never crash a conversation.
"""

import os
import sqlite3
from typing import Final

# <repo>/data/llm_memory.db. This file lives at
# ConversationModules/LLM/memory.py, so three dirname() hops reach the
# NanoCodebase root. (The CV database.py deliberately uses a different data dir.)
DB_PATH: Final[str] = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data",
    "llm_memory.db",
)

DEFAULT_USER: Final[str] = "default"

_SCHEMA: Final[str] = """
CREATE TABLE IF NOT EXISTS llm_memory (
    user_id    TEXT PRIMARY KEY DEFAULT 'default',
    summary    TEXT NOT NULL DEFAULT '',
    updated_at TEXT
);
"""


def _connect() -> sqlite3.Connection:
    """Open the memory database, creating the data dir and table if needed."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.execute(_SCHEMA)
    return connection


def load_summary(user_id: str = DEFAULT_USER) -> str:
    """Return the stored memory summary for ``user_id``, or ``""`` if none."""
    try:
        connection = _connect()
        try:
            row = connection.execute(
                "SELECT summary FROM llm_memory WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        finally:
            connection.close()
    except sqlite3.Error as error:
        print(f"[Conversation-LLM] Failed to load memory: {error}")
        return ""

    return row[0] if row and row[0] else ""


def save_summary(summary: str, user_id: str = DEFAULT_USER) -> None:
    """Insert or update the rolling memory summary for ``user_id``."""
    try:
        connection = _connect()
        try:
            connection.execute(
                """
                INSERT INTO llm_memory (user_id, summary, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(user_id) DO UPDATE SET
                    summary = excluded.summary,
                    updated_at = excluded.updated_at
                """,
                (user_id, summary),
            )
            connection.commit()
        finally:
            connection.close()
    except sqlite3.Error as error:
        print(f"[Conversation-LLM] Failed to save memory: {error}")


if __name__ == "__main__":
    """Exercise save -> load without needing the model."""
    sample = "The user's name is Alex and they enjoy hiking on weekends."
    save_summary(sample)
    print("Saved summary.")
    loaded = load_summary()
    print(f"Loaded summary: {loaded!r}")
    assert loaded == sample, "Round-trip mismatch"
    print(f"Round-trip OK. Database at: {DB_PATH}")
