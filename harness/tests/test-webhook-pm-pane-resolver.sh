#!/usr/bin/env bash
set -euo pipefail

HARNESS_DIR="${HARNESS_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
WEBHOOK="$HARNESS_DIR/webhook-server.ts"

grep -q "function resolvePmPane" "$WEBHOOK" || {
  echo "missing resolvePmPane" >&2
  exit 1
}

grep -q "function notifyPmPane" "$WEBHOOK" || {
  echo "missing notifyPmPane" >&2
  exit 1
}

grep -q "list-panes.*#{pane_index}" "$WEBHOOK" || {
  echo "resolver does not inspect tmux pane titles" >&2
  exit 1
}

grep -q "SOLAR_WEBHOOK_PM_PANE" "$WEBHOOK" || {
  echo "missing explicit PM pane override" >&2
  exit 1
}

if grep -q 'send-keys -t "${SESSION_NAME}:0.0"' "$WEBHOOK"; then
  echo "webhook still hardcodes pane 0.0 send-keys" >&2
  exit 1
fi

grep -q 'execFileSync(' "$WEBHOOK" || {
  echo "webhook notification should use execFileSync argv instead of shell string" >&2
  exit 1
}

echo "PASS webhook resolves PM pane before notify"
