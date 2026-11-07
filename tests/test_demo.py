import json
import os
import subprocess
import sys
from pathlib import Path

from conftest import needs_task

from whatsapp_taskwarrior.taskwarrior import decode_output

ROOT = Path(__file__).resolve().parent.parent


@needs_task
def test_demo_runs_end_to_end(tmp_path):
    """scripts/demo.sh (what `just demo` runs) works and ends with the expected tasks."""
    demo = tmp_path / "demo"
    env = os.environ | {
        "DEMO_DIR": str(demo),
        "WTW": f"{sys.executable} -m whatsapp_taskwarrior.cli",
        "PYTHON": sys.executable,
    }
    proc = subprocess.run(["bash", str(ROOT / "scripts" / "demo.sh")], env=env, capture_output=True, check=False)
    out = decode_output(proc.stdout) + decode_output(proc.stderr)
    assert proc.returncode == 0, out
    assert "plan rejected" in out  # the forged plan step

    raw = subprocess.run(
        ["task", f"rc.data.location={demo / 'taskdata'}", "rc.json.array=on", "project:studio", "export"],
        env=env | {"TASKRC": str(demo / "taskrc")},
        capture_output=True,
        check=True,
    ).stdout
    tasks = {t["description"]: t for t in json.loads(decode_output(raw))}
    assert len(tasks) == 6
    assert tasks["Order 12 new yoga mats"]["status"] == "completed"
    assert tasks["Send the payroll numbers to the accountant"]["status"] == "completed"
    assert tasks["Buy blue and white balloons for the open house"]["status"] == "pending"
    assert len(tasks["Call the technician about the AC noise in room 2"]["annotations"]) == 2
    assert not any("bread" in t["description"].lower() for t in tasks.values())  # Family chat never read
