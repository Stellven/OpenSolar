#!/usr/bin/env bash
set -euo pipefail

EXT_DIR="${EXT_DIR:-$HOME/.solar/harness/extensions/chatgpt-knowledge-capture}"
CHROME_APP="${CHROME_APP:-Google Chrome}"

if [[ ! -f "$EXT_DIR/manifest.json" ]]; then
  echo "missing extension manifest: $EXT_DIR/manifest.json" >&2
  exit 2
fi

open -a "$CHROME_APP" --args --load-extension="$EXT_DIR" "$@"
