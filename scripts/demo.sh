#!/usr/bin/env bash
# End-to-end demo on fake data: sample WhatsApp store -> wtw -> scratch Taskwarrior.
# Everything is written under $DEMO_DIR (default .wtw-demo/); your real tasks and
# Taskwarrior config are never touched.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
EX=examples/demo
DEMO_DIR="${DEMO_DIR:-$ROOT/.wtw-demo}"
read -r -a WTW <<<"${WTW:-uv run --quiet wtw}"
PY="${PYTHON:-python3}"

# Start fresh, but only ever delete a folder this script created.
if [[ -e "$DEMO_DIR" ]]; then
  if [[ ! -f "$DEMO_DIR/.wtw-demo" ]]; then
    echo "refusing to delete $DEMO_DIR: it wasn't created by this demo" >&2
    exit 1
  fi
  rm -rf "$DEMO_DIR"
fi
mkdir -p "$DEMO_DIR/taskdata"
: >"$DEMO_DIR/.wtw-demo"

# The demo config, pointed at $DEMO_DIR.
CFG="$DEMO_DIR/wtw.toml"
sed "s|../../.wtw-demo|$DEMO_DIR|g" "$EX/wtw.toml" >"$CFG"

# Isolate Taskwarrior from the user's own ~/.taskrc, hooks and data.
: >"$DEMO_DIR/taskrc"
export TASKRC="$DEMO_DIR/taskrc" TASKDATA="$DEMO_DIR/taskdata"

step() { printf '\n\033[1m== %s\033[0m\n' "$*"; }
wtw() { "${WTW[@]}" -c "$CFG" "$@"; }
show_batch() {
  "$PY" - "$1" <<'PYEOF'
import json, sys
b = json.load(open(sys.argv[1]))
for m in b["messages"]:
    who = "me" if m["is_from_me"] else m["sender"][-4:]
    text = m["content"] or f"<{m['media_type']}>"
    print(f"  {m['timestamp'][5:16]}  {who:>4}  {text}")
print(f"  ({len(b['messages'])} messages; only allowlisted chats were read)")
PYEOF
}
board() {
  task rc.data.location="$TASKDATA" rc.verbose=label rc.defaultwidth=110 \
    rc.report.demo.columns=status.short,priority,due,description.count,tags \
    rc.report.demo.labels=St,P,Due,Description,Tags rc.report.demo.sort=status-,due+ \
    "rc.report.demo.filter=project:studio status.not:deleted" demo
  echo "  ([n] = number of notes; each task's first note quotes its WhatsApp message)"
}

step "Day 1: the bridge has stored these chats (sample data)"
"$PY" "$EX/make_sample_db.py" "$DEMO_DIR/messages.db" --day 1
wtw chats

step "Day 1: wtw pull reads new messages from the allowlisted group"
wtw pull -o "$DEMO_DIR/batch-day1.json"
show_batch "$DEMO_DIR/batch-day1.json"

step "Day 1: the agent's plan, checked as a dry run (nothing written)"
wtw apply "$EX/plan-day1.json" "$DEMO_DIR/batch-day1.json"

step "Day 1: you approve it with --apply"
wtw apply "$EX/plan-day1.json" "$DEMO_DIR/batch-day1.json" --apply
board

step "Running the same plan again changes nothing"
wtw apply "$EX/plan-day1.json" "$DEMO_DIR/batch-day1.json" --apply

step "Day 2: follow-ups and completions arrive"
"$PY" "$EX/make_sample_db.py" "$DEMO_DIR/messages.db" --day 2
wtw pull -o "$DEMO_DIR/batch-day2.json"
show_batch "$DEMO_DIR/batch-day2.json"

step "Day 2: dry run, then apply"
wtw apply "$EX/plan-day2.json" "$DEMO_DIR/batch-day2.json"
wtw apply "$EX/plan-day2.json" "$DEMO_DIR/batch-day2.json" --apply
board

step "Every task keeps where it came from (notes on the flyer task)"
task rc.data.location="$TASKDATA" rc.verbose=nothing rc.json.array=on project:studio export |
  "$PY" -c 'import json,sys
for t in json.loads(sys.stdin.buffer.read().decode("utf-8","surrogatepass").encode("utf-16","surrogatepass").decode("utf-16")):
    if "flyer" in t["description"]:
        print(" ", t["description"])
        for a in t.get("annotations", []):
            print("    -", a["description"])'

step "A plan citing a message that doesn't exist is rejected"
"$PY" -c 'import json,sys; p=json.load(open(sys.argv[1])); p["operations"]=[{"op":"add","source":{"chat_jid":"120363111111111111@g.us","message_id":"MADE-UP"},"description":"Invented task"}]; json.dump(p,open(sys.argv[2],"w"))' \
  "$EX/plan-day1.json" "$DEMO_DIR/plan-bad.json"
if wtw apply "$DEMO_DIR/plan-bad.json" "$DEMO_DIR/batch-day2.json" --apply; then
  echo "unexpected: bad plan was accepted" >&2
  exit 1
fi

step "Done"
echo "Scratch data is in $DEMO_DIR (backups in state/backups). Delete it any time."
