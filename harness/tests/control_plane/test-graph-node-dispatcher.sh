#!/usr/bin/env bash
# Graph node dispatcher regression tests — DAG queue item -> explicit node dispatch
set -euo pipefail

HARNESS_DIR_REAL="${HARNESS_DIR:-$HOME/.solar/harness}"
BIN="$HARNESS_DIR_REAL/solar-harness.sh"
PASS=0
FAIL=0

ok()   { echo "  PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "  FAIL: $1"; FAIL=$((FAIL+1)); }
check() {
  local label="$1" actual="$2" expected="$3"
  if [[ "$actual" == *"$expected"* ]]; then ok "$label"; else fail "$label (got: $actual)"; fi
}

TMPDIR_TEST=$(mktemp -d)
trap 'rm -rf "$TMPDIR_TEST"' EXIT
mkdir -p "$TMPDIR_TEST/lib" "$TMPDIR_TEST/sprints" "$TMPDIR_TEST/run/queue" "$TMPDIR_TEST/run/pane-leases"

cp "$HARNESS_DIR_REAL/lib/graph_scheduler.py" "$TMPDIR_TEST/lib/graph_scheduler.py"
cp "$HARNESS_DIR_REAL/lib/graph_node_dispatcher.py" "$TMPDIR_TEST/lib/graph_node_dispatcher.py"
cp "$HARNESS_DIR_REAL/lib/task_queue.py" "$TMPDIR_TEST/lib/task_queue.py"
cp "$HARNESS_DIR_REAL/lib/pane_lease.py" "$TMPDIR_TEST/lib/pane_lease.py"

SID="sprint-test-graph-node-dispatch"
GRAPH="$TMPDIR_TEST/sprints/${SID}.task_graph.json"
cat > "$TMPDIR_TEST/sprints/${SID}.contract.md" <<'EOF'
# Contract
EOF
cat > "$GRAPH" <<JSON
{
  "sprint_id": "${SID}",
  "required_gates": ["G0", "G1", "G2"],
  "nodes": [
    {
      "id": "S0",
      "goal": "foundation",
      "depends_on": [],
      "write_scope": ["/foundation"],
      "read_scope": ["/"],
      "required_skills": ["python"],
      "preferred_model": "sonnet",
      "gate": "G0",
      "acceptance": ["foundation passed"],
      "estimated_cost": 1,
      "status": "passed"
    },
    {
      "id": "S1",
      "goal": "implement node S1 only",
      "depends_on": ["S0"],
      "write_scope": ["/a"],
      "read_scope": ["/"],
      "required_skills": ["python"],
      "preferred_model": "sonnet",
      "gate": "G1",
      "acceptance": ["S1 passed"],
      "estimated_cost": 1
    },
    {
      "id": "S2",
      "goal": "implement node S2 only",
      "depends_on": ["S0"],
      "write_scope": ["/b"],
      "read_scope": ["/"],
      "required_skills": ["python"],
      "preferred_model": "sonnet",
      "gate": "G2",
      "acceptance": ["S2 passed"],
      "estimated_cost": 1
    },
    {
      "id": "S3",
      "goal": "join after S1/S2",
      "depends_on": ["S1", "S2"],
      "write_scope": ["/c"],
      "read_scope": ["/"],
      "required_skills": ["python"],
      "preferred_model": "sonnet",
      "gate": "G3",
      "acceptance": ["S3 passed"],
      "estimated_cost": 1
    }
  ],
  "node_results": {
    "S0": {"status": "passed", "updated_at": "2026-05-09T00:00:00Z"}
  },
  "gate_results": {
    "G0": {"status": "passed", "node": "S0", "updated_at": "2026-05-09T00:00:00Z"}
  }
}
JSON

echo "T1: py_compile"
python3 -m py_compile "$TMPDIR_TEST/lib/graph_node_dispatcher.py" "$TMPDIR_TEST/lib/graph_scheduler.py" "$TMPDIR_TEST/lib/task_queue.py" \
  && ok "modules compile" || fail "compile failed"

echo "T2: dispatch-ready dry-run creates explicit node dispatch files"
OUT=$(HARNESS_DIR="$TMPDIR_TEST" SOLAR_HARNESS_SESSION="solar-harness-test" python3 "$TMPDIR_TEST/lib/graph_node_dispatcher.py" dispatch-ready --graph "$GRAPH" --dry-run 2>/dev/null)
check "dispatch-ready ok" "$OUT" '"ok": true'
check "S1 drained" "$OUT" '"node": "S1"'
check "S2 drained" "$OUT" '"node": "S2"'
if [[ "$OUT" != *'"node": "S3"'* ]]; then ok "S3 not dispatched before join"; else fail "S3 dispatched too early"; fi

S1_DISPATCH="$TMPDIR_TEST/sprints/${SID}.S1-dispatch.md"
S2_DISPATCH="$TMPDIR_TEST/sprints/${SID}.S2-dispatch.md"
[[ -s "$S1_DISPATCH" ]] && ok "S1 dispatch file exists" || fail "S1 dispatch file missing"
[[ -s "$S2_DISPATCH" ]] && ok "S2 dispatch file exists" || fail "S2 dispatch file missing"
S1_TEXT=$(cat "$S1_DISPATCH")
check "dispatch text has node id" "$S1_TEXT" "Node: \`S1\`"
check "dispatch text has write scope" "$S1_TEXT" "\`/a\`"
check "dispatch text forbids parent pass" "$S1_TEXT" "不要把 parent sprint 标成 passed"

echo "T3: queue consumed and graph status updated"
OUT=$(HARNESS_DIR="$TMPDIR_TEST" python3 "$TMPDIR_TEST/lib/task_queue.py" depth --sprint "$SID" 2>/dev/null)
check "queue empty" "$OUT" '"depth": 0'
GRAPH_TEXT=$(cat "$GRAPH")
check "S1 dispatched in graph" "$GRAPH_TEXT" '"status": "dispatched"'
check "S2 dispatched in graph" "$GRAPH_TEXT" '"status": "dispatched"'
if [[ "$GRAPH_TEXT" != *'"id": "S3"'*'"status": "dispatched"'* ]]; then ok "S3 not marked dispatched"; else fail "S3 marked dispatched too early"; fi

echo "T4: drain-queue dry-run consumes pre-enqueued graph node payload"
SID2="sprint-test-graph-node-drain"
GRAPH2="$TMPDIR_TEST/sprints/${SID2}.task_graph.json"
cp "$GRAPH" "$GRAPH2"
python3 - "$GRAPH2" "$SID2" <<'PY'
import json, sys
p, sid = sys.argv[1], sys.argv[2]
d = json.load(open(p))
d["sprint_id"] = sid
for n in d["nodes"]:
    n.pop("status", None)
    n.pop("assigned_to", None)
    n.pop("dispatch_id", None)
d["nodes"][0]["status"] = "passed"
d["node_results"] = {"S0": {"status": "passed", "updated_at": "2026-05-09T00:00:00Z"}}
json.dump(d, open(p, "w"), indent=2)
PY
PAYLOAD=$(python3 - "$GRAPH2" "$SID2" <<'PY'
import json, sys
graph, sid = sys.argv[1], sys.argv[2]
d = json.load(open(graph))
node = next(n for n in d["nodes"] if n["id"] == "S1")
print(json.dumps({
    "type": "graph_node",
    "graph": graph,
    "sprint_id": sid,
    "node": node,
    "assignment": {"node": "S1", "pane": "solar-harness-test:0.2"},
    "dispatch_id": "graph-test-drain-S1"
}))
PY
)
HARNESS_DIR="$TMPDIR_TEST" python3 "$TMPDIR_TEST/lib/task_queue.py" enqueue-node --sprint "$SID2" --node-id S1 --payload "$PAYLOAD" >/dev/null
OUT=$(HARNESS_DIR="$TMPDIR_TEST" python3 "$TMPDIR_TEST/lib/graph_node_dispatcher.py" drain-queue --sprint "$SID2" --dry-run 2>/dev/null)
check "drain-queue ok" "$OUT" '"ok": true'
check "drain-queue S1" "$OUT" '"node": "S1"'
[[ -s "$TMPDIR_TEST/sprints/${SID2}.S1-dispatch.md" ]] && ok "drain dispatch file exists" || fail "drain dispatch file missing"

echo "T5: solar-harness graph-dispatch subcommand routing"
OUT=$(bash "$BIN" graph-dispatch help 2>/dev/null || true)
check "graph-dispatch help" "$OUT" "Solar Graph Dispatch"
OUT=$(HARNESS_DIR="$TMPDIR_TEST" bash "$BIN" graph-dispatch drain-queue --sprint "$SID2" --dry-run 2>/dev/null || true)
check "graph-dispatch drain route" "$OUT" '"sprint_id": "sprint-test-graph-node-drain"'

echo ""
echo "=== Graph Node Dispatcher: PASS=$PASS FAIL=$FAIL ==="
[[ $FAIL -eq 0 ]] && exit 0 || exit 1
