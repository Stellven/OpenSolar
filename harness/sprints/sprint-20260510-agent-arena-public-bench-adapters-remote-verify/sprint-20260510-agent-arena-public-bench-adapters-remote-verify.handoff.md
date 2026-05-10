# Handoff — sprint-20260510-agent-arena-public-bench-adapters-remote-verify
Builder: 建设者化身
Round: 1

## 变更文件列表

- 无源代码变更。
- 验证范围：
  - `lib/agent_arena_benchmark.py`
  - `tests/integrations/test-agent-arena-benchmark.sh`

## Done 定义达成

### D1 — Doctor output contains swe-bench-pro, terminal-bench, browsecomp ✅

Command:
```bash
python3 lib/agent_arena_benchmark.py benchmarks doctor --json
```

Key stdout (adapter IDs extracted):
```
adapter_ids: ['swe-bench-pro', 'swe-bench', 'terminal-bench', 'browsecomp', 'osworld', 'gaia', 'webarena', 'tau-bench']
```

All three required adapters present: `swe-bench-pro` ✅ `terminal-bench` ✅ `browsecomp` ✅

### D2 — Integration tests PASS=20 FAIL=0 ✅

Command:
```bash
bash tests/integrations/test-agent-arena-benchmark.sh
```

Full stdout:
```
A1 — doctor exposes agents and public benchmark adapters
  PASS: doctor exits 0
  PASS: doctor has world benchmark adapter inventory

A2 — quick arena run produces evidence-backed Solar result
  PASS: arena exits 0
  PASS: arena JSON proves Solar smoke suite
  PASS: arena markdown report written
  PASS: arena evidence bundle written

A3 — Hermes runtime smoke is separated from Solar capability score
  PASS: arena with Hermes runtime still runs Solar task
  PASS: Hermes runtime boundary is honest

A4 — head-to-head suite and soak mode run same-task verifiers
  PASS: head-to-head run exits 0
  PASS: head-to-head same-task verifiers pass for available agents
  PASS: soak one-iteration exits 0
  PASS: soak evidence written

A5 — public benchmark adapters run only through configured runners
  PASS: SWE-bench Pro fake adapter exits 0
  PASS: SWE-bench Pro adapter records score/evidence
  PASS: Terminal-Bench fake adapter exits 0
  PASS: Terminal-Bench adapter parses pass rate
  PASS: BrowseComp fake adapter exits 0
  PASS: BrowseComp adapter requires answer/grader artifacts
  PASS: missing runner reports pending without fake score
  PASS: pending adapter does not claim benchmark result

=== Agent Arena Benchmark Test: PASS=20 FAIL=0 ===
```

### D3 — Missing runner → adapter is pending, not ok ✅

From doctor JSON for all 8 adapters:
```json
{
  "id": "swe-bench-pro",
  "status": "pending",
  "configured": false,
  "runner": "",
  "reason": "SWE_BENCH_PRO_CMD not set and none of swebench found"
}
```

A5 tests explicitly verify: "missing runner reports pending without fake score" PASS ✅ and "pending adapter does not claim benchmark result" PASS ✅

Anti-cheat confirmed: adapter cannot forge `ok` status without a real installed runner.

### D4 — Handoff written ✅ (this file)

### D5 — Status updated to reviewing ✅

## 结论

Agent Arena public benchmark adapter verification complete. All 8 adapters (swe-bench-pro, swe-bench, terminal-bench, browsecomp, osworld, gaia, webarena, tau-bench) correctly report `pending` without real runners installed. The fake-adapter pattern (A5) proves score integrity — no runner → no score, no forgery. 20/20 integration tests pass.

No code modifications were needed.
