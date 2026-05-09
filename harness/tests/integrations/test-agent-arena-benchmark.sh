#!/usr/bin/env bash
# test-agent-arena-benchmark.sh — proof harness for public-benchmark-ready agent arena.
set -euo pipefail

HARNESS_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
BENCH="$HARNESS_DIR/lib/agent_arena_benchmark.py"
OUT_JSON="$(mktemp /tmp/solar-agent-arena.XXXXXX.json)"
OUT_MD="$(mktemp /tmp/solar-agent-arena.XXXXXX.md)"
EVIDENCE_DIR="$(mktemp -d /tmp/solar-agent-arena-evidence.XXXXXX)"
trap 'rm -f "$OUT_JSON" "$OUT_MD"; rm -rf "$EVIDENCE_DIR"' EXIT

PASS=0
FAIL=0
pass() { echo "  PASS: $1"; PASS=$((PASS + 1)); }
fail() { echo "  FAIL: $1"; FAIL=$((FAIL + 1)); }

echo "A1 — doctor exposes agents and public benchmark adapters"
if python3 "$BENCH" doctor --json >/tmp/solar-agent-arena-doctor.json; then
  pass "doctor exits 0"
else
  fail "doctor exits 0"
fi

if python3 - /tmp/solar-agent-arena-doctor.json >/dev/null <<'PY'
import json, sys
d=json.load(open(sys.argv[1]))
assert "solar-harness" in d["agents"]
assert d["agents"]["solar-harness"]["available"] is True
assert "source" in d["agents"]["hermes"]
ids={b["id"] for b in d["public_benchmark_adapters"]}
assert {"swe-bench","terminal-bench","osworld","gaia","webarena","tau-bench"} <= ids
PY
then
  pass "doctor has world benchmark adapter inventory"
else
  fail "doctor has world benchmark adapter inventory"
fi

echo ""
echo "A2 — quick arena run produces evidence-backed Solar result"
if python3 "$BENCH" run --json --agents solar-harness --out-json "$OUT_JSON" --out-md "$OUT_MD" --evidence-dir "$EVIDENCE_DIR" >/tmp/solar-agent-arena-run.json; then
  pass "arena exits 0"
else
  fail "arena exits 0: $(tail -30 /tmp/solar-agent-arena-run.json | tr '\n' ' ')"
fi

if python3 - "$OUT_JSON" >/dev/null <<'PY'
import json, sys
d=json.load(open(sys.argv[1]))
assert d["ok"] is True, d
solar=[a for a in d["agents"] if a["agent"]=="solar-harness"][0]
assert solar["status"] == "ok", solar
assert solar["score"] == solar["max_score"] and solar["max_score"] >= 4, solar
assert d["claim_boundary"].startswith("Solar-Harness can claim")
PY
then
  pass "arena JSON proves Solar smoke suite"
else
  fail "arena JSON proves Solar smoke suite"
fi

[[ -s "$OUT_MD" ]] && grep -q "Solar Agent Arena Benchmark" "$OUT_MD" \
  && pass "arena markdown report written" || fail "arena markdown report written"

[[ -s "$EVIDENCE_DIR/arena.json" ]] \
  && [[ -s "$EVIDENCE_DIR/agents/solar-harness/status.json" ]] \
  && [[ -s "$EVIDENCE_DIR/agents/solar-harness/commands/state-read-preflight.json" ]] \
  && pass "arena evidence bundle written" || fail "arena evidence bundle written"

echo ""
echo "A3 — Hermes runtime smoke is separated from Solar capability score"
if python3 "$BENCH" run --json --agents solar-harness,hermes --out-json "$OUT_JSON" --out-md "$OUT_MD" --evidence-dir "$EVIDENCE_DIR" >/tmp/solar-agent-arena-hermes.json 2>/tmp/solar-agent-arena-hermes.err; then
  pass "arena with Hermes runtime still runs Solar task"
else
  fail "arena with Hermes runtime still runs Solar task"
fi

if python3 - "$OUT_JSON" >/dev/null <<'PY'
import json, sys
d=json.load(open(sys.argv[1]))
hermes=[a for a in d["agents"] if a["agent"]=="hermes"][0]
assert hermes["status"] == "ok", hermes
assert hermes["score"] == hermes["max_score"] and hermes["max_score"] >= 2, hermes
assert "runtime smoke only" in hermes["reason"], hermes
assert hermes["source"]["source_verified"] is True, hermes
PY
then
  pass "Hermes runtime smoke passes without claiming head-to-head superiority"
else
  fail "Hermes runtime smoke boundary is honest"
fi

echo ""
echo "A4 — head-to-head suite and soak mode run same-task verifiers"
if python3 "$BENCH" run --json --suite head-to-head --agents solar-harness,hermes --out-json "$OUT_JSON" --out-md "$OUT_MD" --evidence-dir "$EVIDENCE_DIR" >/tmp/solar-agent-arena-h2h.json 2>/tmp/solar-agent-arena-h2h.err; then
  pass "head-to-head run exits 0"
else
  fail "head-to-head run exits 0: $(tail -30 /tmp/solar-agent-arena-h2h.err | tr '\n' ' ')"
fi

if python3 - "$OUT_JSON" >/dev/null <<'PY'
import json, sys
d=json.load(open(sys.argv[1]))
assert d["suite"] == "head-to-head", d
agents={a["agent"]: a for a in d["agents"]}
assert agents["solar-harness"]["score"] == agents["solar-harness"]["max_score"] == 2, agents
assert agents["hermes"]["score"] == agents["hermes"]["max_score"] == 2, agents
for a in agents.values():
    assert all(t.get("verification", {}).get("ok") is True for t in a["tasks"]), a
PY
then
  pass "head-to-head same-task verifiers pass"
else
  fail "head-to-head same-task verifiers pass"
fi

SOAK_DIR="$(mktemp -d /tmp/solar-agent-arena-soak.XXXXXX)"
if python3 "$BENCH" soak --json --suite head-to-head --agents solar-harness,hermes --max-iterations 1 --interval-sec 0 --auto-repair --out-dir "$SOAK_DIR" >/tmp/solar-agent-arena-soak.json 2>/tmp/solar-agent-arena-soak.err; then
  pass "soak one-iteration exits 0"
else
  fail "soak one-iteration exits 0: $(tail -30 /tmp/solar-agent-arena-soak.err | tr '\n' ' ')"
fi
[[ -s "$SOAK_DIR/summary.json" && -s "$SOAK_DIR/soak.jsonl" ]] \
  && pass "soak evidence written" || fail "soak evidence written"
rm -rf "$SOAK_DIR"

echo ""
echo "=== Agent Arena Benchmark Test: PASS=$PASS FAIL=$FAIL ==="
[[ "$FAIL" -eq 0 ]]
