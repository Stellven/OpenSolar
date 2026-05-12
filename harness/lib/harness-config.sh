#!/usr/bin/env bash
# ================================================================
# Solar Harness — operator config reader/writer
#
# Keep runtime launchers out of model policy. Model switches should update
# config/solar-user-config.json (or use an env override for one-off tests),
# then launchers consume this helper.
# ================================================================

[[ -n "${SOLAR_HARNESS_CONFIG_SH_LOADED:-}" ]] && return 0
SOLAR_HARNESS_CONFIG_SH_LOADED=1

HARNESS_DIR="${HARNESS_DIR:-$HOME/.solar/harness}"
SOLAR_USER_CONFIG="${SOLAR_USER_CONFIG:-$HARNESS_DIR/config/solar-user-config.json}"
SOLAR_DEFAULT_LAB_BUILDER_MATRIX="glm,glm,glm,anthropic-sonnet"

solar_config_json_get() {
  local dotted_key="$1"
  local default_value="${2:-}"
  python3 - "$SOLAR_USER_CONFIG" "$dotted_key" "$default_value" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
key = sys.argv[2]
default = sys.argv[3]

try:
    data = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    print(default)
    raise SystemExit(0)

cur = data
for part in key.split("."):
    if not isinstance(cur, dict) or part not in cur:
        print(default)
        raise SystemExit(0)
    cur = cur[part]

if cur is None:
    print(default)
elif isinstance(cur, (str, int, float, bool)):
    print(str(cur))
else:
    print(json.dumps(cur, ensure_ascii=False, separators=(",", ":")))
PY
}

solar_config_json_set() {
  local dotted_key="$1"
  local value="$2"
  python3 - "$SOLAR_USER_CONFIG" "$dotted_key" "$value" <<'PY'
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

path = Path(sys.argv[1])
key = sys.argv[2]
value = sys.argv[3]
path.parent.mkdir(parents=True, exist_ok=True)

try:
    data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
except Exception as exc:
    raise SystemExit(f"invalid config json: {path}: {exc}")

if not isinstance(data, dict):
    data = {}

cur = data
parts = key.split(".")
for part in parts[:-1]:
    nxt = cur.get(part)
    if not isinstance(nxt, dict):
        nxt = {}
        cur[part] = nxt
    cur = nxt
cur[parts[-1]] = value
data["updated_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

tmp = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
tmp.replace(path)
PY
}

solar_lab_builder_matrix() {
  if [[ -n "${SOLAR_LAB_BUILDER_MODEL_MATRIX:-}" ]]; then
    printf '%s\n' "$SOLAR_LAB_BUILDER_MODEL_MATRIX"
    return 0
  fi
  solar_config_json_get "models.lab_builder_matrix" "$SOLAR_DEFAULT_LAB_BUILDER_MATRIX"
}

solar_set_lab_builder_matrix() {
  local matrix="$1"
  if ! solar_validate_lab_builder_matrix "$matrix"; then
    return 1
  fi
  solar_config_json_set "models.lab_builder_matrix" "$matrix"
}

solar_validate_lab_builder_matrix() {
  local matrix="${1:-}"
  python3 - "$matrix" <<'PY'
import re
import sys

matrix = sys.argv[1].strip()
allowed = {
    "glm", "glm-5", "glm-5.1", "zhipu",
    "sonnet", "glm-4.7", "glm47", "zhipu-sonnet",
    "deepseek", "deepseek-v4", "deepseek-v4-pro", "deepseek-v4-flash", "ds", "ds-v4",
    "anthropic-sonnet", "claude", "claude-sonnet", "anthropic",
    "opus", "claude-opus",
}
items = [x.strip().lower() for x in matrix.split(",") if x.strip()]
if not items:
    print("error: empty lab builder matrix", file=sys.stderr)
    raise SystemExit(1)
bad = [x for x in items if x not in allowed or not re.match(r"^[a-z0-9_.-]+$", x)]
if bad:
    print("error: unsupported lab model alias: " + ",".join(bad), file=sys.stderr)
    raise SystemExit(1)
print(matrix)
PY
}

solar_model_alias_label() {
  local alias
  alias=$(printf '%s' "${1:-}" | tr '[:upper:]' '[:lower:]' | xargs)
  case "$alias" in
    glm|glm-5|glm-5.1|zhipu) printf '%s' "GLM-5.1" ;;
    sonnet|glm-4.7|glm47|zhipu-sonnet) printf '%s' "GLM-4.7" ;;
    deepseek|deepseek-v4|deepseek-v4-pro|deepseek-v4-flash|ds|ds-v4) printf '%s' "DeepSeek" ;;
    anthropic-sonnet|claude|claude-sonnet|anthropic) printf '%s' "Claude Sonnet" ;;
    opus|claude-opus) printf '%s' "Claude Opus" ;;
    *) printf '%s' "${alias:-N/A}" ;;
  esac
}

solar_lab_builder_matrix_label() {
  local matrix="${1:-}"
  [[ -n "$matrix" ]] || matrix="$(solar_lab_builder_matrix)"
  python3 - "$matrix" <<'PY'
from collections import Counter
import sys

labels = {
    "glm": "GLM-5.1", "glm-5": "GLM-5.1", "glm-5.1": "GLM-5.1", "zhipu": "GLM-5.1",
    "sonnet": "GLM-4.7", "glm-4.7": "GLM-4.7", "glm47": "GLM-4.7", "zhipu-sonnet": "GLM-4.7",
    "deepseek": "DeepSeek", "deepseek-v4": "DeepSeek", "deepseek-v4-pro": "DeepSeek",
    "deepseek-v4-flash": "DeepSeek", "ds": "DeepSeek", "ds-v4": "DeepSeek",
    "anthropic-sonnet": "Claude Sonnet", "claude": "Claude Sonnet",
    "claude-sonnet": "Claude Sonnet", "anthropic": "Claude Sonnet",
    "opus": "Claude Opus", "claude-opus": "Claude Opus",
}
items = [x.strip().lower() for x in sys.argv[1].split(",") if x.strip()]
names = [labels.get(x, x or "N/A") for x in items]
counts = Counter(names)
parts = []
seen = set()
for name in names:
    if name in seen:
        continue
    seen.add(name)
    n = counts[name]
    parts.append(f"{n} {name}" if n > 1 else name)
print(" + ".join(parts) if parts else "N/A")
PY
}

solar_lab_builder_matrix_item_label() {
  local matrix="${1:-}"
  local index="${2:-0}"
  [[ -n "$matrix" ]] || matrix="$(solar_lab_builder_matrix)"
  local item
  item=$(python3 - "$matrix" "$index" <<'PY'
import sys
items = [x.strip() for x in sys.argv[1].split(",") if x.strip()]
idx = int(sys.argv[2] or 0)
if not items:
    print("N/A")
elif idx < len(items):
    print(items[idx])
else:
    print(items[-1])
PY
)
  solar_model_alias_label "$item"
}
