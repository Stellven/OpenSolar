# PRD: 核心实现与数据模型

epic_id: `epic-20260531-请为-solar-harness-开一个新的-p0-p1-架构升级单-主题是-把-task-graph-从现网单文件主读`
sprint_id: `sprint-20260531-请为-solar-harness-开一个新的-p0-p1-架构升级单-主题是-把-task-graph-从现网单文件主读-s03-core-runtime`
slice: `core-runtime`

## 用户原始需求

请为 solar-harness 开一个新的 P0/P1 架构升级单，主题是：把 task_graph 从现网单文件主读写对象，正式切到 spec + state + closure 三分面。\n\n核心目标：\n1. workflow_guard 默认检查并消费 requirement_ir、Contracts.yaml manifest、task_graph.spec、task_dag.state.json、closure.json，而不是继续把 task_graph.json 当唯一真值。\n2. graph_scheduler 默认以 task graph spec 为拓扑/依赖/批处理事实源，以 task_dag.state.json 为 node_results/gate_results/leases/dispatch_ids/events 的运行态事实源；禁止 spec/state 混写。\n3. graph_node_dispatcher 默认消费 spec + state + closure，dispatch-ready / drain-queue / mark / parent-check 等路径不再依赖 inline status 或 stale node_results。\n4. 明确 closure.json 不是 passed alias，而是 contract closeout 事实源：需要 all_nodes_passed、all_required_gates_passed、acceptance_traceability_coverage、tests/evals/changed_files/residual_risks。\n5. 兼容现有主链：短期保留 task_graph.json 作为兼容镜像/编译输出，但新 runtime 默认读 spec/state/closure。\n6. 在这条 runtime 切换稳定后，再继续 true compile evaluator + text-first compiler_profile + dataset/valset/hard_cases 分层，再接 offline optimize_anything runner + Pareto profile governance。\n\n边界要求：\n- 不重写整个 harness。\n- 不跳过 workflow_guard / architecture_guard / evaluator gates。\n- 先做 core-runtime 和 verification-release 的结构收口，再谈 optimizer。\n- 这张单必须把 spec/state 漂移、inline status、stale node_results、closeout 不可回放这些问题写清楚。\n\n建议切片：\nS01 requirements：冻结 spec/state/closure 边界、兼容策略、回放语义。\nS02 architecture：定义 workflow_guard / graph_scheduler / graph_node_dispatcher / parent_ready_check / closure operator 的读写职责。\nS03 core-runtime：实现默认消费切换与兼容镜像。\nS04 orchestration-ui：状态面板/可视化切到三分面。\nS05 verification-release：回归、canary、rollback、为 compile evaluator / compiler_profile 外循环预留数据面。\n\n优先级：P0 for spec/state/closure cutover；P1 for compile evaluator + compiler_profile 外循环。

## 本切片目标

实现核心库、状态机、schema、持久化和向后兼容适配层。

## 范围

- 只交付本切片，不允许声称父 Epic 已完成。
- 必须读取 `epic-20260531-请为-solar-harness-开一个新的-p0-p1-架构升级单-主题是-把-task-graph-从现网单文件主读.epic.md`、`epic-20260531-请为-solar-harness-开一个新的-p0-p1-架构升级单-主题是-把-task-graph-从现网单文件主读.traceability.json` 和父级 task_graph。
- 必须在 handoff 中写明上游依赖、下游影响和未闭环项。

## 验收标准

- 核心 API 有单测覆盖
- 旧路径兼容，不破坏现有 wake/dispatch/status
- 状态变更可由元数据或事件重建

## 非目标

- 不直接绕过 planner 派 builder。
- 不用单个大 PRD 覆盖所有实现细节。
- 不用“已完成”替代可复现证据。

## 交付物

- `sprint-20260531-请为-solar-harness-开一个新的-p0-p1-架构升级单-主题是-把-task-graph-从现网单文件主读-s03-core-runtime.design.md`
- `sprint-20260531-请为-solar-harness-开一个新的-p0-p1-架构升级单-主题是-把-task-graph-从现网单文件主读-s03-core-runtime.plan.md`
- `sprint-20260531-请为-solar-harness-开一个新的-p0-p1-架构升级单-主题是-把-task-graph-从现网单文件主读-s03-core-runtime.task_graph.json`
- `sprint-20260531-请为-solar-harness-开一个新的-p0-p1-架构升级单-主题是-把-task-graph-从现网单文件主读-s03-core-runtime.handoff.md`
- `sprint-20260531-请为-solar-harness-开一个新的-p0-p1-架构升级单-主题是-把-task-graph-从现网单文件主读-s03-core-runtime.eval.md` 或 `sprint-20260531-请为-solar-harness-开一个新的-p0-p1-架构升级单-主题是-把-task-graph-从现网单文件主读-s03-core-runtime.eval.json`
