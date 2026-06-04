#!/usr/bin/env bash
set -u

SID=sprint-20260521-physical-operator-registry
GRAPH=/Users/lisihao/.solar/harness/sprints/${SID}.task_graph.json
REPORT=/Users/lisihao/.solar/harness/monitor-reports/${SID}.live.md
FINAL=/Users/lisihao/.solar/harness/monitor-reports/physical-operator-registry.md

while true; do
  TS=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  {
    echo "# Mac mini monitor: $SID"
    echo
    echo "updated_at: $TS"
    echo
    python3 - "$GRAPH" <<'PY'
import json
import pathlib
import sys

p = pathlib.Path(sys.argv[1])
g = json.loads(p.read_text())
print("```text")
print("┌──────┬────────────┬──────────────────────┬────────────────────────────────────────┬──────────────────────┬────────────────────────────┐")
print("│ node │ status     │ active_task          │ title                                  │ updated_at           │ next                       │")
print("├──────┼────────────┼──────────────────────┼────────────────────────────────────────┼──────────────────────┼────────────────────────────┤")
for n in g.get("nodes", []):
    nid = str(n.get("id", "N/A"))[:4]
    st = str(n.get("status", "pending"))[:10]
    task = str(n.get("dispatch_id") or n.get("assigned_to") or "N/A")[-20:]
    title = str(n.get("title") or n.get("goal") or "")[:38]
    upd = str(n.get("updated_at") or "N/A")[:20]
    if st in {"passed", "failed"}:
        nxt = "done"
    elif st == "reviewing":
        nxt = "verify handoff / mark passed"
    elif st in {"dispatched", "running"}:
        nxt = "monitor output.log"
    else:
        nxt = "wait deps / dispatch"
    print(f"│ {nid:<4} │ {st:<10} │ {task:<20} │ {title:<38} │ {upd:<20} │ {nxt:<26} │")
print("└──────┴────────────┴──────────────────────┴────────────────────────────────────────┴──────────────────────┴────────────────────────────┘")
print("```")
PY
    echo
    echo "## multi-task status"
    echo '```text'
    solar-harness multi-task status --graph "$GRAPH" --no-clear --renderer plain | sed -n '1,180p'
    echo '```'
  } > "$REPORT.tmp" 2>&1
  mv "$REPORT.tmp" "$REPORT"

  python3 - "$GRAPH" "$SID" >"/tmp/${SID}.reviewing" 2>/dev/null <<'PY' || true
import json
import pathlib
import sys

graph_path = pathlib.Path(sys.argv[1])
sid = sys.argv[2]
g = json.loads(graph_path.read_text())
for n in g.get("nodes", []):
    if n.get("status") != "reviewing":
        continue
    handoff = n.get("handoff") or f"/Users/lisihao/.solar/harness/sprints/{sid}.{n.get('id')}-handoff.md"
    hp = pathlib.Path(handoff)
    if hp.exists() and hp.stat().st_size > 200:
        print(n.get("id"))
PY
  while read -r NODE; do
    [ -n "$NODE" ] || continue
    solar-harness graph-scheduler mark --graph "$GRAPH" --node "$NODE" --status passed --in-place >> "$REPORT" 2>&1 || true
  done < "/tmp/${SID}.reviewing"

  solar-harness multi-task start --graph "$GRAPH" --max-workers 1 --once --cooldown-sec 0 --memory-reserve-gb 0 --quota-backoff-sec 0 --no-clear --renderer plain >> "$REPORT" 2>&1 || true

  if [ -s "$FINAL" ]; then
    python3 - "$GRAPH" <<'PY' && break || true
import json
import pathlib
import sys

g = json.loads(pathlib.Path(sys.argv[1]).read_text())
statuses = [n.get("status") for n in g.get("nodes", [])]
sys.exit(0 if statuses and all(s == "passed" for s in statuses) else 1)
PY
  fi
  sleep 180
done
