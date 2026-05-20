# Design — S02 架构设计与接口契约

sprint_id: `sprint-20260519-solar-harness-vnext-code-as-harness-runtime-s02-architecture`
epic_id: `epic-20260519-solar-harness-vnext-code-as-harness-runtime`
slice: `architecture`
date: 2026-05-20
Knowledge Context: solar-harness context inject used

## 1. 架构目标

S02 的目标不是写运行时代码，而是冻结 P0 可实现边界：Plan IR、Action Contract、Execution Broker、Event Ledger、Verifier 输出和旧系统兼容层。S03 才能基于这些接口实现 core runtime，S04 才能接入 four-pane dispatch/UI，S05 才能做 broker coverage 与兼容性终验。

目标约束：

- 所有可执行动作必须由 `ActionContract` 描述，禁止 Builder 直接凭 prompt 调 shell/file_write/tool_call。
- 旧 `status.json`、`task_graph.json`、`wake/dispatch/main-status` 继续可用，但不再是唯一事实源。
- Event Ledger 是 append-only 审计链，status/projection 可以重放，不允许用不可追踪的临时状态覆盖事实。
- 高风险动作默认需要显式 approval，不允许通过 deterministic fallback 冒充通过。

## 2. Control Plane / Data Plane 分层

```text
Control Plane
  PRD / Contract
    -> Plan IR
      -> Task Graph
        -> Node Contract
          -> Action Contract
            -> Execution Broker

Data Plane
  Action Inputs
    -> Sandbox Execution
      -> Captured Output
        -> Artifact Registry Ref
          -> Verifier Evidence
            -> Event Ledger
              -> Status Projection
```

控制面负责授权、调度、策略和状态投影。数据面负责真实输入、输出、artifact、hash、evidence。两者必须分离：Planner 可以生成 contract，但不能把“计划文字”当成执行证据；Builder 可以执行 action，但不能绕过 broker 修改状态；Evaluator 只消费 verifier evidence 和 ledger projection，不读 pane 文案判定通过。

## 3. Plan IR

`PlanIR` 是 Sprint/Node/Action 的稳定中间表示。它从现有 `task_graph.json` 派生，但补齐 action-level 执行语义。

最小结构：

```json
{
  "schema_version": "solar.plan_ir.v1",
  "sprint_id": "sprint-...",
  "epic_id": "epic-...",
  "nodes": [
    {
      "node_id": "N1",
      "goal": "implement action contract schema",
      "depends_on": [],
      "read_scope": [],
      "write_scope": [],
      "required_capabilities": [],
      "actions": ["A1", "A2"],
      "gate": "G_N1"
    }
  ],
  "actions": []
}
```

规则：

- `nodes[*].write_scope` 仍用于 DAG 并发冲突检测。
- `actions[*].write_set` 是执行层更细粒度写范围，必须被 broker policy 检查。
- `required_capabilities` 允许由 capability inference 补齐，但补齐结果必须写回 action contract 或 projection。
- schema evolution 只允许新增 optional 字段，不允许删除 P0 required 字段。

## 4. Action Contract

P0 冻结字段：

```json
{
  "schema_version": "solar.action_contract.v1",
  "action_id": "A1",
  "node_id": "N3",
  "kind": "shell",
  "intent": "run deterministic verifier",
  "read_set": ["harness/lib/research/evaluator.py"],
  "write_set": ["harness/sprints/.../research_eval.json"],
  "required_capabilities": ["research.evaluate"],
  "preconditions": ["input artifact exists"],
  "success_predicates": ["exit_code == 0"],
  "verification": {
    "static": true,
    "runtime": ["python3 -m py_compile harness/lib/research/evaluator.py"],
    "evidence": ["research_eval.json"]
  },
  "rollback": {
    "kind": "git_restore",
    "target": ["harness/lib/research/evaluator.py"]
  },
  "risk_class": "medium",
  "approval_required": false
}
```

字段语义：

| 字段 | 语义 | P0 约束 |
|------|------|---------|
| `kind` | 执行动作类别 | enum: shell, python, file_write, tool_call, research_extract, human_approval |
| `read_set` | 动作允许读取的文件或 artifact ref | 为空时视为未知读，policy warning |
| `write_set` | 动作允许写入的文件或 artifact ref | file_write/shell 产生写入时不能为空 |
| `success_predicates` | 动作成功条件 | 不能只写“完成”，必须可检查 |
| `verification` | 验证方法和证据 | 无 evidence 不允许 PASS |
| `rollback` | 回滚策略 | 写 repo 文件时 required |
| `risk_class` | 风险等级 | apply/git/network write 默认 high |
| `approval_required` | 审批要求 | high 默认 true，除非 allowlist 明确豁免 |

## 5. Execution Broker 接口

Broker 是 GEMS enforcement broker，不是建议层。

```text
propose_action(contract)
  -> validate_contract(contract)
  -> infer_missing_capabilities(contract)
  -> policy_check(contract, actor, state_revision)
  -> acquire_lease(contract.write_set)
  -> execute_in_sandbox(contract)
  -> capture_outputs(result)
  -> verify_outputs(contract, result)
  -> register_artifacts(result)
  -> append_event(...)
  -> update_projection(...)
```

P0 接口边界：

- `validate_contract` 只做 schema/字段/枚举检查，不执行动作。
- `policy_check` 做 approval、write_scope、capability、risk_class、legacy allowlist 检查。
- `execute_in_sandbox` 是唯一执行入口；Planner/Builder/Evaluator 不直接调用 shell/file_write/tool_call。
- `append_event` 成功和失败都写 ledger，失败不能静默吞掉。
- `update_projection` 只从 event ledger 派生，不直接相信 pane 输出。

