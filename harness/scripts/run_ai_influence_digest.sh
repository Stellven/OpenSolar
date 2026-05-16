#!/usr/bin/env bash
set -euo pipefail

HARNESS_DIR="${HARNESS_DIR:-/Users/lisihao/Solar/harness}"
CONFIG="${AI_INFLUENCE_DIGEST_CONFIG:-$HARNESS_DIR/config/ai-influence-daily-digest.yaml}"
PYTHON="${PYTHON:-python3}"

exec "$PYTHON" "$HARNESS_DIR/scripts/ai_influence_digest.py" --config "$CONFIG" "$@"
