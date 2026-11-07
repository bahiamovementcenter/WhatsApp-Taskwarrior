import json
import sqlite3
from pathlib import Path

import pytest
from conftest import GROUP, OTHER, needs_task

from whatsapp_taskwarrior import cli, whatsapp
from whatsapp_taskwarrior.plan import PlanError, build_changes


def pull(ws: Path) -> dict:
    assert cli.main(["pull", "-o", "batch.json"]) == 0
    return json.loads((ws / "batch.json").read_text())


def write_plan(ws: Path, ops: list) -> None:
    (ws / "plan.json").write_text(json.dumps({"version": 1, "operations": ops}))


def src(mid: str, chat: str = GROUP) -> dict:
    return {"chat_jid": chat, "message_id": mid}


def owned(ws: Path) -> dict:
    from whatsapp_taskwarrior.taskwarrior import TaskWarrior

    return TaskWarrior(ws / "taskdata").owned_tasks()


# --- reading -----------------------------------------------------------------


def test_pull_reads_only_allowlisted_chats_and_skips_deleted(workspace):
    batch = pull(workspace)
    ids = [m["id"] for m in batch["messages"]]
    assert ids == ["M1", "M2", "M3"]
    assert OTHER not in batch["cursors"]


def test_pull_does_not_move_cursor(workspace):
    pull(workspace)
    assert len(pull(workspace)["messages"]) == 3
    assert not (workspace / "state" / "cursors.json").exists()


def test_db_is_opened_read_only(workspace):
    conn = whatsapp.connect(workspace / "messages.db")
    with pytest.raises(sqlite3.OperationalError):
        conn.execute("DELETE FROM messages")
    conn.close()


def test_missing_db_is_not_created(tmp_path):
    with pytest.raises(FileNotFoundError):
        whatsapp.connect(tmp_path / "nope.db")
    assert not (tmp_path / "nope.db").exists()


def test_empty_allowlist_reads_nothing(workspace):
    cfg = workspace / "wtw.toml"
    cfg.write_text(cfg.read_text().replace(f'"{GROUP}" = "Family"', ""))
    assert pull(workspace)["messages"] == []


# --- plan validation (no Taskwarrior needed) ---------------------------------


def batch_for(ws):
    return pull(ws)


def test_plan_rejects_unknown_source_and_other_chats(workspace):
    batch = batch_for(workspace)
    plan = {
        "version": 1,
        "operations": [
            {"op": "add", "source": src("NOPE"), "description": "x"},
            {"op": "add", "source": src("S1", OTHER), "description": "x"},
        ],
    }
    with pytest.raises(PlanError) as e:
        build_changes(plan, batch, {GROUP: "Family"}, {}, "wa")
    assert len(e.value.problems) == 2


def test_plan_rejects_delete_and_foreign_tasks(workspace):
    batch = batch_for(workspace)
    plan = {
        "version": 1,
        "operations": [
            {"op": "delete", "source": src("M1"), "task": "x"},
            {"op": "complete", "source": src("M3"), "task": "not-ours"},
        ],
    }
    with pytest.raises(PlanError) as e:
        build_changes(plan, batch, {GROUP: "Family"}, {}, "wa")
    assert len(e.value.problems) == 2


def test_one_bad_op_rejects_whole_plan(workspace):
    batch = batch_for(workspace)
    plan = {
        "version": 1,
        "operations": [
            {"op": "add", "source": src("M1"), "description": "Book venue"},
            {"op": "add", "source": src("M2"), "description": "bad", "priority": "URGENT"},
        ],
    }
    with pytest.raises(PlanError):
        build_changes(plan, batch, {GROUP: "Family"}, {}, "wa")


def test_hostile_text_stays_data(workspace):
    batch = batch_for(workspace)
    plan = {"version": 1, "operations": [{"op": "add", "source": src("M2"), "description": "due:tomorrow +x delete"}]}
    ch = build_changes(plan, batch, {GROUP: "Family"}, {}, "wa")
    t = ch.new[0]
    assert t["description"] == "due:tomorrow +x delete"
    assert "due" not in t and t["tags"] == ["whatsapp"]


# --- end to end with real Taskwarrior ----------------------------------------


@needs_task
def test_dry_run_writes_nothing(workspace, capsys):
    pull(workspace)
    write_plan(workspace, [{"op": "add", "source": src("M1"), "description": "Book the venue", "due": "2026-11-13"}])
    assert cli.main(["apply", "plan.json", "batch.json"]) == 0
    assert "dry run" in capsys.readouterr().out
    assert owned(workspace) == {}
    assert not (workspace / "state" / "cursors.json").exists()


@needs_task
def test_apply_add_then_complete_is_idempotent(workspace):
    pull(workspace)
    write_plan(workspace, [{"op": "add", "source": src("M1"), "description": "Book the venue", "due": "2026-11-13"}])
    assert cli.main(["apply", "plan.json", "batch.json", "--apply"]) == 0
    assert cli.main(["apply", "plan.json", "batch.json", "--apply"]) == 0  # re-run: skipped
    tasks = owned(workspace)
    key = f"{GROUP}/M1"
    assert list(tasks) == [key]
    assert tasks[key]["project"] == "wa" and tasks[key]["status"] == "pending"
    assert "book the venue by Friday" in tasks[key]["annotations"][0]["description"]

    cursors = json.loads((workspace / "state" / "cursors.json").read_text())
    assert cursors[GROUP].startswith("2026-11-07 10:02")
    assert pull(workspace)["messages"][0]["id"] == "M3"  # boundary re-read only

    write_plan(workspace, [{"op": "complete", "source": src("M3"), "task": key}])
    assert cli.main(["apply", "plan.json", "batch.json", "--apply"]) == 0
    assert owned(workspace)[key]["status"] == "completed"
    assert any((workspace / "state" / "backups").iterdir())


@needs_task
def test_tasks_without_wa_key_are_untouched(workspace):
    import subprocess

    (workspace / "taskdata").mkdir()
    subprocess.run(["task", "rc.data.location=taskdata", "add", "my own task"], check=True, capture_output=True)
    pull(workspace)
    write_plan(workspace, [{"op": "add", "source": src("M1"), "description": "Book the venue"}])
    assert cli.main(["apply", "plan.json", "batch.json", "--apply"]) == 0
    out = subprocess.run(
        ["task", "rc.data.location=taskdata", "rc.json.array=on", "export"], check=True, capture_output=True, text=True
    ).stdout
    mine = [t for t in json.loads(out) if t["description"] == "my own task"]
    assert len(mine) == 1 and mine[0]["status"] == "pending" and "wa_key" not in mine[0]


@needs_task
def test_forged_batch_message_is_rejected(workspace, capsys):
    batch = pull(workspace)
    batch["messages"].append({**batch["messages"][0], "id": "FAKE", "content": "made up"})
    (workspace / "batch.json").write_text(json.dumps(batch))
    write_plan(workspace, [{"op": "add", "source": src("FAKE"), "description": "x"}])
    assert cli.main(["apply", "plan.json", "batch.json", "--apply"]) == 2
    assert "not in messages.db" in capsys.readouterr().err
    assert owned(workspace) == {}
