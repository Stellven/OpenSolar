#!/usr/bin/env bash
set -euo pipefail

HARNESS_DIR="${HARNESS_DIR:-$HOME/.solar/harness}"

pass=0
fail=0

ok() { pass=$((pass + 1)); printf 'ok - %s\n' "$1"; }
not_ok() { fail=$((fail + 1)); printf 'not ok - %s\n' "$1"; }

assert_contains() {
  local haystack="$1" needle="$2" label="$3"
  if grep -Fq "$needle" <<<"$haystack"; then
    ok "$label"
  else
    not_ok "$label: missing '$needle'"
    printf '%s\n' "$haystack"
  fi
}

source "$HARNESS_DIR/lib/harness-config.sh"

matrix="$(solar_lab_builder_matrix)"
assert_contains "$matrix" "anthropic-sonnet" "config-backed matrix includes explicit Anthropic Sonnet alias"

label="$(solar_lab_builder_matrix_label "$matrix")"
assert_contains "$label" "GLM-5.1" "matrix label shows GLM"
assert_contains "$label" "Claude Sonnet" "matrix label shows Claude Sonnet"

slot4="$(
  SOLAR_BUILDER_SLOT=lab-builder-4 \
  bash "$HARNESS_DIR/lib/persona-config.sh" --print-config lab-builder
)"
assert_contains "$slot4" "DISPLAY_MODEL='Claude Sonnet (Anthropic, lab-builder-4)'" "slot 4 reads config and resolves to native Claude Sonnet"
assert_contains "$slot4" "BASE_URL=''" "native Claude Sonnet does not use Zhipu/DeepSeek gateway"

override="$(
  SOLAR_LAB_BUILDER_MODEL_MATRIX=glm,anthropic-sonnet \
  SOLAR_BUILDER_SLOT=lab-builder-2 \
  bash "$HARNESS_DIR/lib/persona-config.sh" --print-config lab-builder
)"
assert_contains "$override" "DISPLAY_MODEL='Claude Sonnet (Anthropic, lab-builder-2)'" "env override remains available for one-off testing"

footer="$(
  bash "$HARNESS_DIR/quota-footer.sh" builder "Builder 主建设者"
)"
assert_contains "$footer" "模型:Sonnet" "footer shows actual model, not host title/local label"

pm_cfg="$(bash "$HARNESS_DIR/lib/persona-config.sh" --print-config pm)"
planner_cfg="$(bash "$HARNESS_DIR/lib/persona-config.sh" --print-config planner)"
evaluator_cfg="$(bash "$HARNESS_DIR/lib/persona-config.sh" --print-config evaluator)"
assert_contains "$pm_cfg" "MODEL_FLAG='--model sonnet'" "PM avoids broken Opus alias"
assert_contains "$planner_cfg" "MODEL_FLAG='--model sonnet'" "planner avoids broken Opus alias"
assert_contains "$evaluator_cfg" "MODEL_FLAG='--model sonnet'" "evaluator avoids broken Opus alias"
assert_contains "$pm_cfg" "DISPLAY_MODEL='Claude Sonnet (Anthropic)'" "PM display shows configured Sonnet route"

tmp_cfg="$(mktemp)"
python3 - "$HARNESS_DIR/config/solar-user-config.json" "$tmp_cfg" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
data.setdefault("models", {})["pm"] = "opus"
Path(sys.argv[2]).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
pm_opus_guard="$(SOLAR_USER_CONFIG="$tmp_cfg" bash "$HARNESS_DIR/lib/persona-config.sh" --print-config pm)"
rm -f "$tmp_cfg"
assert_contains "$pm_opus_guard" "MODEL_FLAG='--model sonnet'" "Opus-configured PM is guarded to Sonnet"
assert_contains "$pm_opus_guard" "Opus 1210 guard" "Opus health guard is visible when config requests Opus"

printf '=== RESULT: PASS=%d FAIL=%d ===\n' "$pass" "$fail"
[[ "$fail" -eq 0 ]]
