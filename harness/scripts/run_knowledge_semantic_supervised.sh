#!/usr/bin/env bash
set -uo pipefail

HARNESS_DIR="${HARNESS_DIR:-${SOLAR_REPO}/harness}"
PYTHON="${PYTHON:-python3}"
export PATH="${SOLAR_HOME}/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"
export SOLAR_HARNESS_BIN="${SOLAR_HARNESS_BIN:-${SOLAR_HOME}/bin/solar-harness}"
VAULT="${VAULT:-${SOLAR_KNOWLEDGE_DIR}}"
REGISTRY_DB="${REGISTRY_DB:-$VAULT/_registry/knowledge_ingest.sqlite}"
ENDPOINT="${ENDPOINT:-http://127.0.0.1:8002/v1/chat/completions}"
LOCAL_MODEL="${LOCAL_MODEL:-Qwen3.6-35b-a3b}"
SOURCE_DIR="${SOURCE_DIR:-$VAULT/_raw}"
LOG_DIR="${LOG_DIR:-${HARNESS_DIR}/run}"
LOCK_DIR="${LOCK_DIR:-${HARNESS_DIR}/state/knowledge-semantic-supervised.lockdir}"

mkdir -p "$LOG_DIR" "$(dirname "$LOCK_DIR")"
ACTIVE_PIDS="$(pgrep -f "knowledge-semantic-extract.py .*supervised-backfill" || true)"
if [[ -n "$ACTIVE_PIDS" ]]; then
  STALE_SECONDS="${SUPERVISED_STALE_SECONDS:-$(( (${TIMEOUT_SEC:-240} * ${MAX_BATCHES:-6}) + 120 ))}"
  for active_pid in $ACTIVE_PIDS; do
    active_age="$(ps -o etimes= -p "$active_pid" 2>/dev/null | tr -d ' ' || true)"
    if [[ "$active_age" =~ ^[0-9]+$ && "$active_age" -gt "$STALE_SECONDS" ]]; then
      echo "[knowledge-semantic-supervised] stale supervised-backfill pid=$active_pid age=${active_age}s > ${STALE_SECONDS}s; terminating $(date -u +%Y-%m-%dT%H:%M:%SZ)"
      kill -TERM "$active_pid" 2>/dev/null || true
      sleep 2
      if kill -0 "$active_pid" 2>/dev/null; then
        kill -KILL "$active_pid" 2>/dev/null || true
      fi
    else
      echo "[knowledge-semantic-supervised] another supervised-backfill process is already running pid=$active_pid age=${active_age:-N/A}s; skip $(date -u +%Y-%m-%dT%H:%M:%SZ)"
      exit 0
    fi
  done
fi
if [[ -d "$LOCK_DIR" ]]; then
  lock_pid="$(cat "$LOCK_DIR/pid" 2>/dev/null || true)"
  if [[ "$lock_pid" =~ ^[0-9]+$ ]] && kill -0 "$lock_pid" 2>/dev/null; then
    echo "[knowledge-semantic-supervised] already running pid=$lock_pid; skip $(date -u +%Y-%m-%dT%H:%M:%SZ)"
    exit 0
  fi
  echo "[knowledge-semantic-supervised] stale lock detected pid=${lock_pid:-N/A}; clearing $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  rm -rf "$LOCK_DIR"
fi
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  echo "[knowledge-semantic-supervised] already running; skip $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  exit 0
fi
echo "$$" > "$LOCK_DIR/pid"
trap 'rm -rf "$LOCK_DIR"' EXIT INT TERM

echo "[knowledge-semantic-supervised] start $(date -u +%Y-%m-%dT%H:%M:%SZ)"

"$PYTHON" "$HARNESS_DIR/tools/knowledge-semantic-extract.py" \
  --vault "$VAULT" \
  --registry-db "$REGISTRY_DB" \
  --endpoint "$ENDPOINT" \
  --local-model "$LOCAL_MODEL" \
  --max-chars "${MAX_CHARS:-9000}" \
  --max-tokens "${MAX_TOKENS:-3200}" \
  --timeout-sec "${TIMEOUT_SEC:-240}" \
  --max-consecutive-failures "${MAX_CONSECUTIVE_FAILURES:-3}" \
  --max-fail-rate "${MAX_FAIL_RATE:-0.5}" \
  --min-circuit-attempts "${MIN_CIRCUIT_ATTEMPTS:-4}" \
  --qmd-after \
  supervised-backfill \
  --source-dir "$SOURCE_DIR" \
  --batch-size "${BATCH_SIZE:-2}" \
  --max-batches "${MAX_BATCHES:-6}" \
  --sleep-sec "${SLEEP_SEC:-5}" \
  --stale-minutes "${STALE_MINUTES:-30}" \
  --reap-limit "${REAP_LIMIT:-20}" \
  --json \
  ${VERBOSE:+--verbose}

rc=$?
echo "[knowledge-semantic-supervised] exit $(date -u +%Y-%m-%dT%H:%M:%SZ) rc=$rc"

if [[ "${ALLOW_PARTIAL_SUCCESS:-1}" == "1" && "$rc" != "0" ]]; then
  echo "[knowledge-semantic-supervised] completed with warnings; ALLOW_PARTIAL_SUCCESS=1 so exiting 0"
  exit 0
fi
exit "$rc"
