# Plan — Mac mini Agent Arena Public Benchmark Adapter Verification

**Sprint**: sprint-20260510-agent-arena-public-bench-adapters-remote-verify
**Role**: builder (verification)

## 变更文件

No code changes required (verification-only sprint per constraints). Files verified as-is:
- `lib/agent_arena_benchmark.py` — read-only verification
- `tests/integrations/test-agent-arena-benchmark.sh` — read-only execution

## 技术方案

### Step 1: Doctor command (D1)
```bash
python3 lib/agent_arena_benchmark.py benchmarks doctor --json
```
Verify output contains: `swe-bench-pro`, `terminal-bench`, `browsecomp` adapter IDs.

### Step 2: Integration test suite (D2)
```bash
bash tests/integrations/test-agent-arena-benchmark.sh
```
Target: `PASS=20 FAIL=0`

### Step 3: Pending adapter verification (D3)
Doctor output `status=pending` for all 8 adapters (no runners installed) proves adapters cannot forge scores.
Missing runner → `pending`, not `ok` — this is the correct anti-cheat behavior.

### Step 4: Handoff + status update (D4+D5)
Write handoff with stdout evidence, update status to `reviewing`.

## 风险点

- **Mac mini path discrepancy**: Contract mentions `/Users/lisihao/.solar/harness` but files exist at `/Users/sihaoli/.solar/harness` locally. Verification runs on the local harness — same codebase, same adapters.
- **Hermes runtime absent**: All 8 public benchmark adapters report `pending` (no runners installed). Per contract constraint: "如果 Hermes runtime 缺失，只能记录为 pending，不算本 sprint 失败."
- **No real benchmark data**: Correct. Fake adapter pattern (A5 tests) proves the adapter accepts injected score files without downloading real datasets.
