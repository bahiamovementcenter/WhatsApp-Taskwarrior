"""Validate a task plan and turn it into Taskwarrior records.

A *batch* is what ``wtw pull`` read from WhatsApp. A *plan* is what the agent
(or a person) proposes to do about it. Every operation must cite a message
that is in the batch, from an allowlisted chat, so a plan can't invent sources
or touch chats that weren't read. Validation is all-or-nothing: one bad
operation rejects the whole plan before anything is written.

Allowed operations: ``add``, ``annotate``, ``complete``. There is no delete and
no free-form modify.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date, datetime

from .taskwarrior import tw_timestamp

MAX_DESCRIPTION = 300
MAX_TEXT = 1000
TAG_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,31}$")
PRIORITIES = {"H", "M", "L"}
OPS = {"add", "annotate", "complete"}


class PlanError(ValueError):
    def __init__(self, problems: list[str]):
        super().__init__("; ".join(problems))
        self.problems = problems


def wa_key(chat_jid: str, message_id: str) -> str:
    return f"{chat_jid}/{message_id}"


def _clean(text: object, limit: int, what: str, problems: list[str]) -> str:
    if not isinstance(text, str) or not text.strip():
        problems.append(f"{what} must be non-empty text")
        return ""
    one_line = " ".join(text.split())
    if len(one_line) > limit:
        problems.append(f"{what} is longer than {limit} characters")
    return one_line


def _due(value: object, problems: list[str], where: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        problems.append(f"{where}: due must be a string")
        return None
    try:
        if len(value) == 10:
            d = date.fromisoformat(value)
            dt = datetime(d.year, d.month, d.day).astimezone()  # local midnight
        else:
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is None:
                dt = dt.astimezone()
    except ValueError:
        problems.append(f"{where}: due {value!r} is not an ISO date")
        return None
    return tw_timestamp(dt)


@dataclass
class Changes:
    new: list[dict] = field(default_factory=list)
    updated: list[dict] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    @property
    def empty(self) -> bool:
        return not (self.new or self.updated)

    def to_import(self) -> list[dict]:
        return self.new + self.updated


def build_changes(
    plan: dict,
    batch: dict,
    allowed_chats: dict[str, str],
    owned: dict[str, dict],
    project: str,
) -> Changes:
    problems: list[str] = []
    if plan.get("version") != 1:
        problems.append("plan.version must be 1")
    ops = plan.get("operations")
    if not isinstance(ops, list):
        raise PlanError([*problems, "plan.operations must be a list"])

    messages = {wa_key(m["chat_jid"], m["id"]): m for m in batch.get("messages", [])}
    changes = Changes()
    touched: dict[str, dict] = {}  # wa_key -> working copy of an existing task
    now = tw_timestamp()

    for i, op in enumerate(ops):
        where = f"operations[{i}]"
        if not isinstance(op, dict) or op.get("op") not in OPS:
            problems.append(f"{where}: op must be one of {sorted(OPS)}")
            continue
        src = op.get("source") or {}
        key = wa_key(str(src.get("chat_jid", "")), str(src.get("message_id", "")))
        msg = messages.get(key)
        if msg is None:
            problems.append(f"{where}: source {key!r} is not a message in this batch")
            continue
        if msg["chat_jid"] not in allowed_chats:
            problems.append(f"{where}: chat {msg['chat_jid']!r} is not in the allowlist")
            continue
        label = allowed_chats[msg["chat_jid"]]
        quote = " ".join((msg.get("content") or f"<{msg.get('media_type') or 'empty'}>").split())[:200]
        provenance = f"WhatsApp {label} {msg['timestamp'][:16]}: {quote}"

        if op["op"] == "add":
            desc = _clean(op.get("description"), MAX_DESCRIPTION, f"{where}.description", problems)
            due = _due(op.get("due"), problems, where)
            prio = op.get("priority")
            if prio is not None and prio not in PRIORITIES:
                problems.append(f"{where}: priority must be H, M or L")
            tags = op.get("tags") or []
            if not isinstance(tags, list) or not all(isinstance(t, str) and TAG_RE.match(t) for t in tags):
                problems.append(f"{where}: tags must be simple words")
                tags = []
            if key in owned or any(t["wa_key"] == key for t in changes.new):
                changes.skipped.append(f"add {key}: task already exists")
                continue
            task = {
                "description": desc,
                "project": project,
                "tags": sorted({"whatsapp", *tags}),
                "status": "pending",
                "entry": now,
                "wa_key": key,
                "wa_chat": label,
                "annotations": [{"entry": now, "description": provenance}],
            }
            if due:
                task["due"] = due
            if prio:
                task["priority"] = prio
            changes.new.append(task)
            continue

        target = op.get("task")
        if not isinstance(target, str) or target not in owned:
            problems.append(f"{where}: task {target!r} is not a WhatsApp task this tool created")
            continue
        task = touched.get(target)
        if task is None:
            task = {k: v for k, v in owned[target].items() if k not in ("id", "urgency")}
            touched[target] = task

        if op["op"] == "annotate":
            text = _clean(op.get("text"), MAX_TEXT, f"{where}.text", problems)
            note = f"{text} [{provenance}]"
            if any(a.get("description") == note for a in task.get("annotations", [])):
                changes.skipped.append(f"annotate {target}: already noted")
                continue
            task.setdefault("annotations", []).append({"entry": now, "description": note})
        elif op["op"] == "complete":
            if task.get("status") != "pending":
                changes.skipped.append(f"complete {target}: status is {task.get('status')}")
                continue
            task["status"] = "completed"
            task["end"] = now
            task.setdefault("annotations", []).append({"entry": now, "description": f"Done per {provenance}"})
        task["modified"] = now
        if not any(t is task for t in changes.updated):
            changes.updated.append(task)

    if problems:
        raise PlanError(problems)
    return changes
