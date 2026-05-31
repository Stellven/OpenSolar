# Handoff — sprint-20260510-agent-arena-public-bench-adapters-remote-verify

## Summary

Agent Arena public benchmark adapter verification on Mac mini. Eval Round 1 PASS (D1-D5).
This handoff re-materializes to close the stuck graph state (G0 node reviewing, gate_results empty).

## Deliverables (D1-D5)

### D1: benchmarks doctor ✅
- `python3 ~/.solar/harness/lib/agent_arena_benchmark.py benchmarks doctor --json`
- Output includes `swe-bench-pro`, `terminal-bench`, `browsecomp` — all present
- All 8 adapters report `status: pending` (no runners configured, honest)

### D2: Integration tests ⚠️
- Original Round 1 (2026-05-10): PASS=20 FAIL=0 ✅
- Round 2 re-verification (2026-05-20): PASS=17 FAIL=3 — regression in `dag-node-dispatcher` (control plane), not in adapter code
- 3 FAILs are in sections A2/A3 caused by dag-node-dispatcher FileNotFoundError on `.intent.json` sidecar
- All adapter-specific tests (A1, A4, A5 = 17 tests) pass correctly

### D3: Anti-forgery ✅
- All 8 adapters pending when no runner available, ok=false
- Bogus `SWE_BENCH_PRO_CMD=/usr/bin/false` attack: status=error, score.ok=false, reason=missing_score_file
- No forgery possible

### D4: Handoff with stdout evidence ✅
- G0-handoff.md exists at 4928 bytes with full stdout evidence

### D5: Status reviewing ✅
- status.json updated to reviewing

## Compliance

- No source code modifications (md5 cross-host match)
- No real dataset downloads (FAKE_RUNNER mktemp only)
- No public leaderboard claims (claim_boundary present)
- No secrets in reports

## Verification Commands

```bash
$ python3 ~/.solar/harness/lib/agent_arena_benchmark.py benchmarks doctor --json
# 8 adapters listed, swe-bench-pro/terminal-bench/browsecomp present

$ bash ~/.solar/harness/tests/integrations/test-agent-arena-benchmark.sh
# Round 1: PASS=20 FAIL=0 (eval based on this)
# Round 2: PASS=17 FAIL=3 (dag-node-dispatcher regression, not adapter code)
```

## Scope Compliance

- Only wrote handoff files; no source code changes
- Write scope: `*.handoff.md` files only

## Known Risks

1. **dag-node-dispatcher regression**: 9 FAILs in test-graph-node-dispatcher.sh cause 3 FAILs in integration test. Root cause: FileNotFoundError on `.intent.json` sidecar. Outside write scope to fix.
2. **Graph stuck state**: G0 node stuck in `reviewing` with `gate_results: {}`. Sprint finalized but graph never closed.

## Not Done

- dag-node-dispatcher regression fix — requires write access to `tests/control_plane/`
- G0 gate closure — requires graph-scheduler or coordinator action

Knowledge Context: solar-harness context inject used (degraded: mirage timeout)
Harness Modules Used: solar-harness-runtime (dispatch, status, contracts)
