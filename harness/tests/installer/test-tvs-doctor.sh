#!/usr/bin/env bash
# Regression: installer doctor exposes TVS renderer readiness and smoke result.
set -euo pipefail

HARNESS_DIR_REAL="$(cd "$(dirname "$0")/../.." && pwd)"
TVS_ROOT="${SOLAR_TVS_ROOT:-$HOME/TVS}"

if [[ ! -f "$TVS_ROOT/index.ts" ]]; then
  echo "SKIP: TVS root not found at $TVS_ROOT"
  exit 0
fi

JSON_OUT="$(HARNESS_DIR="$HARNESS_DIR_REAL" SOLAR_TVS_ROOT="$TVS_ROOT" bash "$HARNESS_DIR_REAL/installer/doctor.sh" --json)"
JSON_OUT="$JSON_OUT" python3 - <<'PY'
import json
import os

d = json.loads(os.environ["JSON_OUT"])
tvs = d.get("services", {}).get("tvs_renderer")
assert isinstance(tvs, dict), "services.tvs_renderer missing"
assert tvs.get("bun") == "ok", tvs
assert tvs.get("cli") == "ok", tvs
assert tvs.get("root") == "ok", tvs
assert tvs.get("smoke") == "ok", tvs
assert tvs.get("status") == "ok", tvs
PY

SUMMARY_OUT="$(HARNESS_DIR="$HARNESS_DIR_REAL" SOLAR_TVS_ROOT="$TVS_ROOT" bash "$HARNESS_DIR_REAL/installer/doctor.sh" --summary)"
grep -q "TVS:" <<<"$SUMMARY_OUT" || { echo "FAIL: summary missing TVS line"; exit 1; }
grep -q "smoke=ok" <<<"$SUMMARY_OUT" || { echo "FAIL: summary missing TVS smoke ok"; exit 1; }

echo "PASS: installer doctor exposes TVS renderer readiness"
