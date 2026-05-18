#!/usr/bin/env bash
# Regression: active DAG parents must be driven through graph-dispatch, not the
# generic parent builder dispatch path.
set -euo pipefail

HARNESS_DIR_REAL="${HARNESS_DIR:-$HOME/.solar/harness}"
COORD="$HARNESS_DIR_REAL/coordinator.sh"

PASS=0
FAIL=0

ok() { echo "  PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "  FAIL: $1"; FAIL=$((FAIL+1)); }

echo "T1: coordinator syntax"
bash -n "$COORD" && ok "coordinator bash -n" || fail "coordinator bash -n"

echo "T2: graph_dispatch_active guarded before parent builder dispatch"
if grep -q '"$phase" == "graph_dispatch_active"' "$COORD"; then
  ok "graph_dispatch_active condition present"
else
  fail "graph_dispatch_active condition missing"
fi

if python3 - "$COORD" <<'PY'
import sys
p=sys.argv[1]
s=open(p, encoding="utf-8").read()
guard=s.index('if [[ "$phase" == "graph_dispatch_active" || "$phase" == "planning_complete" ]]; then')
missing=s.index('task_graph missing; refuse parent builder dispatch', guard)
planner=s.index('dispatch_to_planner "$sid" "gate_missing_task_graph"', missing)
blocked=s.index('"active_blocked_missing_task_graph"', planner)
returned=s.index('return 0', blocked)
parent=s.index('Sprint 进入 active → 建设者写实现计划')
assert guard < missing < planner < blocked < returned < parent
PY
then
  ok "missing graph refuses parent builder dispatch before generic parent builder dispatch"
else
  fail "missing graph guard absent or ordered after parent builder dispatch"
fi

echo ""
echo "=== Graph Active Guard: PASS=$PASS FAIL=$FAIL ==="
[[ $FAIL -eq 0 ]]
