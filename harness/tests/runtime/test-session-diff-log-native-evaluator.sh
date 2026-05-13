#!/usr/bin/env bash
# test-session-diff-log-native-evaluator.sh — session replay/diff/log-native eval
set -euo pipefail

HARNESS_DIR="${HOME}/.solar/harness"
LIB_DIR="${HARNESS_DIR}/lib"
SID_A="test-session-tools-pass-$$"
SID_B="test-session-tools-fail-$$"
TMP_HARNESS="$(mktemp -d)"
PASS=0
FAIL=0

cleanup() {
  rm -rf "${HARNESS_DIR}/sessions/${SID_A}" "${HARNESS_DIR}/sessions/${SID_B}" "$TMP_HARNESS"
}
trap cleanup EXIT

ok() { echo "  PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "  FAIL: $1"; FAIL=$((FAIL+1)); }
assert_contains() {
  local label="$1" haystack="$2" needle="$3"
  if [[ "$haystack" == *"$needle"* ]]; then ok "$label"; else fail "$label"; fi
}

export PYTHONPATH="${LIB_DIR}:${PYTHONPATH:-}"

python3 - <<PY
from session_log import SessionLog

sid_a = "${SID_A}"
log = SessionLog(sid_a)
log.append("command_issued", actor="coordinator", sprint_id=sid_a, activity_id="act-1", idempotency_key=sid_a+":cmd")
log.append("activity_started", actor="builder", sprint_id=sid_a, activity_id="act-1")
log.append("model_call_requested", actor="coordinator", sprint_id=sid_a, activity_id="dispatch-1", payload={"dispatch_id":"dispatch-1","pane":"solar-harness:0.2"})
log.append("model_call_succeeded", actor="builder", sprint_id=sid_a, activity_id="dispatch-1", payload={"dispatch_id":"dispatch-1","pane":"solar-harness:0.2","status":"accepted"})
log.append("activity_succeeded", actor="builder", sprint_id=sid_a, activity_id="act-1", idempotency_key=sid_a+":done")

sid_b = "${SID_B}"
log = SessionLog(sid_b)
log.append("command_issued", actor="coordinator", sprint_id=sid_b, activity_id="act-1", idempotency_key=sid_b+":cmd")
log.append("activity_started", actor="builder", sprint_id=sid_b, activity_id="act-1")
log.append("model_call_requested", actor="coordinator", sprint_id=sid_b, activity_id="dispatch-1", payload={"dispatch_id":"dispatch-1","pane":"solar-harness:0.2"})
log.append("model_call_failed", actor="builder", sprint_id=sid_b, activity_id="dispatch-1", payload={"dispatch_id":"dispatch-1","pane":"solar-harness:0.2","error":"boom"})
log.append("activity_failed", actor="builder", sprint_id=sid_b, activity_id="act-1", payload={"error":"boom"})
PY

echo "T1: replay materializes projection"
OUT=$(python3 "${LIB_DIR}/session_tools.py" replay "$SID_A" --json)
assert_contains "replay ok" "$OUT" '"ok": true'
assert_contains "replay status passed" "$OUT" '"status": "passed"'
assert_contains "replay source of truth" "$OUT" 'sessions/<session_id>/events.jsonl'

echo "T2: log-native evaluator passes clean terminal session"
OUT=$(python3 "${LIB_DIR}/session_tools.py" evaluate "$SID_A" --json)
assert_contains "evaluate pass" "$OUT" '"verdict": "pass"'
assert_contains "evaluate log native" "$OUT" '"log_native": true'
assert_contains "evaluate artifact native false" "$OUT" '"artifact_native": false'

echo "T3: log-native evaluator fails failed session"
OUT=$(python3 "${LIB_DIR}/session_tools.py" evaluate "$SID_B" --json || true)
assert_contains "evaluate fail" "$OUT" '"verdict": "fail"'
assert_contains "evaluate terminal failure" "$OUT" 'terminal_failure_status'

echo "T4: diff detects divergent sessions"
OUT=$(python3 "${LIB_DIR}/session_tools.py" diff "$SID_A" "$SID_B" --json || true)
assert_contains "diff has only_in_a" "$OUT" '"only_in_a"'
assert_contains "diff divergence" "$OUT" '"reason": "event_content_differs"'

echo "T5: same-session cross-harness diff supported"
mkdir -p "$TMP_HARNESS/sessions"
cp -R "${HARNESS_DIR}/sessions/${SID_A}" "$TMP_HARNESS/sessions/${SID_A}"
OUT=$(python3 "${LIB_DIR}/session_tools.py" diff "$SID_A" "$SID_A" --harness-a "$HARNESS_DIR" --harness-b "$TMP_HARNESS" --json)
assert_contains "cross harness flag" "$OUT" '"same_session_cross_harness": true'
assert_contains "cross harness no diff" "$OUT" '"only_in_a": 0'
assert_contains "cross harness ok" "$OUT" '"ok": true'

echo "T6: solar-harness CLI wrapper"
OUT=$("${HARNESS_DIR}/solar-harness.sh" session replay "$SID_A" --json)
assert_contains "cli wrapper replay" "$OUT" '"session_id": "'"$SID_A"'"'

echo ""
echo "=== Session Diff / Log-Native Evaluator: PASS=$PASS FAIL=$FAIL ==="
[[ "$FAIL" -eq 0 ]]
