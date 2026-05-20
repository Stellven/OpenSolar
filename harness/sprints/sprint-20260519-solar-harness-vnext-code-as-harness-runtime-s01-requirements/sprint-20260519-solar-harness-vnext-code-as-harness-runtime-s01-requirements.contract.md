# Contract: 需求拆解与追踪矩阵

priority: `P0`
epic_id: `epic-20260519-solar-harness-vnext-code-as-harness-runtime`
sprint_id: `sprint-20260519-solar-harness-vnext-code-as-harness-runtime-s01-requirements`
handoff_to: `planner`

## Intent

把用户原始大需求拆成可验收 outcomes、边界、非目标和追踪矩阵。

## Required Capabilities

- product.requirements
- workflow.planning

## Acceptance

- 每个 outcome 都有验收标准和风险边界
- 明确哪些工作不能直接派 builder
- 生成父 epic 到子 sprint 的 traceability map

## Stop Rules

- 缺 `.task_graph.json` 不得派 builder。
- 缺可复现验证不得标记 passed。
- 发现 scope 冲突必须回写父级 traceability。
