# Contract: 需求拆解与追踪矩阵

priority: `P0`
epic_id: `epic-20260530-p0-修复单-去除-tmux-send-keys-作为主任务协议-收口到-operatord-mailbox-runti`
sprint_id: `sprint-20260530-p0-修复单-去除-tmux-send-keys-作为主任务协议-收口到-operatord-mailbox-runti-s01-requirements`
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
- [ ] D1: 从修复单提取 >= 10 个 RG，覆盖 task envelope schema、mailbox 协议、coordinator cutover、operatord 升级、send-keys 降级、兼容层、验收
- [ ] D2: 每个 RG 有量化验收标准（如「coordinator.ts 中 dispatchToPane() 调用数降为 0」）
- [ ] D3: 非目标边界 >= 5 条（不删除 tmux、不重写 DAG scheduler、不实现远程 mailbox 等）
- [ ] D4: 风险识别 >= 5 条（send-keys 切换中断生产、mailbox 未实现、operatord 状态不一致等）
- [ ] D5: 生成 epic → 5 slice traceability map，RG 映射到 S02-S05
- [ ] D6: handoff.md 含 RG 清单、task envelope schema 草案、S02 设计需求和未闭环项
