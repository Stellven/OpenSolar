---
id: sprint-20260510-agent-arena-public-bench-adapters-remote-verify
title: Mac mini Agent Arena public benchmark adapter verification
priority: P0
lane: verification
bypass_pm: true
handoff_to: builder_main
target_role: builder
owner: mac-mini-solar-harness
---

# Contract — Mac mini Agent Arena Public Benchmark Adapter Verification

## Intent
Mac mini 上的 Solar Harness 必须用自己的 builder/evaluator 链路验证 Agent Arena benchmark adapter 已经可用，而不是由 Codex 直接 SSH 跑完就算数。

## Scope
验证已同步到 `/Users/lisihao/.solar/harness` 的实现：
- `lib/agent_arena_benchmark.py`
- `tests/integrations/test-agent-arena-benchmark.sh`
- `~/.solar/bin/solar-remote-dispatch`

## Done
- D1: 在 Mac mini 上运行 `python3 ~/.solar/harness/lib/agent_arena_benchmark.py benchmarks doctor --json`，输出必须包含 `swe-bench-pro`、`terminal-bench`、`browsecomp`。
- D2: 在 Mac mini 上运行 `bash ~/.solar/harness/tests/integrations/test-agent-arena-benchmark.sh`，必须 `PASS=20 FAIL=0`。
- D3: 证明缺少真实 runner 时 adapter 是 `pending`，不是 `ok`，不能伪造成绩。
- D4: 写 handoff：`~/.solar/harness/sprints/sprint-20260510-agent-arena-public-bench-adapters-remote-verify.handoff.md`，粘贴关键 stdout 和结论。
- D5: 更新 status 为 `reviewing`，等待 evaluator 复核。

## Constraints
- 不要修改源代码，除非测试失败且必须修复。
- 不要下载真实 SWE-bench/Terminal-Bench/BrowseComp 数据。
- 不要声称 public leaderboard 成绩。
- 如果 Hermes runtime 缺失，只能记录为 pending，不算本 sprint 失败。

## Verify Commands
```bash
python3 ~/.solar/harness/lib/agent_arena_benchmark.py benchmarks doctor --json
bash ~/.solar/harness/tests/integrations/test-agent-arena-benchmark.sh
```
