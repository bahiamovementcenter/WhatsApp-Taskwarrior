"""Read-only access to the whatsapp-mcp bridge's messages.db.

The database is opened with SQLite ``mode=ro``, so this module cannot create,
change or lock-for-write the bridge's store. It never talks to the bridge's
HTTP API, so it cannot send anything to WhatsApp.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Message:
    id: str
    chat_jid: str
    chat_name: str | None
    sender: str
    content: str
    timestamp: str
    is_from_me: bool
    media_type: str | None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Chat:
    jid: str
    name: str | None
    last_message_time: str | None

    @property
    def is_group(self) -> bool:
        return self.jid.endswith("@g.us")


def connect(db_path: Path) -> sqlite3.Connection:
    path = db_path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"WhatsApp messages database not found at {path}; run the bridge once first")
    return sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)


def list_chats(db_path: Path) -> list[Chat]:
    with closing(connect(db_path)) as conn:
        rows = conn.execute("SELECT jid, name, last_message_time FROM chats ORDER BY last_message_time DESC").fetchall()
    return [Chat(*r) for r in rows]


def fetch_messages(
    db_path: Path,
    chats: list[str],
    cursors: dict[str, str],
    limit: int,
) -> list[Message]:
    """Messages from ``chats`` at or after each chat's cursor, oldest first.

    ``>=`` (not ``>``) so a message stored later with the same timestamp as the
    cursor is not skipped; re-reading the boundary message is harmless because
    task creation is idempotent per message.
    """
    out: list[Message] = []
    with closing(connect(db_path)) as conn:
        for jid in chats:
            rows = conn.execute(
                """
                SELECT m.id, m.chat_jid, c.name, m.sender, COALESCE(m.content, ''), m.timestamp,
                       m.is_from_me, m.media_type
                FROM messages m LEFT JOIN chats c ON c.jid = m.chat_jid
                WHERE m.chat_jid = ? AND m.timestamp >= ? AND m.deleted_at IS NULL
                ORDER BY m.timestamp ASC, m.id ASC
                LIMIT ?
                """,
                (jid, cursors.get(jid, ""), limit),
            ).fetchall()
            out.extend(
                Message(
                    id=r[0],
                    chat_jid=r[1],
                    chat_name=r[2],
                    sender=r[3] or "",
                    content=r[4],
                    timestamp=str(r[5]),
                    is_from_me=bool(r[6]),
                    media_type=r[7] or None,
                )
                for r in rows
            )
    out.sort(key=lambda m: (m.timestamp, m.chat_jid, m.id))
    return out[:limit]


def existing_message_keys(db_path: Path, keys: list[tuple[str, str]]) -> set[tuple[str, str]]:
    """Which (chat_jid, message_id) pairs really exist in messages.db."""
    found: set[tuple[str, str]] = set()
    with closing(connect(db_path)) as conn:
        for jid, mid in keys:
            if conn.execute("SELECT 1 FROM messages WHERE chat_jid = ? AND id = ?", (jid, mid)).fetchone():
                found.add((jid, mid))
    return found
