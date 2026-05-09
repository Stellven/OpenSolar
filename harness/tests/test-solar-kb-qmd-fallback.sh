#!/usr/bin/env bash
# test-solar-kb-qmd-fallback.sh — Regression tests for solar-knowledge-context qmd fallback
# Coverage: A1-A6 from sprint contract + A3 fail-open + A4 disable flag + A5 max-chars
set -euo pipefail

SCRIPT="$HOME/.solar/harness/lib/solar-knowledge-context.py"
HOOK="$HOME/.claude/hooks/solar-knowledge-context.sh"
PASS=0; FAIL=0

pass() { echo "  PASS: $1"; PASS=$((PASS+1)); }
fail() { echo "  FAIL: $1 — $2"; FAIL=$((FAIL+1)); }

echo "=== test-solar-kb-qmd-fallback.sh ==="

# T1 — DB miss + qmd hit: query known to exist only in qmd solar-wiki
t1_hits=$(python3 "$SCRIPT" --query '大模型热力学' --json --fail-open \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print(len(d["hits"]))' 2>/dev/null)
if [ "${t1_hits:-0}" -ge 1 ]; then
  pass "T1 qmd hit count=$t1_hits for '大模型热力学'"
else
  fail "T1" "expected ≥1 hit, got ${t1_hits:-error}"
fi

# T2 — hit schema: source/title/snippet/path all present
schema_ok=$(python3 "$SCRIPT" --query '大模型热力学' --json --fail-open \
  | python3 -c '
import json,sys
d=json.load(sys.stdin)
h=d["hits"][0] if d["hits"] else {}
ok = all(k in h for k in ["source","title","snippet","path"])
print("ok" if ok else "missing:"+str([k for k in ["source","title","snippet","path"] if k not in h]))
' 2>/dev/null)
if [ "$schema_ok" = "ok" ]; then
  pass "T2 hit schema has required fields"
else
  fail "T2" "schema check: $schema_ok"
fi

# T3 — qmd unavailable → fail-open, valid JSON, hits may be empty
t3_out=$(QMD_BIN=/tmp/no-such-qmd python3 "$SCRIPT" \
  --query '大模型热力学' --json --fail-open 2>/dev/null)
if echo "$t3_out" | python3 -c 'import json,sys; json.load(sys.stdin)' 2>/dev/null; then
  pass "T3 qmd missing → fail-open valid JSON"
else
  fail "T3" "invalid JSON or exception when qmd missing"
fi

# T4 — SOLAR_KB_CONTEXT=0 disables hook injection
t4_out=$(printf '{"user_prompt":"大模型热力学"}' \
  | SOLAR_KB_CONTEXT=0 "$HOOK" 2>/dev/null)
if [ -z "$t4_out" ]; then
  pass "T4 SOLAR_KB_CONTEXT=0 → empty hook output"
else
  fail "T4" "hook output not empty with SOLAR_KB_CONTEXT=0"
fi

# T5 — max-chars budget respected
t5_chars=$(python3 "$SCRIPT" --query '大模型热力学' --json --max-chars 500 --fail-open \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d.get("total_chars",0))' 2>/dev/null)
if [ "${t5_chars:-9999}" -le 500 ]; then
  pass "T5 max-chars=500 respected (total_chars=${t5_chars})"
else
  fail "T5" "total_chars=${t5_chars} exceeds 500"
fi

# T6 — valid JSON output always
t6_valid=$(python3 "$SCRIPT" --query '大模型热力学' --json --fail-open \
  | python3 -c 'import json,sys; d=json.load(sys.stdin); print("ok")' 2>/dev/null)
if [ "$t6_valid" = "ok" ]; then
  pass "T6 output is valid JSON"
else
  fail "T6" "invalid JSON output"
fi

# T7 — hook emits <solar-knowledge-context> for matching prompt
t7_tag=$(printf '{"user_prompt":"帮我基于大模型热力学分析注意力机制"}' \
  | "$HOOK" 2>/dev/null | grep -c '<solar-knowledge-context>' || true)
if [ "${t7_tag:-0}" -ge 1 ]; then
  pass "T7 hook emits <solar-knowledge-context>"
else
  fail "T7" "hook did not emit <solar-knowledge-context>"
fi

# T8 — hit deduplication: no duplicate ids for same query
t8_dedup=$(python3 "$SCRIPT" --query '大模型热力学' --json --fail-open \
  | python3 -c '
import json,sys
d=json.load(sys.stdin)
ids=[h.get("id","") for h in d["hits"]]
print("ok" if len(ids)==len(set(ids)) else "dups:"+str(ids))
' 2>/dev/null)
if [ "$t8_dedup" = "ok" ]; then
  pass "T8 no duplicate hits"
else
  fail "T8" "$t8_dedup"
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
[ "$FAIL" -eq 0 ]
