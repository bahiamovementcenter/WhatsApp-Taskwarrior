"""wtw: read allowlisted WhatsApp chats and keep a Taskwarrior list in step.

wtw chats                       list chats, to build the allowlist
wtw tasks                       list the tasks wtw manages
wtw pull -o batch.json          read new messages (changes nothing)
wtw apply plan.json batch.json  show what would change (dry run)
wtw apply ... --apply           back up Taskwarrior, write, advance cursors
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from . import config as config_mod
from . import whatsapp
from .plan import PlanError, build_changes
from .taskwarrior import TaskWarrior


def _cursors_path(cfg: config_mod.Config) -> Path:
    return cfg.state_dir / "cursors.json"


def _load_cursors(cfg: config_mod.Config) -> dict[str, str]:
    p = _cursors_path(cfg)
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def _write_json_atomic(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def _taskwarrior(cfg: config_mod.Config) -> TaskWarrior:
    if cfg.taskdata is not None:
        cfg.taskdata.mkdir(parents=True, exist_ok=True)
    return TaskWarrior(cfg.taskdata)


def cmd_chats(args: argparse.Namespace) -> int:
    db = Path(args.db) if args.db else config_mod.load(args.config).messages_db
    for chat in whatsapp.list_chats(db):
        if args.groups and not chat.is_group:
            continue
        print(f"{chat.jid}\t{chat.name or ''}\t{chat.last_message_time or ''}")
    return 0


def cmd_tasks(args: argparse.Namespace) -> int:
    cfg = config_mod.load(args.config)
    for key, t in sorted(_taskwarrior(cfg).owned_tasks().items()):
        if args.all or t.get("status") == "pending":
            print(f"{key}\t{t.get('status')}\t{t.get('due', '')}\t{t.get('description')}")
    return 0


def cmd_pull(args: argparse.Namespace) -> int:
    cfg = config_mod.load(args.config)
    if not cfg.chats:
        print("no chats in the allowlist ([whatsapp].chats); nothing to read", file=sys.stderr)
    cursors = _load_cursors(cfg)
    msgs = whatsapp.fetch_messages(cfg.messages_db, list(cfg.chats), cursors, cfg.max_messages)
    new_cursors = dict(cursors)
    for m in msgs:
        if m.timestamp > new_cursors.get(m.chat_jid, ""):
            new_cursors[m.chat_jid] = m.timestamp
    batch = {
        "version": 1,
        "created": datetime.now(UTC).isoformat(timespec="seconds"),
        "chats": cfg.chats,
        "cursors": {k: v for k, v in new_cursors.items() if k in cfg.chats},
        "truncated": len(msgs) >= cfg.max_messages,
        "messages": [m.to_dict() for m in msgs],
    }
    if args.output == "-":
        json.dump(batch, sys.stdout, indent=2, ensure_ascii=False)
        print()
    else:
        _write_json_atomic(Path(args.output), batch)
        print(f"read {len(msgs)} messages from {len(cfg.chats)} chats -> {args.output}", file=sys.stderr)
    return 0


def cmd_apply(args: argparse.Namespace) -> int:
    cfg = config_mod.load(args.config)
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    batch = json.loads(Path(args.batch).read_text(encoding="utf-8"))
    cited = sorted(
        {
            (str(o["source"].get("chat_jid")), str(o["source"].get("message_id")))
            for o in plan.get("operations", [])
            if isinstance(o, dict) and isinstance(o.get("source"), dict)
        }
    )
    missing = set(cited) - whatsapp.existing_message_keys(cfg.messages_db, cited)
    if missing:
        print("plan rejected, nothing written: cited messages are not in messages.db:", file=sys.stderr)
        for jid, mid in sorted(missing):
            print(f"  - {jid}/{mid}", file=sys.stderr)
        return 2
    tw = _taskwarrior(cfg)
    try:
        changes = build_changes(plan, batch, cfg.chats, tw.owned_tasks(), cfg.project)
    except PlanError as e:
        print("plan rejected, nothing written:", file=sys.stderr)
        for p in e.problems:
            print(f"  - {p}", file=sys.stderr)
        return 2

    for t in changes.new:
        print(f"+ add      {t['description']}  [{t['wa_chat']}]")
    for t in changes.updated:
        print(f"~ update   {t['description']}  -> {t['status']}")
    for s in changes.skipped:
        print(f"= skip     {s}")

    if not args.apply:
        print("\ndry run: nothing written. Re-run with --apply to write.")
        return 0

    if not changes.empty:
        backup = tw.backup(cfg.state_dir / "backups")
        print(f"backed up Taskwarrior data to {backup}" if backup else "no existing Taskwarrior data to back up")
        tw.import_tasks(changes.to_import())
    log = cfg.state_dir / "log.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as fh:
        entry = {"at": datetime.now(UTC).isoformat(timespec="seconds"), "plan": args.plan, "batch": args.batch}
        entry |= {"new": len(changes.new), "updated": len(changes.updated), "skipped": changes.skipped}
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # Only move cursors forward, and only for allowlisted chats.
    cursors = _load_cursors(cfg)
    for jid, ts in batch.get("cursors", {}).items():
        if jid in cfg.chats and ts > cursors.get(jid, ""):
            cursors[jid] = ts
    _write_json_atomic(_cursors_path(cfg), cursors)
    print(f"wrote {len(changes.new)} new and {len(changes.updated)} updated tasks; cursors advanced")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="wtw", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("-c", "--config", type=Path, default=config_mod.DEFAULT_CONFIG)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("chats", help="list chats in messages.db")
    p.add_argument("--db", help="messages.db path (default: from config)")
    p.add_argument("--groups", action="store_true", help="only group chats")
    p.set_defaults(func=cmd_chats)

    p = sub.add_parser("tasks", help="list tasks this tool manages (read only)")
    p.add_argument("--all", action="store_true", help="include completed tasks")
    p.set_defaults(func=cmd_tasks)

    p = sub.add_parser("pull", help="read new messages from allowlisted chats")
    p.add_argument("-o", "--output", default="-", help="batch file (default: stdout)")
    p.set_defaults(func=cmd_pull)

    p = sub.add_parser("apply", help="check a plan against a batch; write with --apply")
    p.add_argument("plan")
    p.add_argument("batch")
    p.add_argument("--apply", action="store_true", help="actually write to Taskwarrior")
    p.set_defaults(func=cmd_apply)

    args = ap.parse_args(argv)
    try:
        return args.func(args)
    except (config_mod.ConfigError, FileNotFoundError, RuntimeError, json.JSONDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
