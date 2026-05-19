#!/usr/bin/env bash
# test-autoresearch-integration.sh — smallnest/autoresearch safe local-issue integration.
set -euo pipefail

HARNESS_DIR="${HARNESS_DIR:-$HOME/.solar/harness}"
PASS=0
FAIL=0

ok() { echo "  PASS: $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL: $1"; FAIL=$((FAIL + 1)); }

echo "A1 — modules compile"
python3 -m py_compile "$HARNESS_DIR/lib/autoresearch_adapter.py" "$HARNESS_DIR/lib/external-integrations-health.py" \
  && ok "autoresearch modules compile" || fail "autoresearch modules compile"

echo "A2 — status is readable even before vendor"
OUT=$("$HARNESS_DIR/solar-harness.sh" integrations autoresearch-status --json)
python3 - "$OUT" <<'PY' && ok "autoresearch status schema" || fail "autoresearch status schema"
import json, sys
d=json.loads(sys.argv[1])
assert d["source"]["repo"] == "https://github.com/smallnest/autoresearch.git"
assert d["mode"] == "explicit_local_issue_runner"
assert d["safety"]["default_execution"] == "dry_run"
assert d["safety"]["execute_requires_flag"] == "--execute"
PY

echo "A3 — dry-run local issue creates controlled issue file and does not execute"
TMP_PROJECT=$(mktemp -d /tmp/solar-autoresearch-project.XXXXXX)
git -C "$TMP_PROJECT" init -q
OUT=$("$HARNESS_DIR/solar-harness.sh" integrations autoresearch-run-local \
  --project "$TMP_PROJECT" \
  --issue-title "Improve test harness" \
  --issue-body "Add a tiny deterministic check." \
  --max-iterations 2 \
  --json || true)
python3 - "$OUT" "$TMP_PROJECT" <<'PY' && ok "autoresearch dry-run issue plan" || fail "autoresearch dry-run issue plan"
import json, sys
from pathlib import Path
d=json.loads(sys.argv[1])
project=str(Path(sys.argv[2]).resolve())
if d.get("reason") == "autoresearch_run_sh_missing":
    assert d["autoresearch_dir"].endswith("vendor/autoresearch")
else:
    assert d["ok"] is True
    assert d["executed"] is False
    assert d["mode"] == "dry_run"
    assert str(Path(d["created_issue"]).resolve()).startswith(project)
    assert d["command"][-2] == str(d["issue_number"])
    assert d["command"][-1] == "2"
    assert any(str(item).startswith("--issues-dir=") for item in d["command"])
    assert d["environment"]["PASSING_SCORE"] == "80"
PY
rm -rf "$TMP_PROJECT"

echo "A4 — plugin manifest validates and capability sync sees provider"
OUT=$("$HARNESS_DIR/solar-harness.sh" integrations validate --id autoresearch --json)
python3 - "$OUT" <<'PY' && ok "autoresearch manifest valid" || fail "autoresearch manifest valid"
import json, sys
d=json.loads(sys.argv[1])
assert d["ok"] is True
assert d["results"][0]["valid"] is True
PY
"$HARNESS_DIR/solar-harness.sh" integrations sync-caps --json >/tmp/solar-autoresearch-sync.json
OUT=$("$HARNESS_DIR/solar-harness.sh" integrations capabilities query autoresearch.issue_loop --json)
python3 - "$OUT" <<'PY' && ok "autoresearch capability found" || fail "autoresearch capability found"
import json, sys
d=json.loads(sys.argv[1])
assert d["found"] is True
assert d["providers"][0]["provider"] == "autoresearch"
PY

echo "A5 — unified health exposes autoresearch"
OUT=$("$HARNESS_DIR/solar-harness.sh" integrations status --json --refresh)
python3 - "$OUT" <<'PY' && ok "autoresearch unified health present" || fail "autoresearch unified health present"
import json, sys
d=json.loads(sys.argv[1])
items=[x for x in d.get("integrations", []) if "autoresearch" in x.get("name", "").lower()]
assert items, "autoresearch integration missing"
ev=items[0].get("evidence", {})
assert ev.get("dispatch_capability") == "autoresearch.issue_loop"
assert ev.get("execute_requires") == "--execute"
PY

echo ""
echo "=== Autoresearch Integration Test: PASS=$PASS FAIL=$FAIL ==="
[[ "$FAIL" -eq 0 ]]
