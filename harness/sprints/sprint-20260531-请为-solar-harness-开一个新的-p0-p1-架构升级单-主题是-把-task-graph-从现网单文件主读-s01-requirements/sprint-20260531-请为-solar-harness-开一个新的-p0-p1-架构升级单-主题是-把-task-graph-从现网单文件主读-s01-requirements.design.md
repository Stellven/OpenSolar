# Design: task_graph spec/state/closure 三分面 — Requirements (S01)

sprint_id: `sprint-20260531-请为-solar-harness-开一个新的-p0-p1-架构升级单-主题是-把-task-graph-从现网单文件主读-s01-requirements`

## 1. 三分面定义

| 分面 | 文件 | 语义 | 读写 |
|------|------|------|------|
| Spec | `task_graph.spec.json` | 拓扑/依赖/gates/acceptance/write_scope — 编译时冻结 | 只读 (runtime 不修改) |
| State | `task_dag.state.json` | node_results/gate_results/leases/dispatch_ids/events — 运行态 | 可写 (scheduler/dispatcher/evaluator) |
| Closure | `closure.json` | contract closeout 事实源 — 全部 passed 后生成 | 只写一次 (evaluator 生成) |

当前问题：task_graph.json 同时承载 spec + state，导致 spec/state 混写、inline status 漂移、stale node_results、closeout 不可回放。

## 2. Spec Schema (只读)

```json
{
  "schema_version": "solar.task_graph.spec.v1",
  "sprint_id": "string",
  "required_gates": ["G1"],
  "nodes": [
    {
      "id": "N1",
      "goal": "string",
      "depends_on": [],
      "write_scope": [],
      "read_scope": [],
      "required_skills": [],
      "preferred_model": "sonnet",
      "gate": "G1",
      "acceptance": [],
      "estimated_cost": 1,
      "stop_rules": []
    }
  ]
}
```

## 3. State Schema (可写运行态)

```json
{
  "schema_version": "solar.task_dag.state.v1",
  "sprint_id": "string",
  "updated_at": "datetime",
  "node_results": {
    "N1": {
      "status": "pending|dispatched|running|passed|failed|skipped",
      "dispatch_id": "string",
      "operator_id": "string",
      "lease_id": "string",
      "started_at": "datetime",
      "completed_at": "datetime",
      "verdict": "string",
      "artifacts": [],
      "error": "string"
    }
  },
  "gate_results": {
    "G1": {"passed": true, "passed_at": "datetime", "by_node": "N1"}
  },
  "events": [
    {"ts": "datetime", "event": "string", "node_id": "string", "by": "string"}
  ]
}
```

## 4. Closure Schema

```json
{
  "schema_version": "solar.closure.v1",
  "sprint_id": "string",
  "closed_at": "datetime",
  "all_nodes_passed": true,
  "all_required_gates_passed": true,
  "acceptance_traceability_coverage": 1.0,
  "tests": [{"name": "string", "result": "pass|fail"}],
  "evals": [{"evaluator": "string", "verdict": "string"}],
  "changed_files": ["path"],
  "residual_risks": ["string"],
  "evidence_refs": ["artifact_path"]
}
```

## 5. 消费端读写职责矩阵

| 消费端 | Spec | State | Closure | 当前行为 |
|--------|------|-------|---------|---------|
| workflow_guard | R | R | R | 只读 task_graph.json |
| graph_scheduler | R (拓扑/依赖) | R/W (dispatch_ids) | — | 混读 task_graph.json |
| graph_node_dispatcher | R (节点定义) | R/W (node_results) | — | 混读混写 task_graph.json |
| parent_ready_check | R (required_gates) | R (gate_results) | R | 混读 task_graph.json |
| evaluator | R (acceptance) | R/W (verdicts) | W (生成) | 不读 closure |
| planner | W (生成) | — | — | 写 task_graph.json |

## 6. 兼容策略

- 短期：保留 `task_graph.json` 作为兼容镜像/编译输出
- 新 runtime 默认读 spec/state/closure
- `task_graph.json` 由 spec+state compile 生成 (向后兼容外部工具)
- 迁移路径：先双写 → 新消费端切 spec/state → 验证稳定后废弃 inline status

## 7. Spec/State 漂移检测规则

| 漂移类型 | 检测规则 | 严重性 |
|---------|---------|--------|
| Inline status in spec | spec 中出现 status/node_results 字段 | ERROR |
| Topology mutation in state | state 中修改了 depends_on/gate | ERROR |
| Stale node_results | state.node_results 与 dispatch 实际结果不一致 | WARN |
| Spec-state sprint_id mismatch | spec.sprint_id ≠ state.sprint_id | ERROR |
| Closure without all_passed | closure 存在但 all_nodes_passed=false | ERROR |

## 8. 需求分组

| RG | 需求 | 验收 | 对应切片 |
|----|------|------|---------|
| RG1 | Spec Schema 定义 | JSON schema + 验证 | S01→S02 |
| RG2 | State Schema 定义 | JSON schema + 验证 | S01→S02 |
| RG3 | Closure Schema 定义 | JSON schema + 验证 | S01→S02 |
| RG4 | 消费端读写职责矩阵 | 每个消费端明确 R/W/— | S01→S02 |
| RG5 | 兼容策略 | 双写 → 切换 → 废弃路径 | S01→S03 |
| RG6 | 漂移检测规则 | 5 条检测规则实现 | S01→S03 |
| RG7 | Closure 生成流程 | evaluator 生成 closure | S01→S03 |
| RG8 | 状态面板切换 | 三分面可视化 | S01→S04 |

## 9. Epic→Sprint Traceability

| 切片 | 输入 | 产出 | 验收 | 依赖 |
|------|------|------|------|------|
| S01 requirements | epic.md | 三分面 schema, 职责矩阵, 漂移规则 | D1-D6 | 无 |
| S02 architecture | S01 schema + 矩阵 | 消费端接口设计, migration plan | 架构 review | S01 |
| S03 core-runtime | S02 架构 | spec/state 分离, closure 生成, 双写 | 功能可用 | S02 |
| S04 observability | S03 | 三分面状态面板 | 面板可用 | S03 |
| S05 verification | S03+S04 | 漂移检测 + 回归 + canary | 全 PASS | S03,S04 |

## 10. 非目标
- 不重写整个 harness
- 不跳过 workflow_guard / architecture_guard
- 不在 S01 实现 compile evaluator / compiler_profile 外循环
- 不删除 task_graph.json (保留为兼容镜像)

## 11. 风险

| # | 风险 | 影响 | 缓解 |
|---|------|------|------|
| R1 | 外部工具直接读写 task_graph.json | 双写不一致 | 双写期间 lint 检查 |
| R2 | State 并发写入冲突 | 数据丢失 | 原子写入 + lock |
| R3 | 迁移期间 spec/state 不同步 | 调度错误 | canary + rollback |
