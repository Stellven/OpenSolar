---
id: sprint-20260510-contract-housekeeping
title: Solar Contract Library Housekeeping
priority: P2
lane: reliability
bypass_pm: true
handoff_to: builder_main
target_role: builder
owner: solar-harness
---

# Contract — Solar Contract Library Housekeeping

## Intent

清理合约库里的低风险残留：`no_status` 合约诊断、旧 task_queue pending 残留、expired leases。不得抢占正在 active 的 P0/P1 sprint，不得伪造历史状态。

## Current Facts

- Contract total: 103.
- no_status contracts: 11.
- pending queue remnants: 2.
- Active sprints to avoid: `sprint-20260510-data-plane-storage-access-unification`, `sprint-20260510-solar-mia-full-integration`.

## Done

- D1: 生成 `reports/contract-housekeeping/no-status-audit.md/json`，列出 11 个 no_status 合约、对应文件、mtime、是否有 handoff/eval/events/task_graph。
- D2: 生成 `reports/contract-housekeeping/queue-audit.md/json`，列出 pending queue remnants，并判定是否 stale/terminal/unsafe。
- D3: 只清理明确 stale 且 terminal 的 queue remnants；active 或无法判断的队列只报告，不删除。
- D4: 运行 pane lease reap 并报告 reaped 数量。
- D5: 写 handoff，总结清理前后 contract/status/queue/lease 数量。

## Safety Rules

- 不得修改 active sprint 的 contract/status/task_graph/queue。
- 不得为 no_status 合约伪造 passed/failed；只能报告或标记 `needs_triage` 到 housekeeping report。
- 删除 queue 前必须保存备份到 `reports/contract-housekeeping/queue-backup/`。
- 所有动作可重跑、幂等。

## Verify Commands

```bash
test -f /Users/sihaoli/.solar/harness/reports/contract-housekeeping/no-status-audit.json
test -f /Users/sihaoli/.solar/harness/reports/contract-housekeeping/queue-audit.json
test -f /Users/sihaoli/.solar/harness/sprints/sprint-20260510-contract-housekeeping.handoff.md
```
