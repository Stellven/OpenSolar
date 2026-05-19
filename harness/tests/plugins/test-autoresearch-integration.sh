#!/usr/bin/env bash
# test-autoresearch-integration.sh — smallnest/autoresearch safe local-issue integration.
set -euo pipefail

HARNESS_DIR="${HARNESS_DIR:-$HOME/.solar/harness}"
PASS=0
FAIL=0

ok() { echo "  PASS: $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL: $1"; FAIL=$((FAIL + 1)); }

echo "A1 — modules compile"
python3 -m py_compile \
  "$HARNESS_DIR/lib/autoresearch_adapter.py" \
  "$HARNESS_DIR/lib/external-integrations-health.py" \
  "$HARNESS_DIR/lib/intent_engine_adapter.py" \
  "$HARNESS_DIR/lib/capability_inference.py" \
  "$HARNESS_DIR/lib/solar_skills.py" \
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

echo "A5 — planner/builder dispatch can see autoresearch but does not auto-execute"
intent="$("$HARNESS_DIR/solar-harness.sh" intent match "Use autoresearch issue loop for this local issue with score gate" 2>/dev/null)"
grep -q "autoresearch" <<<"$intent" && ok "autoresearch intent route" || fail "autoresearch intent route"
plain_intent="$("$HARNESS_DIR/solar-harness.sh" intent match "请写一段普通总结，不要运行本地问题循环" 2>/dev/null)"
if grep -q "autoresearch" <<<"$plain_intent"; then
  fail "negative intent should not route to autoresearch"
else
  ok "negative intent avoids autoresearch"
fi

TMP_DISPATCH=$(mktemp /tmp/solar-autoresearch-dispatch.XXXXXX.md)
cat > "$TMP_DISPATCH" <<'EOF'
# Planner Handoff

Implement the local issue through an explicit autoresearch issue-loop.
Use score-gated iterations, but do not execute without user approval.
EOF
"$HARNESS_DIR/solar-harness.sh" skills inject "$TMP_DISPATCH" >/dev/null
grep -q "Autoresearch (autoresearch.issue_loop" "$TMP_DISPATCH" \
  && grep -q "不得自动运行" "$TMP_DISPATCH" \
  && ok "Autoresearch capability injected with stop rules" \
  || fail "Autoresearch capability injected with stop rules"
python3 - "$TMP_DISPATCH.intent.json" <<'PY' && ok "autoresearch telemetry visible" || fail "autoresearch telemetry visible"
import json, sys
d=json.load(open(sys.argv[1], encoding="utf-8"))
assert any(m.get("source") == "autoresearch" for m in d["intent"]["matches"]), d["intent"]
assert any(c.get("provider") == "Autoresearch" for c in d["capabilities"]), d["capabilities"]
assert d["worker_visible"]["solar_intent_context"] is True, d["worker_visible"]
assert d["worker_visible"]["solar_capability_context"] is True, d["worker_visible"]
PY
OUT=$(python3 "$HARNESS_DIR/lib/capability_inference.py" infer --text "Create a local issue and run an autoresearch score gate implementation loop")
python3 - "$OUT" <<'PY' && ok "capability inference routes autoresearch" || fail "capability inference routes autoresearch"
import json, sys
d=json.loads(sys.argv[1])
matches=d.get("matches", [])
assert any(m.get("provider") == "Autoresearch" and "autoresearch.issue_loop" in m.get("capabilities", []) for m in matches), matches
PY

echo "A6 — unified health exposes autoresearch"
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
