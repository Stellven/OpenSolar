# Contract: Requirement Compiler Backend Foundation

Sprint: `sprint-20260523-pm-pane-requirement-compiler-backend-foundation`
Canonical Policy: `IR facts -> contract set -> TaskDAG spec -> markdown/handoff views`

## 1. Source-of-Truth Contract

- `RequirementIR` 是需求事实源。
- `.pm/contracts/*.yaml` 是执行约束事实源。
- `task_dag.json` 是编译后的 executable graph spec。
- `task_dag.state.json` 是运行态，不得污染 DAG spec。
- `prd.md / .contract.md / handoff.md` 是 human-readable compiled views。

## 2. Contracts Manifest Contract

- `Contracts.yaml` 不是第五份 contract。
- `Contracts.yaml` 只承担 manifest / aggregation / digest index 职责。
- planner / builder / evaluator 读取顺序：
  1. `.pm/contracts/*.yaml`
  2. `.pm/Contracts.yaml`
  3. `.contract.md` fallback

## 3. Product Contract

- goal: PM pane 产出三类需求的 RequirementIR、PRD、Contract Set、TaskDAG、Codex/Solar handoff。
- success_metrics:
  - 三类需求均可编译成稳定 `.pm/` 包
  - planner 不需要重新猜分类
  - builder 不可直接消费 raw request
  - research 请求必须有 evidence policy / ledger gate
- non_goals:
  - P0 不做完整四区 UI 重构
  - P0 不做 DAG 拖拽编辑器
  - P0 不绕过 planner 直接派 builder

## 4. Interface Contract

- `RequirementIR`、contract set、TaskDAG、DispatchPackage 必须 schema-valid。
- `task_dag.json` 必须无环。
- 每条 acceptance 必须至少映射一个 validation step。
- mixed request 必须显式输出：
  - `primary_type`
  - `secondary_types`
  - `mixed_request_policy`
- dispatch package 必须包含：
  - `requirement_ir_ref`
  - `contracts_manifest_ref`
  - `task_dag_ref`

## 5. Agent Execution Contract

- raw request 禁止直派 builder。
- interface/contract gate 未通过前，implementation 节点不得开始。
- 高风险节点必须具备 approval gate。
- research 请求若无 evidence policy，不得进入 done。
- 所有变更必须回填：
  - acceptance status
  - validation commands
  - changed files
  - residual risks

## 6. Research Contract

- research 类型默认 `evidence_required = true`
- 每个 engineering implication 必须可追溯到 claim 或 experiment
- 没有 evidence ledger，不得标记完成
- adoption threshold 与 rejection criteria 必须显式存在

## 7. Dispatch Contract

- 派单链路必须是：

```text
User Input
  -> Requirement Compiler
  -> RequirementIR / contracts / TaskDAG
  -> product-brief
  -> planner
  -> builder / evaluator
```

- 明确禁止：
  - `raw request -> builder`
  - `research without evidence -> done`
  - `doc-only / contract-only -> mislabeled implemented`

## 8. Validation Contract

必须新增或强化：

1. `RequirementIR` schema validator
2. contract set validator
3. TaskDAG acyclicity validator
4. acceptance coverage validator
5. dispatch package validator
6. mixed request policy validator
7. research evidence gate validator

## 9. Sprint Slice Contract

- `N0` Baseline inventory
- `N1` RequirementIR schema + validator
- `N2` Upgrade router -> compiler entrypoint
- `N3` PRD + contract compilers
- `N4` TaskDAG compiler + validators
- `N5` Dispatch integration
- `N6` Minimal readonly PM pane
- `N7` Golden evals + docs

`N7` 必须独立存在，不得并入 UI 节点。
