# Handoff: S02 Architecture (task_graph 三分面系统设计切片)

sprint_id: `sprint-20260531-请为-solar-harness-开一个新的-p0-p1-架构升级单-主题是-把-task-graph-从现网单文件主读-s02-architecture`
Knowledge Context: `solar-harness context inject used`

## 1. 结论与已完成事项

S02 Architecture 架构设计已完成，成功规划三分面切分方案并生成子任务依赖。
本切片已产出：
1. `sprint-20260531-...-s02-architecture.design.md` - layered design, matrices, drift rules.
2. `sprint-20260531-...-s02-architecture.plan.md` - implementation waves, stop rules, SLO metrics.
3. `sprint-20260531-...-s02-architecture.task_graph.json` - validated child task graph.
4. Compiled HTML artifacts: `design.html`, `planning.html`.

---

## 2. 下游任务启动数据包 (Downstream Kickoff Package)

### 2.1 S03 Core-Runtime (核心实现与兼容策略)
- **数据结构 Model**: `task_graph.spec.json` (只读拓扑), `task_dag.state.json` (读写状态机), `closure.json` (闭环归档)。
- **核心逻辑**:
  - `workflow_guard`: 改为默认顺序读取 spec, state, closure，替代原单文件 `task_graph.json` 真值。
  - `MirrorCompiler`: 实现合并 `spec` 和 `state` 字段，编译写出兼容 `task_graph.json` 镜像的逻辑。
  - **Drift Lint 规则**: 实现 5 条一致性校验逻辑。

### 2.2 S04 Orchestration-UI (调度、自动与可视化)
- **调度流**: `graph_scheduler` 改为依据 `spec` 计算拓扑并动态读取/回写 `state` 进行驱动。
- **状态监控**: 升级面板与 CLI 检查逻辑，当触发状态查询时直接由 `state` 面提供渲染事实。
- **派发器升级**: `graph_node_dispatcher` 仅对 `state` 进行基于文件锁的写，不破坏 spec 的只读性质。

### 2.3 S05 Verification-Release (验证与发布)
- **测试用例**: 提供对 spec-state 漂移、并发锁状态更新、以及 rollback 重置场景的影子验证用例。
- **闭环验证**: 校验 closure 生成是否包含 tests/evals 凭证并被成功导出至知识库 raw 区。

---

## 3. 残余风险与未闭环项 (Residual Risks)

1. **并行写锁机制优化度**: 并发磁盘锁在超高频写入下可能触发少量退避重试，需在 S03 代码编写中仔细进行压测和异常防范。
2. **存量 Sprint 兼容转换**: 存量处于活动态的 sprint 可能需要在引入 S03 runtime 后执行一次性 spec-state 同步，需提供 migration 补丁。
