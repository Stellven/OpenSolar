# Plan: headless pane agent routing replan

## Strategy

本 sprint 只做规划和证据化分析，不直接修改 production profile。执行顺序：

1. 盘点 Mac mini 当前 headless multi-task 能力、profiles、doctor、status、Antigravity 安装/OAuth 状态。
2. 基于用户给出的三家定位，形成角色路由矩阵和后端 gate。
3. 设计 tmux headless worker pool 分层架构、并行策略、write_scope/成本/安全约束。
4. 形成后续 implementation 变更清单和迁移计划。
5. 汇总最终报告，明确已验证事实、假设、阻塞和下一步。

## DAG Summary

```text
N1 current-state audit
  ├─> N2 role-routing matrix
  └─> N3 headless-pool architecture
N2 + N3 ─> N4 implementation backlog
N4 ─> N5 final report
```