## 6. Policy 决策

| 场景 | 默认判定 | 原因 | 允许例外 |
|------|----------|------|----------|
| 无 action contract | FAIL | 无法审计 | 无 |
| file_write 但 `write_set=[]` | FAIL | 写范围不可控 | 无 |
| shell 声称只读但产生文件 | FAIL | 违反 contract | 重新生成 contract |
| apply/git commit/git push | HIGH + approval | 可破坏 repo 状态 | human approval event |
| network write/purchase/send | HIGH + approval | 外部可见副作用 | human approval event |
| 只读 grep/sed/jq | LOW | 可重放、低副作用 | 仍需 event |
| legacy dispatch path | WARN | 兼容期允许 | 必须 `legacy=true` 且计入 coverage |

S02 采纳 S01 未闭环拍板：`apply=high`、`git=high`、`network_write=high`。这不是永久策略，而是 P0 安全默认值；后续可以通过 allowlist 降低特定只读或本地安全动作。

## 7. Event Ledger 选型

P0 采用 JSONL + advisory lock + fsync + atomic append 的最小实现，原因：

- 与现有文件型 harness 一致，迁移成本低。
- 便于人工审计、diff、恢复。
- S03 可快速实现 replay smoke，不需要引入 SQLite migration 风险。

后续 P1 可增加 SQLite WAL projection，但事实源仍建议保留 JSONL。

事件最小结构：

```json
{
  "event_id": "evt_...",
  "ts": "2026-05-20T00:00:00Z",
  "sprint_id": "sprint-...",
  "node_id": "N1",
  "action_id": "A1",
  "type": "action.executed",
  "actor": "builder:0.2",
  "input_hash": "sha256:...",
  "output_hash": "sha256:...",
  "policy_verdict": "PASS",
  "evidence_refs": ["artifact:..."],
  "parent_event_ids": []
}
```

必写事件：

- `action.proposed`
- `policy.verdict`
- `action.executed`
- `action.failed`
- `artifact.registered`
- `verifier.verdict`
- `projection.updated`

## 8. Verifier 输出契约

统一输出：

```json
{
  "schema_version": "solar.verifier_result.v1",
  "verifier": "runtime",
  "verdict": "PASS",
  "metrics": {},
  "errors": [],
  "warnings": [],
  "evidence_refs": []
}
```

P0 只要求把现有检查包进统一接口：

- `static` verifier: py_compile / jsonschema / grep hard gate。
- `runtime` verifier: smoke command exit code + captured output。
- `policy` verifier: broker coverage、unscoped write、approval bypass。
- `regression` verifier: wake/dispatch/status/graph_scheduler smoke。

DeepResearch `research/evaluator.py` 保持 P1/P2，不进入 S03 P0 实现路径；但 S02 保留接口兼容位置。

## 9. 兼容与迁移

兼容原则：

- 旧 `task_graph.json` 不删除，只增加可选 `action_contracts` 或通过 sidecar Plan IR 引用。
- 旧 `status.json` 继续写，但标记为 projection；真实执行事实来自 ledger。
- 旧 `dispatch.md` 保留；Builder 执行前由 dispatcher 生成或查找 action contract。
- 旧 four-pane UI 保留；S04 只增加 broker coverage、action/event/artifact/verifier 状态展示。

迁移步骤：

1. S03 增加 schema + broker + ledger，但默认 dry-run/observe mode。
2. S03 为 shell/file_write/tool_call 建最小执行适配器。
3. S04 dispatcher 开启 enforce mode：无 contract 不派发 builder。
4. S05 activation-proof 校验 coverage=100%，legacy path 为 0 或显式豁免。

## 10. 失败恢复

| 失败 | 分类 | 恢复策略 |
|------|------|----------|
| schema validation fail | PLAN_INVALID | 阻断 Builder，返回 Planner 修 contract |
| write_scope conflict | WRITE_SCOPE_CONFLICT | graph scheduler 不并行，broker 拒绝执行 |
| policy fail | CAPABILITY_MISMATCH / HUMAN_APPROVAL_REQUIRED | 写 event，不执行 action |
| action exit non-zero | EXECUTION_FAILED | 捕获 stdout/stderr，生成 repair node |
| verifier fail | VERIFICATION_FAILED | 不写 PASS projection，要求修复 |
| ledger append fail | STATE_CONFLICT | 不更新 status projection，保留原状态 |
| projection replay fail | REGRESSION_RISK | 回滚到 last known good projection |

## 11. S03/S04/S05 交付边界

S03 core runtime:

- 交付 schema 文件、contract parser、broker MVP、event ledger、policy modules、basic tests。
- 不改 dashboard，不做 ResearchGraph，不做 full artifact registry。

S04 orchestration/UI:

- graph_node_dispatcher 接入 broker。
- four-pane 状态显示 broker coverage、action count、last policy verdict。
- status server 链接到 action/event artifacts。

S05 verification/release:

- activation-proof 增加 broker coverage。
- regression smoke: wake/dispatch/main-status/graph-scheduler。
- final handoff 用 S01 七列表格格式，证明 O-03/O-08/O-09 闭环。

## 12. Architecture Gate

S02 通过条件：

- `design.md` 覆盖 control/data plane、state、failure recovery、observability。
- `plan.md` 明确 S03/S04/S05 执行顺序和验收。
- `task_graph.json` 通过 `solar-harness graph-scheduler validate`。
- Builder 不得在缺 `task_graph.json` 时执行。

