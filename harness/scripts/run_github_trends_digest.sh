#!/usr/bin/env bash
set -euo pipefail

HARNESS_DIR="${HARNESS_DIR:-/Users/lisihao/Solar/harness}"
CONFIG="${GITHUB_TRENDS_CONFIG:-$HARNESS_DIR/config/github-trends.yaml}"
PYTHON="${PYTHON:-python3}"

exec "$PYTHON" "$HARNESS_DIR/scripts/github_trends_digest.py" run --config "$CONFIG" "$@"
