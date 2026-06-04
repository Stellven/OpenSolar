# Contract: 需求拆解与追踪矩阵

priority: `P0`
epic_id: `epic-20260531-请为-solar-harness-开一个新的-p0-p1-架构升级单-主题是-把-task-graph-从现网单文件主读`
sprint_id: `sprint-20260531-请为-solar-harness-开一个新的-p0-p1-架构升级单-主题是-把-task-graph-从现网单文件主读-s01-requirements`
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

## Done

- [ ] D1: 三分面边界定义 — task_graph.spec(拓扑/依赖/gates/acceptance只读) / task_dag.state.json(node_results/gate_results/leases/dispatch_ids/events可写) / closure.json(closeout事实源) 边界已冻结
- [ ] D2: 消费端读写职责矩阵 — workflow_guard/graph_scheduler/graph_node_dispatcher/parent_check 对 spec/state/closure 的读写权限已明确定义
- [ ] D3: Closure Schema 定义 — all_nodes_passed/all_required_gates_passed/acceptance_traceability_coverage/tests/evals/changed_files/residual_risks 字段已定义
- [ ] D4: 兼容策略 — task_graph.json 保留为兼容镜像/编译输出，新 runtime 默认读 spec/state/closure 的迁移路径已定义
- [ ] D5: Spec/State 漂移检测 — inline status/stale node_results/spec-state 混写的检测规则已定义
- [ ] D6: Epic→Sprint Traceability Matrix — S01-S05 输入/输出/验收/依赖追踪表已生成
