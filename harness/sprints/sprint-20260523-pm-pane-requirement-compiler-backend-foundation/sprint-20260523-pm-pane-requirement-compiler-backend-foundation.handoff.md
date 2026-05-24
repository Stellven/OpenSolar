# solar-harness Handoff — Requirement Compiler Backend Foundation

## Dispatch Target

`planner`

## Read First

1. `sprint-20260523-pm-pane-requirement-compiler-backend-foundation.prd.md`
2. `sprint-20260523-pm-pane-requirement-compiler-backend-foundation.contract.md`
3. `sprint-20260523-pm-pane-requirement-compiler-backend-foundation.Contracts.yaml`
4. `sprint-20260523-pm-pane-requirement-compiler-backend-foundation.task_graph.json`

## Goal

把这张单从“方案说明”推进成可执行的 P0 backend foundation：锁定分层真值、manifest contract、mixed request 策略、TaskDAG spec/state 分离、dispatch integration，以及 N0..N7 切片。

## Non-Negotiables

- 不允许 `raw request -> builder`
- 不允许把 `Contracts.yaml` 当成第五份 contract
- 不允许把运行态写回 `task_dag.json`
- 不允许 research 请求没有 evidence gate 就进入 done
- 不允许把 `doc-only / contract-only` 冒充 `implemented`

## Planner Must Produce

- `design.md`
- `plan.md`
- `task_graph.json`

并且必须显式回答：

1. `RequirementIR`、contract set、TaskDAG、markdown views 的 source-of-truth layering
2. `Contracts.yaml` manifest semantics
3. mixed request `split / sequence / block_for_clarification`
4. `task_dag.json` vs `task_dag.state.json`
5. `pm-dispatch` / `product-brief` / legacy package adapter
6. `N0..N7` 的工作切片与 gate
7. golden evals 如何独立成 `N7`

## Expected Constraints

- planner 不需要重新猜这张单是 UI sprint 还是 backend sprint：它是 **Requirement Compiler Backend Foundation**
- P0 只做最小 readonly UI，不做重交互
- compatibility 必须保留 `PM -> Planner -> Builder` 主链
