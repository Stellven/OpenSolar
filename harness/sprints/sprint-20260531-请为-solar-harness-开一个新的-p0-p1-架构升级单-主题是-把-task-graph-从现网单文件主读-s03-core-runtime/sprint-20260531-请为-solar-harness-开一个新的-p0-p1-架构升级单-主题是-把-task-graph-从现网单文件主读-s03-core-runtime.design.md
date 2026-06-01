# Design: S03 Core-Runtime (task_graph 三分面)

## 1. 目标

把 `spec + state + closure` 从架构结论变成可运行的默认 runtime 行为，同时保留 `task_graph.json` 兼容镜像，避免现网 wake/dispatch/status 断裂。

## 2. 实现范围

1. `workflow_guard`
   - 默认顺序：`task_graph.spec` / `task_dag.state.json` / `closure.json`
   - `task_graph.json` 仅作为镜像和 fallback
2. `graph_scheduler`
   - 拓扑、依赖、批处理只读 spec
   - node/gate/lease/dispatch 只写 state
3. `graph_node_dispatcher`
   - `dispatch-ready`、`drain-queue`、`mark`、`parent-check` 不再依赖 inline status
4. `closure operator`
   - 明确 closeout 证据：tests/evals/changed_files/residual_risks/coverage
5. `MirrorCompiler`
   - 从 spec+state 生成兼容 `task_graph.json`

## 3. 运行时数据模型

### 3.1 `task_graph.spec.json`
- sprint_id
- nodes
- required_gates
- dependency_policy
- architecture_guard

### 3.2 `task_dag.state.json`
- sprint_id
- node_results
- gate_results
- active_leases
- dispatch_ids
- updated_at
- event_cursor

### 3.3 `closure.json`
- sprint_id
- all_nodes_passed
- all_required_gates_passed
- acceptance_traceability_coverage
- tests
- evals
- changed_files
- residual_risks
- closed_at

## 4. 兼容策略

1. 读路径先看 spec/state/closure。
2. 写路径禁止再把 runtime 状态塞回 spec。
3. `task_graph.json` 继续生成，但只作为兼容镜像。
4. 老 sprint 缺 state/closure 时允许 fail-open 读取 legacy graph，并在首次写入时回填 state skeleton。

## 5. 风险点

1. 老单 inline status 与 `node_results` 双真值漂移。
2. `wake` / `status-server` / `graph_node_dispatcher` 可能仍有 legacy 假设。
3. migration/backfill 需避免覆盖正在运行的 lease。

## 6. 本切片 Definition of Done

1. 默认 runtime 读写三分面。
2. legacy graph 仍可被镜像消费。
3. 有针对 `workflow_guard / scheduler / dispatcher / closeout` 的单测。

