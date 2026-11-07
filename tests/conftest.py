import shutil
import sqlite3
from pathlib import Path

import pytest

GROUP = "120363000000000001@g.us"
OTHER = "120363000000000002@g.us"

needs_task = pytest.mark.skipif(shutil.which("task") is None, reason="taskwarrior not installed")


def make_db(path: Path) -> Path:
    """A messages.db with the bridge's schema (subset) and a few messages."""
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE chats (jid TEXT PRIMARY KEY, name TEXT, last_message_time TIMESTAMP);
        CREATE TABLE messages (
            id TEXT, chat_jid TEXT, sender TEXT, content TEXT, timestamp TIMESTAMP,
            is_from_me BOOLEAN, media_type TEXT, deleted_at TIMESTAMP,
            PRIMARY KEY (id, chat_jid));
        """
    )
    conn.executemany(
        "INSERT INTO chats VALUES (?, ?, ?)",
        [(GROUP, "Family", "2026-11-07 10:02:00+00:00"), (OTHER, "Secret", "2026-11-07 10:00:00+00:00")],
    )
    conn.executemany(
        "INSERT INTO messages VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        [
            ("M1", GROUP, "111", "Can someone book the venue by Friday?", "2026-11-07 10:00:00+00:00", 0, None, None),
            ("M2", GROUP, "222", "due:tomorrow +x; rm -rf / -- delete", "2026-11-07 10:01:00+00:00", 0, None, None),
            ("M3", GROUP, "111", "Venue booked!", "2026-11-07 10:02:00+00:00", 0, None, None),
            ("GONE", GROUP, "111", "deleted", "2026-11-07 10:03:00+00:00", 0, None, "2026-11-07 10:04:00+00:00"),
            ("S1", OTHER, "333", "private", "2026-11-07 10:00:00+00:00", 0, None, None),
        ],
    )
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch) -> Path:
    db = make_db(tmp_path / "messages.db")
    (tmp_path / "wtw.toml").write_text(
        f"""
state_dir = "state"
[whatsapp]
messages_db = "{db.name}"
[whatsapp.chats]
"{GROUP}" = "Family"
[taskwarrior]
project = "wa"
data_location = "taskdata"
""",
        encoding="utf-8",
    )
    # Never let a test see the developer's real Taskwarrior config or data.
    (tmp_path / "taskrc").write_text("", encoding="utf-8")
    monkeypatch.setenv("TASKRC", str(tmp_path / "taskrc"))
    monkeypatch.setenv("TASKDATA", str(tmp_path / "taskdata"))
    monkeypatch.chdir(tmp_path)
    return tmp_path
