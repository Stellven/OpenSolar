#!/usr/bin/env bash
# Regression: `solar-harness multi-task` launches ready DAG nodes into an
# independent tmux worker pool without requiring extra four-pane sessions.
set -euo pipefail
cd "$(dirname "$0")/.."

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP"/{bin,config,lib,sprints,personas,templates,run/multi-task,work}

cp solar-harness.sh "$TMP/solar-harness.sh"
cp lib/run-state.sh "$TMP/lib/run-state.sh"
cp lib/events.sh "$TMP/lib/events.sh"
cp lib/graph_scheduler.py "$TMP/lib/graph_scheduler.py"
cp lib/intent_engine_adapter.py "$TMP/lib/intent_engine_adapter.py"
cp lib/multi_task_runner.py "$TMP/lib/multi_task_runner.py"
cp lib/gemini_adapter.py "$TMP/lib/gemini_adapter.py"
cp config/multi-task-profiles.json "$TMP/config/multi-task-profiles.json"
cp config/model-registry.json "$TMP/config/model-registry.json"
cp personas/builder.md "$TMP/personas/builder.md"
cp personas/planner.md "$TMP/personas/planner.md"

python3 - "$TMP/solar-harness.sh" "$TMP" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
tmp = sys.argv[2]
s = p.read_text()
s = s.replace('HARNESS_DIR="${HARNESS_DIR:-$HOME/.solar/harness}"', f'HARNESS_DIR="${{HARNESS_DIR:-{tmp}}}"', 1)
p.write_text(s)
PY
chmod +x "$TMP/solar-harness.sh"

cat > "$TMP/bin/tmux" <<'EOF'
#!/usr/bin/env bash
echo "$@" >> "$HARNESS_DIR/tmux-calls.log"
case "$1" in
  has-session)
    exit 1
    ;;
  new-session|new-window|kill-window|attach)
    exit 0
    ;;
  *)
    exit 0
    ;;
esac
EOF
chmod +x "$TMP/bin/tmux"

cat > "$TMP/bin/gemini" <<'EOF'
#!/usr/bin/env bash
echo "$@" >> "$HARNESS_DIR/gemini-calls.log"
exit 0
EOF
chmod +x "$TMP/bin/gemini"

graph="$TMP/sprints/sprint-20260520-multi-task.task_graph.json"
cat > "$graph" <<'JSON'
{
  "sprint_id": "sprint-20260520-multi-task",
  "nodes": [
    {
      "id": "A",
      "goal": "touch A",
      "target_role": "planner",
      "depends_on": [],
      "write_scope": ["work/a.txt"],
      "acceptance": ["A handoff exists"]
    },
    {
      "id": "B",
      "goal": "touch B",
      "depends_on": [],
      "write_scope": ["work/b.txt"],
      "acceptance": ["B handoff exists"]
    }
  ]
}
JSON

PATH="$TMP/bin:$PATH" HARNESS_DIR="$TMP" "$TMP/solar-harness.sh" multi-task start --graph "$graph" --max-workers 2 --cooldown-sec 0 --memory-reserve-gb 0 --once --no-clear >/tmp/solar-multi-task-test.out

status_count=$(find "$TMP/run/multi-task" -name status.json | wc -l | tr -d ' ')
[[ "$status_count" -eq 2 ]] || { echo "FAIL: expected two multi-task status files, got $status_count"; exit 1; }

grep -q "new-session" "$TMP/tmux-calls.log" || { echo "FAIL: tmux new-session not called"; exit 1; }
grep -q "Solar Harness Multi-Task" /tmp/solar-multi-task-test.out || { echo "FAIL: summary not rendered"; exit 1; }
find "$TMP/run/multi-task" -name runner.sh -print0 | xargs -0 -n1 bash -n

python3 - "$graph" <<'PY'
import json, sys
graph = json.load(open(sys.argv[1], encoding="utf-8"))
nodes = {n["id"]: n for n in graph["nodes"]}
for node_id in ("A", "B"):
    n = nodes[node_id]
    assert n.get("status") == "dispatched", (node_id, n)
    assert str(n.get("assigned_to", "")).startswith("multi-task:"), (node_id, n)
    assert str(n.get("dispatch_id", "")).startswith("mt-"), (node_id, n)
PY

