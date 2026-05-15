#!/usr/bin/env bash
# Verify mandatory Definition of Done constraints are wired into Solar and Harness prompts.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
HARNESS_DIR="$REPO_DIR/harness"

PASS=0
FAIL=0

ok() { echo "PASS: $*"; PASS=$((PASS+1)); }
fail() { echo "FAIL: $*" >&2; FAIL=$((FAIL+1)); }
contains() {
  local label="$1" file="$2" needle="$3"
  if grep -q "$needle" "$file"; then
    ok "$label"
  else
    fail "$label"
  fi
}

contains "Solar CLAUDE.md has system DoD" "$REPO_DIR/CLAUDE.md" "DEFINITION OF DONE"
contains "Solar CLAUDE.md forbids success without evidence" "$REPO_DIR/CLAUDE.md" "没有证据，不许报喜"
contains "Harness runtime prompt has DoD" "$HARNESS_DIR/lib/persona-config.sh" "Definition of Done · Mandatory Completion Gate"
contains "Coordinator dispatch template has DoD" "$HARNESS_DIR/coordinator.sh" "DEFINITION OF DONE"
contains "DAG dispatcher has DoD constant" "$HARNESS_DIR/lib/graph_node_dispatcher.py" "DEFINITION_OF_DONE_POLICY"
contains "DAG dispatcher requires structured closeout" "$HARNESS_DIR/lib/graph_node_dispatcher.py" "已完成 · 已验证 · 未验证 · 风险 · 后续待办"

echo "PROBES_PASSED=$PASS PROBES_FAILED=$FAIL"
[[ "$FAIL" -eq 0 ]]
