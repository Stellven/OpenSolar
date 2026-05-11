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

if grep -q 'phase=graph_dispatch_active but task_graph missing; refuse parent builder dispatch' "$COORD"; then
  ok "missing graph refuses parent builder dispatch"
else
  fail "missing graph guard absent"
fi

if python3 - "$COORD" <<'PY'
import sys
p=sys.argv[1]
s=open(p, encoding="utf-8").read()
graph=s.index('phase=graph_dispatch_active but task_graph missing; refuse parent builder dispatch')
parent=s.index('Sprint 进入 active 且 planner plan 已完成')
assert graph < parent
PY
then
  ok "graph guard appears before generic parent builder dispatch"
else
  fail "graph guard comes after parent builder dispatch"
fi

echo ""
echo "=== Graph Active Guard: PASS=$PASS FAIL=$FAIL ==="
[[ $FAIL -eq 0 ]]

