#!/usr/bin/env bash
# test-skills-inject-idempotent.sh — verify skills inject is idempotent
# Passes if both blocks are present after 2 inject calls with identical result.
set -euo pipefail

HARNESS_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SKILLS_PY="$HARNESS_DIR/lib/solar_skills.py"
TMPDIR_TEST="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_TEST"' EXIT

fail() { echo "FAIL: $*" >&2; exit 1; }
pass() { echo "PASS: $*"; }

# Create a minimal dispatch file
DISPATCH="$TMPDIR_TEST/test.dispatch.md"
cat > "$DISPATCH" <<'DISPATCH_EOF'
# Test Dispatch

## 本次任务
- Sprint ID: test-sprint
- 角色: 建设者

### 步骤
1. 执行任务
DISPATCH_EOF

# First inject
python3 "$SKILLS_PY" inject "$DISPATCH" || fail "first inject failed"

# Verify both blocks present
grep -q "<solar-skills-context>" "$DISPATCH" || fail "solar-skills-context block missing after first inject"
grep -q "</solar-skills-context>" "$DISPATCH" || fail "solar-skills-context close tag missing"
grep -q "<solar-knowledge-context>" "$DISPATCH" || fail "solar-knowledge-context block missing after first inject"
grep -q "</solar-knowledge-context>" "$DISPATCH" || fail "solar-knowledge-context close tag missing"

# Capture content after first inject
AFTER_FIRST="$(cat "$DISPATCH")"

# Second inject (idempotency test)
python3 "$SKILLS_PY" inject "$DISPATCH" || fail "second inject failed"

AFTER_SECOND="$(cat "$DISPATCH")"

# Counts must be identical (no duplication)
COUNT_SKILLS_OPEN_1=$(echo "$AFTER_FIRST" | grep -c "<solar-skills-context>" || true)
COUNT_SKILLS_OPEN_2=$(echo "$AFTER_SECOND" | grep -c "<solar-skills-context>" || true)
[[ "$COUNT_SKILLS_OPEN_1" -eq 1 ]] || fail "expected 1 solar-skills-context after first inject, got $COUNT_SKILLS_OPEN_1"
[[ "$COUNT_SKILLS_OPEN_2" -eq 1 ]] || fail "expected 1 solar-skills-context after second inject, got $COUNT_SKILLS_OPEN_2"

COUNT_KB_OPEN_1=$(echo "$AFTER_FIRST" | grep -c "<solar-knowledge-context>" || true)
COUNT_KB_OPEN_2=$(echo "$AFTER_SECOND" | grep -c "<solar-knowledge-context>" || true)
[[ "$COUNT_KB_OPEN_1" -eq 1 ]] || fail "expected 1 solar-knowledge-context after first inject, got $COUNT_KB_OPEN_1"
[[ "$COUNT_KB_OPEN_2" -eq 1 ]] || fail "expected 1 solar-knowledge-context after second inject, got $COUNT_KB_OPEN_2"

pass "inject idempotency — both blocks present exactly once after 2 inject calls"
pass "solar-skills-context block: present"
pass "solar-knowledge-context block: present"
echo "PROBES_PASSED=3 PROBES_FAILED=0"
exit 0
