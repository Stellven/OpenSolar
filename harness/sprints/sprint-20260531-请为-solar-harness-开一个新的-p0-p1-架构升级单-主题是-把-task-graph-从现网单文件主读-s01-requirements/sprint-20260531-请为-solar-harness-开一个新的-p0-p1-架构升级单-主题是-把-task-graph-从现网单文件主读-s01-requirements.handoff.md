# Handoff

## 结论

S01 requirements 已完成：`spec + state + closure` 三分面切换的目标、边界、兼容策略和后续 architecture 任务已冻结，可进入 `S02_architecture`。

## 本切片锁定的 requirements 真值

1. `task_graph.spec` 负责拓扑/依赖/批处理事实源。
2. `task_dag.state.json` 负责 node_results / gate_results / leases / dispatch_ids 等运行态。
3. `closure.json` 负责 closeout 事实源，不能等同于 `passed` alias。
4. `workflow_guard / graph_scheduler / graph_node_dispatcher` 不能继续把单文件 `task_graph.json` 当唯一真值。
5. P0 先做 runtime 三分面切换，P1 再做 compile evaluator / compiler_profile 外循环。

## 进入 S02 必做项

1. 定义 workflow_guard 对 `requirement_ir / Contracts manifest / spec / state / closure` 的默认消费
2. 定义 graph_scheduler 的 spec/state 职责分离
3. 定义 graph_node_dispatcher 的 dispatch-ready / drain-queue / mark / parent-check 读写边界
4. 定义 closure.json closeout contract 与回放语义
5. 明确兼容镜像 / stale node_results / drift/backfill 策略

## 未闭环项

1. 还没有完成全量 runtime cutover
2. 还没有正式接 `true compile evaluator`
3. 还没有把 `compiler_profile` 与 GEPA 外循环接进治理面
