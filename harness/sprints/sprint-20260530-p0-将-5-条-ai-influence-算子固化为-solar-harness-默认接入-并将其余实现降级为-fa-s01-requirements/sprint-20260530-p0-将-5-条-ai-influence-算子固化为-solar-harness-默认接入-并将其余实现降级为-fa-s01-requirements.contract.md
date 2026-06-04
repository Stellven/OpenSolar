# Contract: 需求拆解与追踪矩阵

priority: `P0`
epic_id: `epic-20260530-p0-将-5-条-ai-influence-算子固化为-solar-harness-默认接入-并将其余实现降级为-fa`
sprint_id: `sprint-20260530-p0-将-5-条-ai-influence-算子固化为-solar-harness-默认接入-并将其余实现降级为-fa-s01-requirements`
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
- [ ] D1: 5 条主线 + 4 条执行器/辅助脚本（共 9 个文件）的 operator inventory 表完成，每条标注角色(primary/executor/fallback)
- [ ] D2: >= 8 个 requirement groups 从 PRD 6 大目标中提取并编号，标注 P0/P1/P2
- [ ] D3: 每个 requirement group 有 >= 2 条可量化验收标准和风险边界
- [ ] D4: 非目标清单 >= 5 条，覆盖 PRD §6 约束和已知反模式
- [ ] D5: Traceability map 将所有 RG 映射到 S02-S05 切片，识别 >= 3 个跨切片依赖
- [ ] D6: handoff.md 写明: operator inventory + RG 列表 + 验收矩阵 + 非目标 + traceability + 未闭环项
