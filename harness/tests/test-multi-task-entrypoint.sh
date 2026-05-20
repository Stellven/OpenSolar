#!/usr/bin/env bash
# Regression: `solar-harness multi-task` launches ready DAG nodes into an
# independent tmux worker pool without requiring extra four-pane sessions.
set -euo pipefail
cd "$(dirname "$0")/.."

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP"/{bin,lib,sprints,personas,templates,run/multi-task,work}

cp solar-harness.sh "$TMP/solar-harness.sh"
cp lib/run-state.sh "$TMP/lib/run-state.sh"
cp lib/events.sh "$TMP/lib/events.sh"
cp lib/graph_scheduler.py "$TMP/lib/graph_scheduler.py"
cp lib/multi_task_runner.py "$TMP/lib/multi_task_runner.py"

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

graph="$TMP/sprints/sprint-20260520-multi-task.task_graph.json"
cat > "$graph" <<'JSON'
{
  "sprint_id": "sprint-20260520-multi-task",
  "nodes": [
    {
      "id": "A",
      "goal": "touch A",
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

PATH="$TMP/bin:$PATH" HARNESS_DIR="$TMP" "$TMP/solar-harness.sh" multi-task status --graph "$graph" --no-clear | grep -q "sprint-20260520-multi-task" \
  || { echo "FAIL: status did not include graph"; exit 1; }

echo "PASS: multi-task entrypoint dispatches ready DAG nodes to tmux worker pool"
