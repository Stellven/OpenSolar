# Contract: tmux 无头 pane agent routing 重规划

priority: `P0`
epic_id: `epic-20260521-headless-agent-runtime`
sprint_id: `sprint-20260521-headless-pane-agent-routing-replan`
handoff_to: `multi-task`
target_runtime: `Mac mini /Users/lisihao/.solar/harness`

## Intent

基于用户对 Claude Code、Codex、Antigravity/Gemini、ThunderOMLX 的定位，重新规划 solar-harness tmux headless worker pool 的角色路由、并行度、后端 gate 和监控验收标准。

## Required Outputs

- `/Users/lisihao/.solar/harness/monitor-reports/headless-agent-routing-replan.md`
- `/Users/lisihao/.solar/harness/sprints/sprint-20260521-headless-pane-agent-routing-replan.N1-handoff.md`
- `/Users/lisihao/.solar/harness/sprints/sprint-20260521-headless-pane-agent-routing-replan.N2-handoff.md`
- `/Users/lisihao/.solar/harness/sprints/sprint-20260521-headless-pane-agent-routing-replan.N3-handoff.md`
- `/Users/lisihao/.solar/harness/sprints/sprint-20260521-headless-pane-agent-routing-replan.N4-handoff.md`
- `/Users/lisihao/.solar/harness/sprints/sprint-20260521-headless-pane-agent-routing-replan.N5-handoff.md`

## Required Capabilities

- `solar-harness.runtime`
- `multi-task`
- `tmux`
- `model-routing`
- `cost-control`
- `agent-orchestration`

## Stop Rules

- 不打印 API key、OAuth token、refresh token、authorization code。
- 不自动启用 Antigravity dispatch，除非 `agy --print` smoke 明确成功。
- 不把用户提供 benchmark 当作已验证事实；未验证必须标 `assumption`。
- 不改 ThunderOMLX 缓存开关。
- 不 kill 现有 tmux/pane/process。
- 不把 knowledge extraction 默认路由到 Claude。

## Acceptance

- 最终报告包含：
  - 角色/任务类型/首选后端/备用后端/并行度/成本/风险矩阵。
  - headless pane pool 分层架构。
  - Antigravity gated rollout 方案。
  - Gemini CLI 迁移处理。
  - ThunderOMLX 用于知识抽取和粗活的边界。
  - Claude/Codex 分工原则。
  - 后续实现任务清单。
- 每个节点必须写 handoff。
- task_graph 所有节点最终 `passed`。

## Suggested Verification

```bash
solar-harness multi-task profiles
solar-harness multi-task doctor --no-clear --renderer plain
solar-harness multi-task status --no-clear --renderer plain
/Users/lisihao/.local/bin/agy --version
```

任何失败都必须写入 blocker 和 next action。
