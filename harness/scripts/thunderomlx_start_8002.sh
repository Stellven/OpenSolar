#!/usr/bin/env bash
set -euo pipefail

HARNESS_DIR="${HARNESS_DIR:-$HOME/.solar/harness}"
THUNDER_DIR="${THUNDER_DIR:-$HOME/ThunderOMLX}"
MODEL_DIR="${THUNDEROMLX_MODEL_DIR:-/Volumes/toshiba/models}"
SSD_CACHE_DIR="${THUNDEROMLX_SSD_CACHE_DIR:-/Volumes/RAID0-Main/omlx-cache/ssd-qwen36}"
SSD_CACHE_MAX_SIZE="${THUNDEROMLX_SSD_CACHE_MAX_SIZE:-460GB}"
HOT_CACHE_MAX_SIZE="${THUNDEROMLX_HOT_CACHE_MAX_SIZE:-8GB}"
INITIAL_CACHE_BLOCKS="${THUNDEROMLX_INITIAL_CACHE_BLOCKS:-256}"
HOST="${THUNDEROMLX_HOST:-127.0.0.1}"
PORT="${THUNDEROMLX_PORT:-8002}"
SESSION="${THUNDEROMLX_TMUX_SESSION:-thunderomlx-qwen36}"
LOG_FILE="${THUNDEROMLX_LOG_FILE:-$HARNESS_DIR/logs/thunderomlx-8002.log}"

mkdir -p "$SSD_CACHE_DIR" "$HARNESS_DIR/logs"

if ! lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  tmux kill-session -t "$SESSION" 2>/dev/null || true
  tmux new-session -d -s "$SESSION" \
    "cd '$THUNDER_DIR' && exec ./venv/bin/omlx serve --model-dir '$MODEL_DIR' --host '$HOST' --port '$PORT' --max-model-memory 50GB --max-process-memory disabled --max-num-seqs 1 --completion-batch-size 1 --paged-ssd-cache-dir '$SSD_CACHE_DIR' --paged-ssd-cache-max-size '$SSD_CACHE_MAX_SIZE' --hot-cache-max-size '$HOT_CACHE_MAX_SIZE' --initial-cache-blocks '$INITIAL_CACHE_BLOCKS' 2>&1 | tee -a '$LOG_FILE'"
fi

for _ in $(seq 1 90); do
  if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    python3 "$HARNESS_DIR/scripts/thunderomlx_auto_prewarm.py" --force
    exit 0
  fi
  sleep 2
done

tmux capture-pane -t "$SESSION" -p -S -120 2>/dev/null | tail -120 >&2 || true
echo "ThunderOMLX did not listen on $HOST:$PORT" >&2
exit 1
