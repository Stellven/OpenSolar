#!/usr/bin/env bash
# Regression test: queued wake routing must not fall through to generic builder.

set -uo pipefail
cd "$(dirname "$0")/.."
PASS=0
FAIL=0

ok() { echo "PASS: $*"; PASS=$((PASS+1)); }
fail() { echo "FAIL: $*"; FAIL=$((FAIL+1)); }

SCRIPT="solar-harness.sh"
STATE_MAPPER="lib/state-mapper.sh"

python3 - <<'PY'
from pathlib import Path
s = Path("solar-harness.sh").read_text()
queued = s.index("    queued)")
drafting = s.index("    drafting|drafting_held)")
wildcard = s.index("    *)", drafting)
assert queued < drafting < wildcard
assert "wake_promoted_queued_to_planner" in s
assert "wake_promoted_queued_to_builder" in s
assert "wake_promoted_queued_to_pm" in s
assert "runtime_status.py" in s[queued:drafting]
assert '"bypass_pm":true' in s[queued:drafting]
assert '"auto_held":false' in s[queued:drafting]
assert 'target_pane="$LIVE_PLANNER"' in s[queued:drafting]
assert 'target_pane="$LIVE_BUILDER"' in s[queued:drafting]
assert 'target_pane="$LIVE_PM"' in s[queued:drafting]
assert "未知状态: ${st}，派发给 PM 做状态诊断" in s
PY
[[ $? -eq 0 ]] && ok "wake has explicit queued routing before wildcard" || fail "queued routing missing or ordered incorrectly"

grep -q "phase in ('prd_ready', 'contract_ready') or handoff_to == 'planner'" "$STATE_MAPPER" \
  && ok "state mapper routes queued contract_ready to planner" \
  || fail "state mapper does not route queued contract_ready to planner"

grep -q "handoff_to in ('builder', 'builder_main')" "$STATE_MAPPER" \
  && ok "state mapper routes queued builder handoff to builder_main" \
  || fail "state mapper does not route queued builder handoff"

bash -n "$SCRIPT" \
  && ok "solar-harness.sh syntax ok" \
  || fail "solar-harness.sh syntax failed"

bash -n "$STATE_MAPPER" \
  && ok "state-mapper.sh syntax ok" \
  || fail "state-mapper.sh syntax failed"

python3 - <<'PY'
from pathlib import Path
s = Path("coordinator.sh").read_text()
assert "status_has_bypass_pm()" in s
assert "sprint_bypasses_pm_gate()" in s
assert "sprint_bypasses_pm_gate \"$sid\"" in s
assert "phase == \"planning_complete\"" in s
PY
[[ $? -eq 0 ]] && ok "coordinator gate honors status bypass" || fail "coordinator gate bypass missing"

echo ""
echo "========================"
echo "PASS=$PASS FAIL=$FAIL"
if [[ "$FAIL" -eq 0 ]]; then echo "PASS"; exit 0; else echo "FAIL"; exit 1; fi