planner_status=$(python3 - "$TMP/run/multi-task" <<'PY'
import json, sys
from pathlib import Path
for path in Path(sys.argv[1]).glob("*/status.json"):
    data = json.loads(path.read_text())
    if data.get("node_id") == "A":
        print(data.get("role"), data.get("profile"), data.get("backend"), data.get("model"))
PY
)
[[ "$planner_status" == "planner planner claude-cli sonnet" ]] || { echo "FAIL: planner profile routing wrong: $planner_status"; exit 1; }

PATH="$TMP/bin:$PATH" HARNESS_DIR="$TMP" "$TMP/solar-harness.sh" multi-task profiles | grep -q "gemini-builder" \
  || { echo "FAIL: profiles did not include gemini-builder"; exit 1; }
PATH="$TMP/bin:$PATH" HARNESS_DIR="$TMP" "$TMP/solar-harness.sh" multi-task foreground planner | grep -q "tmux attach -t solar-harness-multi-task:" \
  || { echo "FAIL: foreground selector did not resolve planner"; exit 1; }
PATH="$TMP/bin:$PATH" HARNESS_DIR="$TMP" python3 "$TMP/lib/gemini_adapter.py" doctor | grep -q '"cli"' \
  || { echo "FAIL: gemini adapter doctor missing cli section"; exit 1; }

graph2="$TMP/sprints/sprint-20260520-gemini.task_graph.json"
cat > "$graph2" <<'JSON'
{
  "sprint_id": "sprint-20260520-gemini",
  "nodes": [
    {
      "id": "G1",
      "goal": "gemini smoke",
      "depends_on": [],
      "write_scope": ["work/gemini.txt"],
      "preferred_model": "gemini",
      "acceptance": ["Gemini dispatch exists"]
    }
  ]
}
JSON
PATH="$TMP/bin:$PATH" HARNESS_DIR="$TMP" "$TMP/solar-harness.sh" multi-task start --graph "$graph2" --profile gemini-builder --max-workers 3 --cooldown-sec 0 --memory-reserve-gb 0 --once --no-clear >/tmp/solar-multi-task-gemini.out
gemini_runner=$(find "$TMP/run/multi-task" -path "*sprint-20260520-gemini*/runner.sh" -print | head -1)
[[ -n "$gemini_runner" ]] || { echo "FAIL: gemini runner missing"; exit 1; }
grep -q "gemini_adapter.py" "$gemini_runner" || { echo "FAIL: gemini runner does not use gemini adapter"; exit 1; }
grep -q '"backend": "gemini-cli"' "$(dirname "$gemini_runner")/status.json" || { echo "FAIL: gemini status backend missing"; exit 1; }

PATH="$TMP/bin:$PATH" HARNESS_DIR="$TMP" "$TMP/solar-harness.sh" multi-task status --graph "$graph" --no-clear | grep -q "sprint-20260520-multi-task" \
  || { echo "FAIL: status did not include graph"; exit 1; }

COLUMNS=80 LINES=20 PATH="$TMP/bin:$PATH" HARNESS_DIR="$TMP" "$TMP/solar-harness.sh" multi-task screen --graph "$graph" --command "显示状态" --no-clear >/tmp/solar-multi-task-screen.out
grep -q "自然语言指令" /tmp/solar-multi-task-screen.out \
  || { echo "FAIL: screen did not render input pane"; exit 1; }
screen_lines=$(wc -l < /tmp/solar-multi-task-screen.out | tr -d ' ')
[[ "$screen_lines" -le 20 ]] || { echo "FAIL: screen exceeded terminal height: $screen_lines"; exit 1; }
python3 - /tmp/solar-multi-task-screen.out <<'PY'
import sys, unicodedata
def width(s):
    n = 0
    for ch in s.rstrip("\n"):
        if unicodedata.combining(ch):
            continue
        n += 2 if unicodedata.east_asian_width(ch) in {"F", "W"} else 1
    return n
bad = [(i, width(line)) for i, line in enumerate(open(sys.argv[1], encoding="utf-8"), 1) if width(line) > 80]
if bad:
    raise SystemExit(f"screen exceeded terminal width: {bad[:3]}")
PY
grep -q '"action": "status"' "$TMP/run/multi-task/screen-commands.jsonl" \
  || { echo "FAIL: screen command was not logged through intent path"; exit 1; }

echo "PASS: multi-task entrypoint dispatches ready DAG nodes to tmux worker pool"
