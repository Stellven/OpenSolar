# Implementation Plan — Remote-Only Dispatch Productization Smoke

## 变更文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `~/.solar/harness/sprints/...plan.md` | 创建 | 本计划文件 |
| `~/.solar/harness/sprints/...handoff.md` | 已存在 | D2 产物，已由 builder 写入 |
| `~/.solar/harness/sprints/...status.json` | 更新 | 状态流转: reviewing → planning → implementation_complete |
| `~/.solar/harness/sprints/...eval.md` | 待写 | D4 评估报告（evaluator 角色） |
| `~/.solar/harness/sprints/...eval.json` | 待写 | D4 结构化评估结果 |

## 技术方案

### 任务分解

**D1 — 环境记录** (已完成)
- 执行 `hostname`, `pwd`, `date -u` 并记录
- 验证: hostname 包含 "Mac-mini" → 符合合约约束

**D2 — Handoff 文件** (已完成)
- 写入 `~/.solar/harness/sprints/sprint-20260510-remote-dispatch-productization-remote-only-smoke.handoff.md`
- 包含: hostname=lisihaodeMac-mini-3.local, pwd=/Users/lisihao/Knowledge, date=2026-05-11T00:48:07Z

**D3 — 状态更新** (已完成)
- status.json 已更新为 `reviewing` / `implementation_complete`
- history 记录了 `builder_handoff` 事件

**D4 — 评估** (待 evaluator 执行)
- 写 eval.md 和 eval.json
- 验证 D1-D3 产出文件存在且内容正确
- 运行 Verify Commands 并记录结果

**D5 — 最终状态** (待 evaluator 执行)
- 将 status 标为 `passed`

### 数据流

```
MacBook (codex/coordinator)
  → remote dispatch (solar-remote-dispatch)
  → Mac mini (builder)
    → D1: hostname/pwd/date 记录
    → D2: handoff.md 写入
    → D3: status → reviewing
  → Mac mini (evaluator)
    → D4: eval.md + eval.json
    → D5: status → passed
```

## 风险点

1. **主机名验证严格性**：合约要求 "若 hostname 不是 Mac mini，不得通过"。当前 hostname 为 `lisihaodeMac-mini-3.local`，包含 "Mac-mini" 但不完全是 "Mac mini"（有连字符和后缀）。evaluator 应接受此变体。

2. **状态文件已处于 reviewing**：status.json 已被之前的 builder 运行更新为 `reviewing`/`implementation_complete`。本次 plan 执行不应降级状态，应保持或推进。

3. **handoff.md 已存在**：不要覆盖已存在的 handoff 文件，它包含有效的 D1-D2 证据。

4. **不修改源码约束**：合约明确要求不修改源码。本 smoke test 仅写状态文件和 handoff，不涉及源码修改。

5. **evaluator 角色分离**：builder 不应执行 D4/D5（evaluator 任务），保持角色分离。
