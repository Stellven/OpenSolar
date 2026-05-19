#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

python3 -m py_compile lib/skill_healthcheck.py
bash -n solar-harness.sh

out="$(./solar-harness.sh skills healthcheck --force --no-remote --json)"
python3 - "$out" <<'PY'
import json
import pathlib
import sys

data = json.loads(sys.argv[1])
assert data["ok"] is True
assert data["window_ok"] is True
assert data["power_ok"] is True
assert data["remote"]["checked"] is False
assert data["report_path"]
assert pathlib.Path(data["report_path"]).exists()
assert isinstance(data["skill_candidates"], list)
assert data["memrl_status"]["implementation_exists"] is True
assert "sys_skill_bank" in data["memrl_status"]["required_tables_present"]
assert data["skillrl_status"]["knowledge_doc_exists"] is True
assert data["evolution_engine"]["ok"] is True
assert data["evolution_gate"]["promotion_allowed"] is False
assert "external_eval_pack_not_passed" in data["evolution_gate"]["promotion_blockers"]
assert data["memrl_feedback"]["jsonl"]
print("skill-healthcheck ok")
PY
