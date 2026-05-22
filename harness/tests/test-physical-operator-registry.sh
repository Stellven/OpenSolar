#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export HARNESS_DIR="$ROOT"
export SOLAR_MULTI_TASK_OPERATORS="$ROOT/config/physical-operators.json"

python3 -m py_compile "$ROOT/lib/multi_task_runner.py"
python3 -m json.tool "$ROOT/config/physical-operators.json" >/dev/null

ROOT="$ROOT" python3 - <<'PY'
import os
import sys
from pathlib import Path

root = Path(os.environ["ROOT"])
sys.path.insert(0, str(root / "lib"))
import multi_task_runner as m

cases = [
    (
        {"id": "impl", "role": "builder", "operator_selector": {"task_type": "implementation"}},
        "mini-claude-sonnet-builder",
        "builder",
    ),
    (
        {"id": "kb", "role": "builder", "operator_selector": {"task_type": "knowledge-extraction"}},
        "mini-thunderomlx-qwen36-knowledge",
        "knowledge-extractor",
    ),
    (
        {"id": "plan", "preferred_operator": "mini-claude-opus-planner"},
        "mini-claude-opus-planner",
        "planner",
    ),
]

for node, operator_id, profile_name in cases:
    selected = m.select_profile(node)
    assert selected.get("operator_id") == operator_id, (node, selected)
    assert selected.get("name") == profile_name, (node, selected)

legacy = m.select_profile({"id": "legacy", "role": "builder"})
assert legacy.get("name") == "builder", legacy
assert legacy.get("operator_id") in (None, ""), legacy

disabled = m.select_profile({"id": "agy", "preferred_operator": "mini-antigravity-gemini35-flash-high"})
assert disabled.get("name") == "builder", disabled
assert "preferred_operator_unavailable" in disabled.get("operator_fallback_reason", ""), disabled

image = m.select_profile({
    "id": "image",
    "role": "builder",
    "operator_selector": {"task_type": "image-processing"},
    "goal": "analyze screenshot image",
})
assert image.get("name") == "gemini-builder", image
assert image.get("operator_id") == "mini-antigravity-gemini35-flash-image", image

image_op = m.resolve_operator("mini-antigravity-gemini35-flash-image")
ok, reason = m.operator_dispatchable(image_op)
assert ok, (ok, reason)
assert "image" in image_op.get("input_modalities", []), image_op
assert image_op.get("command"), image_op

assert not m.QUOTA_RE.search("quota cycle monthly; quota refresh unknown")
assert m.QUOTA_RE.search("API Error 429 quota exceeded")

print("physical_operator_registry_ok")
PY
