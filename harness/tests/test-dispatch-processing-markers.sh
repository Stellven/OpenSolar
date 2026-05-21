#!/usr/bin/env bash
set -euo pipefail
ROOT="${HARNESS_DIR:-/Users/lisihao/.solar/harness}"
regex=$(grep -E "grep -qE 'Crafting\|Cogitating" "$ROOT/coordinator.sh" | sed -E "s/.*grep -qE '([^']+)'.*/\1/" | tail -1)
for marker in Ideating Musing Orbiting Reticulating '✢'; do
  if ! printf '%s\n' "$marker" | grep -qE "$regex"; then
    echo "FAIL: missing processing marker $marker" >&2
    exit 1
  fi
done
echo "PASS: dispatch processing markers include Claude Code 2.x states"
