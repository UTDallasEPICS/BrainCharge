"""Durable single-user conversation history, independent of robot hardware."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterator


class ConversationStore:
    def __init__(self, path: Path) -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path)
        self._connection.row_factory = sqlite3.Row
        try:
            self._connection.execute("PRAGMA foreign_keys = ON")
            self._connection.executescript("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
                    ended_at TEXT
                );
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER NOT NULL REFERENCES conversations(id),
                    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
                    content TEXT NOT NULL,
                    status TEXT NOT NULL CHECK (status IN ('pending', 'completed', 'failed', 'interrupted')),
                    reply_to INTEGER UNIQUE REFERENCES messages(id),
                    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
                );
                CREATE INDEX IF NOT EXISTS messages_by_conversation
                    ON messages(conversation_id, id);
                CREATE TABLE IF NOT EXISTS conversation_summaries (
                    conversation_id INTEGER PRIMARY KEY REFERENCES conversations(id),
                    content TEXT NOT NULL DEFAULT '',
                    source_message_id INTEGER REFERENCES messages(id),
                    source_offset INTEGER NOT NULL DEFAULT 0 CHECK (source_offset >= 0),
                    target_message_id INTEGER NOT NULL REFERENCES messages(id),
                    pending INTEGER NOT NULL DEFAULT 1 CHECK (pending IN (0, 1)),
                    updated_at TEXT
                );
                -- Backfill summary work for conversations closed before Phase 3.
                INSERT INTO conversation_summaries (conversation_id, target_message_id)
                SELECT c.id, MAX(m.id) FROM conversations c
                JOIN messages m ON m.conversation_id = c.id
                WHERE c.ended_at IS NOT NULL AND m.status = 'completed'
                GROUP BY c.id
                ON CONFLICT(conversation_id) DO NOTHING;
            """)
        except BaseException:
            self._connection.close()
            raise

    def close(self) -> None:
        self._connection.close()

    def require_open(self, conversation_id: int) -> None:
        row = self._connection.execute(
            "SELECT ended_at FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        if row is None or row["ended_at"] is not None:
            raise ValueError("This conversation is not open. Start another with /new.")

    def start_conversation(self, previous_id: int | None = None) -> int:
        # /new closes the old conversation and creates its replacement atomically.
        with self._connection:
            if previous_id is not None:
                self.require_open(previous_id)
                self._end_conversation(previous_id)
            cursor = self._connection.execute("INSERT INTO conversations DEFAULT VALUES")
            return cursor.lastrowid

    def _end_conversation(self, conversation_id: int) -> None:
        self._connection.execute(
            "UPDATE messages SET status = 'interrupted' "
            "WHERE conversation_id = ? AND status = 'pending'", (conversation_id,)
        )
        self._connection.execute(
            "UPDATE conversations SET ended_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') "
            "WHERE id = ? AND ended_at IS NULL", (conversation_id,)
        )
        self._queue_summary(conversation_id)

    def end_conversation(self, conversation_id: int) -> None:
        with self._connection:
            self._end_conversation(conversation_id)

    def add_user_message(self, conversation_id: int, text: str) -> int:
        with self._connection:
            self.require_open(conversation_id)
            cursor = self._connection.execute(
                "INSERT INTO messages (conversation_id, role, content, status) "
                "VALUES (?, 'user', ?, 'pending')", (conversation_id, text)
            )
            return cursor.lastrowid

    def complete_turn(self, user_message_id: int, reply: str) -> None:
        with self._connection:
            # Updating first obtains the write lock; a failed insert rolls it back.
            cursor = self._connection.execute(
                "UPDATE messages SET status = 'completed' "
                "WHERE id = ? AND role = 'user' AND status = 'pending'",
                (user_message_id,),
            )
            if cursor.rowcount != 1:
                raise ValueError("The message is no longer waiting for a reply.")
            self._connection.execute(
                "INSERT INTO messages (conversation_id, role, content, status, reply_to) "
                "SELECT conversation_id, 'assistant', ?, 'completed', id "
                "FROM messages WHERE id = ?", (reply, user_message_id)
            )

    def fail_turn(self, user_message_id: int, interrupted: bool = False) -> None:
        with self._connection:
            self._connection.execute(
                "UPDATE messages SET status = ? WHERE id = ? AND status = 'pending'",
                ("interrupted" if interrupted else "failed", user_message_id),
            )

    def recent_exchanges(self, conversation_id: int) -> Iterator[dict]:
        """Yield complete exchanges newest first without loading the full archive."""
        cursor = self._connection.execute(
            "SELECT u.id AS user_id, a.id AS assistant_id, "
            "u.content AS user_content, a.content AS assistant_content "
            "FROM messages u JOIN messages a ON a.reply_to = u.id "
            "WHERE u.conversation_id = ? AND a.conversation_id = u.conversation_id "
            "AND u.role = 'user' AND a.role = 'assistant' "
            "AND u.status = 'completed' AND a.status = 'completed' ORDER BY u.id DESC",
            (conversation_id,),
        )
        try:
            for row in cursor:
                yield dict(row)
        finally:
            cursor.close()

    def list_conversations(self) -> list[dict]:
        cursor = self._connection.execute(
            "SELECT c.id, c.started_at, c.ended_at, COUNT(m.id) AS message_count "
            "FROM conversations c LEFT JOIN messages m ON m.conversation_id = c.id "
            "GROUP BY c.id ORDER BY c.id DESC"
        )
        return [dict(row) for row in cursor]

    def _queue_summary(self, conversation_id: int, through_id: int | None = None) -> None:
        row = self._connection.execute(
            "SELECT MAX(id) AS id FROM messages WHERE conversation_id = ? "
            "AND status = 'completed' AND id <= ?",
            (conversation_id, through_id if through_id is not None else 2**63 - 1),
        ).fetchone()
        target_id = row["id"]
        if target_id is None:
            return
        self._connection.execute(
            "INSERT INTO conversation_summaries (conversation_id, target_message_id) VALUES (?, ?) "
            "ON CONFLICT(conversation_id) DO UPDATE SET "
            "target_message_id = MAX(target_message_id, excluded.target_message_id), "
            "pending = CASE WHEN source_message_id IS NULL "
            "OR source_message_id < MAX(target_message_id, excluded.target_message_id) "
            "OR source_offset < (SELECT length(content) FROM messages "
            "WHERE id = MAX(target_message_id, excluded.target_message_id)) THEN 1 ELSE pending END",
            (conversation_id, target_id),
        )

    def queue_summary(self, conversation_id: int, through_id: int | None = None) -> None:
        with self._connection:
            self._queue_summary(conversation_id, through_id)

    def get_summary(self, conversation_id: int) -> dict | None:
        row = self._connection.execute(
            "SELECT * FROM conversation_summaries WHERE conversation_id = ?", (conversation_id,)
        ).fetchone()
        return dict(row) if row is not None else None

    def pending_summaries(self, limit: int = 3) -> list[int]:
        rows = self._connection.execute(
            "SELECT conversation_id FROM conversation_summaries WHERE pending = 1 "
            "ORDER BY conversation_id DESC LIMIT ?", (limit,)
        )
        return [row["conversation_id"] for row in rows]

    def summary_sources(self, state: dict) -> Iterator[dict]:
        cursor = self._connection.execute(
            "SELECT id, role, content FROM messages WHERE conversation_id = ? "
            "AND status = 'completed' AND id >= ? AND id <= ? ORDER BY id",
            (state["conversation_id"], state["source_message_id"] or 0, state["target_message_id"]),
        )
        try:
            for row in cursor:
                yield dict(row)
        finally:
            cursor.close()

    def save_summary(self, state: dict, content: str, source_id: int, offset: int) -> bool:
        # A competing update must not be overwritten by a summary of an older prefix.
        with self._connection:
            cursor = self._connection.execute(
                "UPDATE conversation_summaries SET content = ?, source_message_id = ?, "
                "source_offset = ?, updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now'), "
                "pending = CASE WHEN target_message_id = ? AND ? >= "
                "(SELECT length(content) FROM messages WHERE id = target_message_id) THEN 0 ELSE 1 END "
                "WHERE conversation_id = ? AND source_message_id IS ? AND source_offset = ?",
                (content, source_id, offset, source_id, offset, state["conversation_id"],
                 state["source_message_id"], state["source_offset"]),
            )
            return cursor.rowcount == 1

    def previous_summaries(self, conversation_id: int, limit: int = 3) -> list[dict]:
        rows = self._connection.execute(
            "SELECT s.conversation_id, s.content, s.pending, c.started_at "
            "FROM conversation_summaries s JOIN conversations c ON c.id = s.conversation_id "
            "WHERE s.conversation_id != ? AND c.ended_at IS NOT NULL AND s.content != '' "
            "ORDER BY c.id DESC LIMIT ?", (conversation_id, limit),
        )
        return [dict(row) for row in rows]

    def get_messages(self, conversation_id: int) -> list[dict]:
        exists = self._connection.execute(
            "SELECT 1 FROM conversations WHERE id = ?", (conversation_id,)
        ).fetchone()
        if exists is None:
            raise ValueError(f"Conversation {conversation_id} does not exist.")
        cursor = self._connection.execute(
            "SELECT id, role, content, status, created_at FROM messages "
            "WHERE conversation_id = ? ORDER BY id", (conversation_id,)
        )
        return [dict(row) for row in cursor]
