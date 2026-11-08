"""Write a fake bridge messages.db from chat.json (the bridge's own table layout).

python examples/demo/make_sample_db.py OUT.db --day 1    # create with day 1
python examples/demo/make_sample_db.py OUT.db --day 2    # add day 2's messages
"""

import argparse
import json
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS chats (
    jid TEXT PRIMARY KEY, name TEXT, last_message_time TIMESTAMP,
    ephemeral_expiration INTEGER NOT NULL DEFAULT 0,
    ephemeral_setting_timestamp INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS messages (
    id TEXT, chat_jid TEXT, sender TEXT, content TEXT, timestamp TIMESTAMP, is_from_me BOOLEAN,
    media_type TEXT, filename TEXT, url TEXT, media_key BLOB, file_sha256 BLOB, file_enc_sha256 BLOB,
    file_length INTEGER, deleted_at TIMESTAMP, quoted_message_id TEXT,
    PRIMARY KEY (id, chat_jid), FOREIGN KEY (chat_jid) REFERENCES chats(jid));
CREATE INDEX IF NOT EXISTS idx_messages_chat_jid ON messages(chat_jid);
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("db", type=Path)
    ap.add_argument("--day", required=True, choices=["1", "2"])
    args = ap.parse_args()
    data = json.loads((Path(__file__).parent / "chat.json").read_text(encoding="utf-8"))

    conn = sqlite3.connect(args.db)
    conn.executescript(SCHEMA)
    for jid, name in data["chats"].items():
        conn.execute("INSERT OR IGNORE INTO chats (jid, name) VALUES (?, ?)", (jid, name))
    for mid, jid, sender, from_me, ts, content, *media in data["days"][args.day]:
        conn.execute(
            "INSERT OR IGNORE INTO messages (id, chat_jid, sender, content, timestamp, is_from_me, media_type)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (mid, jid, sender, content, ts, from_me, media[0] if media else None),
        )
        conn.execute("UPDATE chats SET last_message_time = ? WHERE jid = ?", (ts, jid))
    conn.commit()
    conn.close()


if __name__ == "__main__":
    main()
