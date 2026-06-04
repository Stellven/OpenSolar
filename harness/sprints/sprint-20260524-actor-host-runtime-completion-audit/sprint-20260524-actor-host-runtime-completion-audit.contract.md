# Contract: Actor Host Runtime Completion Audit

Sprint: `sprint-20260524-actor-host-runtime-completion-audit`

## Objective

让 `solar-harness` 自己逐项核查 13 个 actor/operator/runtime 升级点的真实完成度，并给出证据化结论。

## Hard Rules

- 不允许把 `contract/doc` 当成 `implemented`。
- 不允许只凭印象下结论。
- 不允许跳过运行时证据。
- 不允许把审计单偷换成立即大改实现。
- 不允许遗漏任一升级点。

## Required Deliverables

```text
┌───────────────┬─────────────────────────────────────────────────────────────┐
│ deliverable   │ path / expectation                                          │
├───────────────┼─────────────────────────────────────────────────────────────┤
│ design        │ audit method / evidence sources / judgment rubric           │
│ plan          │ check order / proof workflow / acceptance gates             │
│ task_graph    │ 13-point audit DAG with explicit coverage                   │
│ matrix        │ completion matrix for all 13 upgrade points                 │
│ report        │ top gaps + remediation backlog                              │
└───────────────┴─────────────────────────────────────────────────────────────┘
```

## Mandatory Design Decisions

1. Judgment status only:
   - `implemented`
   - `partial`
   - `contract_only`
   - `missing`
2. `implemented` 必须要求 runtime/code evidence。
3. `contract_only` 至少说明已有哪份 PRD/contract/doc。
4. 审计与 repair 必须分离。
5. remediation backlog 必须分优先级。

## Planner Done Definition

- `design.md` 定义 completion rubric。
- `plan.md` 定义 13 点检查顺序。
- `task_graph.json` 明确每个节点负责哪几条升级点。
- `handoff.md` 或等价报告包含 13 行矩阵。
- 至少一节专门总结“当前生产真值”和“仍停留在 contract 层”的差异。

## Acceptance Gates

- 缺 13 行矩阵不算完成。
- 缺 evidence paths 不算完成。
- 把 `contract_only` 错标成 `implemented` 不算完成。
- 缺 remediation backlog 不算完成。

