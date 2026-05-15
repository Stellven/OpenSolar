---
id: sprint-20260510-solar-mia-full-integration
title: Solar MIA Full Integration — Upstream First
priority: P1
lane: capability
bypass_pm: true
handoff_to: builder_main
target_role: builder
owner: solar-harness
upstream: https://github.com/ECNU-SII/MIA
upstream_head: d428f4897782c996ca34ec46fd61fc4620c0884d
---

# Contract — Solar MIA Full Integration

## Intent

完整评估并融合 ECNU-SII/MIA，而不是继续以本地 `experience` 实现为主。上游项目由专家团队开发，应作为主参考实现；Solar 现有 `lib/experience/*` 只作为适配层、回退层或迁移对象。

## Source Of Truth

- Paper: `https://arxiv.org/pdf/2604.04503`
- Code: `https://github.com/ECNU-SII/MIA`
- Upstream HEAD at contract creation: `d428f4897782c996ca34ec46fd61fc4620c0884d`

## Current Solar State

- Solar 已有 inspired-by-MIA 实现：`lib/experience/*`、`experience/index.db`、`experience/trajectory/*`、`experience/entries/*`。
- 该实现已通过 `sprint-20260509-205414`，但只覆盖经验压缩/检索/dispatch advisory。
- 缺失原版 MIA 的 `Manager / Planner / Executor / Memory-Serve / Planner-Train / Executor-Train / TTRL` 等完整机制。

## Done

- D1: Vendor 上游 MIA 到 `vendor/MIA`，记录 commit、license、目录树、依赖、入口命令；不得改写上游源码。
- D2: 生成 inventory report，覆盖 `Executor-Train`、`Planner-Train`、`Memory-Serve`、`TTRL`、数据格式、配置、脚本、模型依赖、GPU/CPU 要求。
- D3: 生成 collision report，对比上游 MIA 与 Solar `lib/experience`、coordinator、DAG scheduler、QMD/Mirage 数据层的职责重叠和冲突。
- D4: 跑最小 upstream smoke：能 import/启动文档中最小组件；如果依赖缺失，必须标 `pending` 并写清楚缺什么，不能伪 ok。
- D5: 设计融合方案：明确哪些模块直接采用上游，哪些用 adapter，哪些保留 Solar experience 作为兼容层，哪些不接入。
- D6: 写 P2 implementation contract，把“可安全并入 Solar”的模块拆成 DAG 节点；本 sprint 不做大规模训练、不下载大模型、不污染用户 shell。

## Principles

- Upstream first: 上游 MIA 是主实现，本地 experience layer 不是主实现。
- No overwrite: 不直接删除或替换 Solar experience memory；先 adapter/collision report。
- No fake pass: 依赖、模型、GPU 缺失必须 `pending|warn`，不能算 ok。
- No secrets: 不把 API key/token 写入 vendor、reports、config。
- No heavy foreground: 任何训练、embedding、大下载都必须另开 sprint 并后台/隔离执行。

## Verify Commands

```bash
test -d /Users/lisihao/.solar/harness/vendor/MIA
git -C /Users/lisihao/.solar/harness/vendor/MIA rev-parse HEAD
test -f /Users/lisihao/.solar/harness/reports/mia-integration/inventory.md
test -f /Users/lisihao/.solar/harness/reports/mia-integration/collision-report.md
test -f /Users/lisihao/.solar/harness/reports/mia-integration/fusion-design.md
```

## Required Evidence

- `reports/mia-integration/inventory.md`
- `reports/mia-integration/inventory.json`
- `reports/mia-integration/collision-report.md`
- `reports/mia-integration/upstream-smoke.md`
- `reports/mia-integration/fusion-design.md`
- `sprint-20260510-solar-mia-full-integration.handoff.md`
