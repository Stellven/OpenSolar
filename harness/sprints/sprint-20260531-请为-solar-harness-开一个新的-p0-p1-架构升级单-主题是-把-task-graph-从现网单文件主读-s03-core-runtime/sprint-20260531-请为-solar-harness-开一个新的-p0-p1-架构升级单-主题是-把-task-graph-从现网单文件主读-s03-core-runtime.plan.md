# Plan: S03 Core-Runtime (task_graph 三分面)

## Wave 1: 状态面落盘与兼容骨架

1. 补 `task_dag.state.json` loader/save path
2. 补 `closure.json` loader/save path
3. 补 legacy graph -> state backfill helper

## Wave 2: 读写职责切换

1. `workflow_guard` 默认消费 spec/state/closure
2. `graph_scheduler` 只从 spec 读拓扑，从 state 读运行态
3. `graph_node_dispatcher` 停止依赖 inline node status

## Wave 3: 兼容镜像与 closeout

1. 实现 mirror compiler
2. closeout 统一从 closure 读
3. 防止 stale node_results 假通过

## Wave 4: 验证

1. 回归 wake / dispatch / status
2. 三分面 drift regression
3. closeout replay

## 停止规则

1. 任何一步若需要改动非本线业务逻辑，先停在 handoff 写清 tradeoff。
2. 若 closeout 证据不可重放，不得宣称 pass。

