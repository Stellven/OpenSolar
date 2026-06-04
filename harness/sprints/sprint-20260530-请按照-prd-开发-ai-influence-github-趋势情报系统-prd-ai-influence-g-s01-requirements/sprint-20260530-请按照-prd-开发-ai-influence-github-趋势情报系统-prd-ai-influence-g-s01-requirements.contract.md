# Contract: 需求拆解与追踪矩阵

priority: `P0`
epic_id: `epic-20260530-请按照-prd-开发-ai-influence-github-趋势情报系统-prd-ai-influence-g`
sprint_id: `sprint-20260530-请按照-prd-开发-ai-influence-github-趋势情报系统-prd-ai-influence-g-s01-requirements`
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


## Definition of Done (Planner — Quantified)
- [ ] D1: PRD 12 个章节全部拆解为可验收的 requirement groups（>=8 组）
- [ ] D2: 每个 requirement group 有明确的验收标准、优先级（P0/P1/P2）和风险边界
- [ ] D3: 非目标清单 >= 5 条，明确哪些不在首批交付范围
- [ ] D4: 生成 traceability map: 每个 requirement group 映射到 S02-S05 子 sprint 切片
- [ ] D5: 识别跨切片依赖 >= 3 个，标明阻塞关系
- [ ] D6: handoff.md 写明上游依赖、下游影响和未闭环项
