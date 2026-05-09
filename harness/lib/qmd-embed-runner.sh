#!/usr/bin/env bash
# qmd-embed-runner.sh — idle-only background embedding runner for solar-wiki.

set -euo pipefail

HARNESS_DIR="${HARNESS_DIR:-$HOME/.solar/harness}"
QMD_BIN="${QMD_BIN:-$(command -v qmd 2>/dev/null || true)}"
[[ -z "$QMD_BIN" && -x "$HOME/.npm-global/bin/qmd" ]] && QMD_BIN="$HOME/.npm-global/bin/qmd"
COLLECTION="${QMD_WIKI_COLLECTION:-solar-wiki}"
RUN_DIR="$HARNESS_DIR/run"
STATE_DIR="$HARNESS_DIR/state"
LOCK_DIR="$RUN_DIR/qmd-embed.lockdir"
STATUS_FILE="$STATE_DIR/qmd-embed-status.json"
LOG_FILE="$RUN_DIR/qmd-embed.log"
MIN_IDLE_SEC="${SOLAR_QMD_EMBED_MIN_IDLE_SEC:-900}"
MAX_LOAD_1M="${SOLAR_QMD_EMBED_MAX_LOAD_1M:-4.0}"
CHECK_INTERVAL="${SOLAR_QMD_EMBED_CHECK_INTERVAL:-20}"
FORCE="${SOLAR_QMD_EMBED_FORCE:-0}"

mkdir -p "$RUN_DIR" "$STATE_DIR"

json_escape() {
  python3 -c 'import json,sys; print(json.dumps(sys.stdin.read())[1:-1])'
}

status_json() {
  local state="$1"
  local detail="${2:-}"
  local pending_before="${3:-}"
  local pending_after="${4:-}"
  local idle_seconds="${5:-}"
  local load_1m="${6:-}"
  local ts
  ts="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  cat > "$STATUS_FILE" <<EOF
{
  "state": "$state",
  "collection": "$COLLECTION",
  "mode": "idle_only",
  "updated_at": "$ts",
  "pending_before": "${pending_before}",
  "pending_after": "${pending_after}",
  "idle_seconds": "${idle_seconds}",
  "min_idle_seconds": "${MIN_IDLE_SEC}",
  "load_1m": "${load_1m}",
  "max_load_1m": "${MAX_LOAD_1M}",
  "detail": "$(printf '%s' "$detail" | json_escape)",
  "log": "$LOG_FILE"
}
EOF
}

pending_count() {
  [[ -n "$QMD_BIN" ]] || { echo ""; return; }
  "$QMD_BIN" status 2>/dev/null | awk '/Pending:/ {print $2; exit}'
}

idle_seconds() {
  ioreg -c IOHIDSystem 2>/dev/null | awk '/HIDIdleTime/ {print int($NF / 1000000000); exit}'
}

load_1m() {
  sysctl -n vm.loadavg 2>/dev/null | awk '{for(i=1;i<=NF;i++) if ($i ~ /^[0-9.]+$/) {print $i; exit}}'
}

float_le() {
  awk -v a="${1:-999}" -v b="${2:-0}" 'BEGIN { exit (a <= b ? 0 : 1) }'
}

is_idle_enough() {
  [[ "$FORCE" == "1" ]] && return 0
  local idle load
  idle="$(idle_seconds || true)"
  load="$(load_1m || true)"
  [[ -n "$idle" ]] || idle=0
  [[ -n "$load" ]] || load=999
  if (( idle < MIN_IDLE_SEC )); then
    status_json "idle_wait" "user active; waiting for idle window" "$(pending_count || true)" "" "$idle" "$load"
    return 1
  fi
  if ! float_le "$load" "$MAX_LOAD_1M"; then
    status_json "idle_wait" "system load too high; waiting for idle window" "$(pending_count || true)" "" "$idle" "$load"
    return 1
  fi
  return 0
}

if [[ -z "$QMD_BIN" || ! -x "$QMD_BIN" ]]; then
  status_json "missing" "qmd binary not found"
  exit 0
fi

if ! is_idle_enough; then
  exit 0
fi

if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  status_json "locked" "another qmd embed run is active"
  exit 0
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

before="$(pending_count || true)"
idle="$(idle_seconds || true)"
load="$(load_1m || true)"
status_json "running" "qmd embed started" "$before" "" "$idle" "$load"

{
  echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] qmd embed -c $COLLECTION started; pending_before=${before:-N/A}"
  /usr/bin/nice -n 15 "$QMD_BIN" embed -c "$COLLECTION" &
  embed_pid=$!
  while kill -0 "$embed_pid" 2>/dev/null; do
    sleep "$CHECK_INTERVAL"
    if ! is_idle_enough; then
      echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] user/system active; stopping qmd embed pid=$embed_pid"
      kill -TERM "$embed_pid" 2>/dev/null || true
      sleep 3
      kill -KILL "$embed_pid" 2>/dev/null || true
      wait "$embed_pid" 2>/dev/null || true
      after="$(pending_count || true)"
      status_json "paused" "stopped because machine is no longer idle" "$before" "$after" "$(idle_seconds || true)" "$(load_1m || true)"
      exit 0
    fi
  done
  wait "$embed_pid"
  rc=$?
  after="$(pending_count || true)"
  echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] qmd embed finished rc=$rc pending_after=${after:-N/A}"
  if [[ "$rc" -eq 0 ]]; then
    status_json "ok" "qmd embed completed" "$before" "$after" "$(idle_seconds || true)" "$(load_1m || true)"
  else
    status_json "error" "qmd embed failed rc=$rc" "$before" "$after" "$(idle_seconds || true)" "$(load_1m || true)"
  fi
  exit "$rc"
} >>"$LOG_FILE" 2>&1
