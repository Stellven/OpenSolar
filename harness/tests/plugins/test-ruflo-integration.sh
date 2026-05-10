#!/usr/bin/env bash
# test-ruflo-integration.sh — Ruflo safe vendor/plugin/capability integration.
set -euo pipefail

HARNESS_DIR="${HARNESS_DIR:-$HOME/.solar/harness}"
PASS=0
FAIL=0

ok() { echo "  PASS: $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL: $1"; FAIL=$((FAIL + 1)); }

echo "R1 — modules compile"
python3 -m py_compile "$HARNESS_DIR/lib/ruflo_adapter.py" "$HARNESS_DIR/lib/solar_skills.py" \
  && ok "ruflo/skills modules compile" || fail "ruflo/skills modules compile"

echo "R2 — Ruflo vendor status is readable"
OUT=$("$HARNESS_DIR/solar-harness.sh" integrations ruflo-status --json)
python3 - "$OUT" <<'PY' && ok "ruflo status ok" || fail "ruflo status ok"
import json, sys
d=json.loads(sys.argv[1])
assert d["ok"] is True
assert d["source"]["repo"] == "https://github.com/ruvnet/ruflo.git"
assert d["inventory"]["plugins"] >= 30
assert d["inventory"]["skill_files"] >= 100
assert d["mode"] == "read_only_safe_vendor"
PY

echo "R3 — plugin manifest and capability registry"
OUT=$("$HARNESS_DIR/solar-harness.sh" integrations validate --id ruflo --json)
python3 - "$OUT" <<'PY' && ok "ruflo manifest valid" || fail "ruflo manifest valid"
import json, sys
d=json.loads(sys.argv[1])
assert d["ok"] is True
assert d["results"][0]["valid"] is True
PY
"$HARNESS_DIR/solar-harness.sh" integrations sync-caps --json >/tmp/solar-ruflo-sync.json
OUT=$("$HARNESS_DIR/solar-harness.sh" integrations capabilities query ruflo.swarm --json)
python3 - "$OUT" <<'PY' && ok "ruflo.swarm capability found" || fail "ruflo.swarm capability found"
import json, sys
d=json.loads(sys.argv[1])
assert d["found"] is True
assert d["providers"][0]["provider"] == "ruflo"
PY

echo "R4 — skill inventory includes Ruflo but does not claim all skills are prompt-loaded"
OUT=$("$HARNESS_DIR/solar-harness.sh" skills inventory --json)
python3 - "$OUT" <<'PY' && ok "skill inventory truth labels" || fail "skill inventory truth labels"
import json, sys
d=json.loads(sys.argv[1])
assert d["totals"]["skill_files_recursive"] >= 1000
assert d["sources"]["vendor-skill-files"]["ruflo"]["skill_files"] >= 100
assert d["usability"]["all_1000_plus_loaded_into_prompt"] is False
PY

echo "R5 — dispatch injection selects Ruflo by keyword"
TMP=$(mktemp /tmp/solar-ruflo-dispatch.XXXXXX.md)
printf '# Dispatch\n\nUse Ruflo swarm and Claude Flow for multi-agent orchestration.\n' > "$TMP"
"$HARNESS_DIR/solar-harness.sh" skills inject "$TMP" >/dev/null
grep -q "Ruflo (ruflo.swarm" "$TMP" && ok "Ruflo capability injected" || fail "Ruflo capability injected"
rm -f "$TMP"

echo ""
echo "=== Ruflo Integration Test: PASS=$PASS FAIL=$FAIL ==="
[[ "$FAIL" -eq 0 ]]
