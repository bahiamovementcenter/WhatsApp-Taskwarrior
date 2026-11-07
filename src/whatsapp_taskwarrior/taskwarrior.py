"""Talk to Taskwarrior only through ``task export`` and ``task import``.

Task text from WhatsApp is never put on the ``task`` command line, so message
content can't be read as a filter, a modifier (``due:``, ``+tag``) or a command
(``delete``). Every task this tool owns carries the ``wa_key`` UDA; tasks
without it are never changed. UDAs are declared with ``rc.`` overrides on each
call, so the user's ``.taskrc`` is not edited.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path

UDAS = {
    "wa_key": "WA message",
    "wa_chat": "WA chat",
}

Runner = Callable[[Sequence[str], str | None], str]


def _default_runner(args: Sequence[str], stdin: str | None) -> str:
    proc = subprocess.run(list(args), input=stdin, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"`{' '.join(args[:1] + args[-1:])}` failed ({proc.returncode}): {proc.stderr.strip()}")
    return proc.stdout


def tw_timestamp(dt: datetime | None = None) -> str:
    return (dt or datetime.now(UTC)).astimezone(UTC).strftime("%Y%m%dT%H%M%SZ")


class TaskWarrior:
    def __init__(self, data_location: Path | None = None, runner: Runner | None = None, binary: str = "task"):
        self.data_location = data_location
        self.run = runner or _default_runner
        self.binary = binary

    def _base(self) -> list[str]:
        args = [self.binary, "rc.confirmation=off", "rc.verbose=nothing", "rc.json.array=on"]
        if self.data_location is not None:
            args.append(f"rc.data.location={self.data_location}")
        for name, label in UDAS.items():
            args += [f"rc.uda.{name}.type=string", f"rc.uda.{name}.label={label}"]
        return args

    def owned_tasks(self) -> dict[str, dict]:
        """All tasks (any status) that carry a wa_key, keyed by it."""
        out = self.run([*self._base(), "wa_key.any:", "export"], None)
        tasks = json.loads(out or "[]")
        return {t["wa_key"]: t for t in tasks if t.get("wa_key")}

    def resolved_data_location(self) -> Path:
        if self.data_location is not None:
            return self.data_location
        out = self.run([*self._base(), "_get", "rc.data.location"], None).strip()
        return Path(out).expanduser()

    def import_tasks(self, tasks: list[dict]) -> None:
        if not tasks:
            return
        for t in tasks:
            if not t.get("wa_key"):
                raise ValueError("refusing to import a task without wa_key")
        self.run([*self._base(), "import", "-"], json.dumps(tasks))

    def backup(self, dest_root: Path) -> Path | None:
        """Copy the whole data directory; None if Taskwarrior has no data yet."""
        src = self.resolved_data_location()
        if not src.is_dir():
            return None
        dest = dest_root / datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
        shutil.copytree(src, dest, dirs_exist_ok=False)  # never overwrite an earlier backup
        return dest
