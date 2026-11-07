"""Load and validate wtw.toml.

Nothing is read from a chat unless its JID is listed in ``[whatsapp].chats``:
an empty allowlist means the tool does nothing.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

DEFAULT_CONFIG = Path("wtw.toml")


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class Config:
    messages_db: Path
    chats: dict[str, str]  # jid -> label
    state_dir: Path
    project: str = "whatsapp"
    taskdata: Path | None = None  # None = Taskwarrior's own default
    max_messages: int = 500


def load(path: Path = DEFAULT_CONFIG) -> Config:
    if not path.is_file():
        raise ConfigError(f"config not found: {path} (copy wtw.example.toml to {path})")
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    base = path.resolve().parent

    def resolve(p: str) -> Path:
        q = Path(p).expanduser()
        return q if q.is_absolute() else (base / q)

    wa = raw.get("whatsapp", {})
    tw = raw.get("taskwarrior", {})
    if "messages_db" not in wa:
        raise ConfigError("[whatsapp].messages_db is required")

    chats = wa.get("chats", {})
    if not isinstance(chats, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in chats.items()):
        raise ConfigError('[whatsapp].chats must be a table of "jid" = "label" strings')
    for jid in chats:
        if "@" not in jid:
            raise ConfigError(f"not a WhatsApp JID: {jid!r} (run `wtw chats` to list them)")

    project = tw.get("project", "whatsapp")
    if not project or any(c.isspace() for c in project):
        raise ConfigError("[taskwarrior].project must be a non-empty word")

    return Config(
        messages_db=resolve(wa["messages_db"]),
        chats=dict(chats),
        state_dir=resolve(raw.get("state_dir", ".wtw")),
        project=project,
        taskdata=resolve(tw["data_location"]) if tw.get("data_location") else None,
        max_messages=int(wa.get("max_messages", 500)),
    )
