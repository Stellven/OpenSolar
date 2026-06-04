# Contract: Operator Class Compatibility Cutover

Sprint: `sprint-20260523-operator-class-compatibility-cutover`

## Objective

设计旧 role bucket 向新 operator taxonomy 的平滑兼容桥和 staged cutover，不破坏后台正在运行的 worker。

## Hard Rules

- 不允许停掉 `LEASED / RUNNING / DRAINING` 的 operator。
- 不允许强制重启全部 pane。
- 不允许回滚父 sprint 或当前 taxonomy sprint 的 planner 真值。
- 不允许让 legacy role 继续作为长期调度真值。
- 不允许 strict canonical mode 抢跑。
- 不允许无观测切换。

## Required Deliverables

```text
┌───────────────┬─────────────────────────────────────────────────────────────┐
│ deliverable   │ path / expectation                                          │
├───────────────┼─────────────────────────────────────────────────────────────┤
│ design        │ compatibility bridge / canonical mapping / rollout          │
│ plan          │ staged migration + rollback                                 │
│ task_graph    │ audit / mapping / scheduler / safety / observability / rollout │
│ mapping       │ legacy role -> canonical class matrix                       │
│ validation    │ in-flight safety proof + no-breaking evidence               │
│ report        │ strict mode entry criteria / remaining gaps                 │
└───────────────┴─────────────────────────────────────────────────────────────┘
```

## Mandatory Design Decisions

1. 必须引入 `canonical_operator_class` 中间层。
2. legacy role 只能作为 alias / compatibility input。
3. `LEASED / RUNNING / DRAINING` operator 不允许在线重分类。
4. scheduler 必须先 alias resolve，再 canonical resolve，再 strict mode。
5. observability 必须同时展示 legacy / canonical / selected binding。
6. rollout 必须可回退，且不得要求停机。

## Planner Done Definition

- `design.md` 明确 canonical mapping layer。
- `plan.md` 明确 phased rollout。
- `task_graph.json` 每个节点都写清 compatibility / migration / safety / observability 目标。
- 至少一个节点专门处理 in-flight safety。
- 至少一个节点专门处理 status/monitor 三视图。

## Acceptance Gates

- 缺 canonical mapping 不得算完成。
- 缺 `RUNNING/LEASED/DRAINING` 安全规则不算完成。
- 缺 scheduler alias resolve 顺序不算完成。
- 缺 rollout/rollback 不算完成。
