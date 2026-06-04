# Contract: 调度、自动化与可视化

priority: `P0`
epic_id: `epic-20260528-p0-ai-influence-youtube-报告流默认流程固化与验收`
sprint_id: `sprint-20260528-p0-ai-influence-youtube-报告流默认流程固化与验收-s04-orchestration-ui`
handoff_to: `planner`

## Intent

把核心能力接入 autopilot、DAG 调度、status UI、pane 可视化和运行时证据。

## Required Capabilities

- workflow.planning
- observability
- frontend

## Acceptance

- ready 子任务能自动激活并派到正确角色
- UI 显示 epic、child sprint、能力使用和阻塞原因
- pane 输出不再只靠自然语言声称完成

## Stop Rules

- 缺 `.task_graph.json` 不得派 builder。
- 缺可复现验证不得标记 passed。
- 发现 scope 冲突必须回写父级 traceability。
